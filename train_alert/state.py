"""Durable observations and an at-least-once pending notification queue."""
import hashlib
import json
from datetime import datetime


def fingerprint(config):
    values = {key: config[key] for key in ('origin', 'destination', 'dates')}
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()


def fresh_state(config):
    return {'version': 1, 'config': fingerprint(config), 'entries': {}, 'pending': {},
            'checked_at': None, 'health': {'failures': 0, 'notified': False, 'errors': []}}


def aware_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Timezone missing')
    return parsed


def validate_state(state, config):
    try:
        if state['version'] != 1 or state['config'] != fingerprint(config):
            raise ValueError('State version/config mismatch')
        if not isinstance(state['entries'], dict) or not isinstance(state['pending'], dict):
            raise ValueError('Invalid entries/pending')
        if state['checked_at'] is not None:
            aware_time(state['checked_at'])
        health = state['health']
        if type(health['failures']) is not int or health['failures'] < 0 or type(health['notified']) is not bool:
            raise ValueError('Invalid health')
        if not isinstance(health['errors'], list) or any(not isinstance(x, str) for x in health['errors']):
            raise ValueError('Invalid health errors')
        for key, entry in state['entries'].items():
            if entry['key'] != key or not isinstance(key, str):
                raise ValueError('Invalid entry key')
            for name in ('count', 'cycle'):
                if type(entry[name]) is not int or entry[name] < 0:
                    raise ValueError('Invalid entry count/cycle')
            for name in ('date', 'train', 'coach', 'description', 'arrival_time'):
                if not isinstance(entry[name], str) or not entry[name]:
                    raise ValueError('Invalid entry field')
            aware_time(entry['departure_at'])
            aware_time(entry['observed_at'])
        for key, event in state['pending'].items():
            if event['id'] != key or event['kind'] not in ('availability', 'health_failure', 'health_recovery'):
                raise ValueError('Invalid event')
            aware_time(event['created_at'])
            if event['kind'] == 'availability' and event['key'] not in state['entries']:
                raise ValueError('Orphan event')
    except (KeyError, TypeError, AttributeError, ValueError):
        raise ValueError('State is corrupt or belongs to a different configuration; refusing to reset') from None
    return state


def reconcile(state, observations, errors, now):
    stamp = now.isoformat()
    fresh = {o.key: o for o in observations}
    problems = list(errors)
    for key, old in state['entries'].items():
        if key not in fresh and aware_time(old['departure_at']) > now:
            problems.append(f'Missing previously observed coach {key}')
    for observation in observations:
        if aware_time(observation.departure_at) <= now:
            continue
        old = state['entries'].get(observation.key)
        cycle = old['cycle'] if old else 0
        if observation.count > 0 and (old is None or old['count'] == 0):
            cycle += 1
            event_id = f'{observation.key}:{cycle}'
            state['pending'][event_id] = {'id': event_id, 'kind': 'availability',
                'key': observation.key, 'created_at': stamp}
        state['entries'][observation.key] = {**observation.to_dict(), 'cycle': cycle, 'observed_at': stamp}
    for event_id, event in list(state['pending'].items()):
        if event['kind'] == 'availability':
            entry = state['entries'][event['key']]
            if entry['count'] == 0 or aware_time(entry['departure_at']) <= now:
                del state['pending'][event_id]
    health = state['health']
    health['failures'] = health['failures'] + 1 if problems else 0
    health['errors'] = problems[:20]
    if problems:
        state['pending'].pop('health_recovery', None)
        if health['failures'] >= 3 and not health['notified']:
            state['pending'].setdefault('health_failure', {'id': 'health_failure',
                'kind': 'health_failure', 'created_at': stamp})
    else:
        state['pending'].pop('health_failure', None)
        if health['notified']:
            state['pending'].setdefault('health_recovery', {'id': 'health_recovery',
                'kind': 'health_recovery', 'created_at': stamp})
    state['checked_at'] = stamp


def pending_alerts(state, observations, now):
    fresh = {o.key: o for o in observations if o.count > 0 and aware_time(o.departure_at) > now}
    result = []
    for event in state['pending'].values():
        if event['kind'] != 'availability':
            result.append({**event, 'health': dict(state['health'])})
        elif event['key'] in fresh:
            result.append({**event, 'observation': fresh[event['key']].to_dict(),
                           'checked_at': state['checked_at']})
    return result


def acknowledge(state, event):
    del state['pending'][event['id']]
    if event['kind'] == 'health_failure':
        state['health']['notified'] = True
    elif event['kind'] == 'health_recovery':
        state['health']['notified'] = False
