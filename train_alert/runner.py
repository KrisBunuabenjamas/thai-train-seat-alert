from datetime import timedelta
import time
from .state import validate_state, reconcile, pending_alerts, acknowledge, aware_time


def run_once(client, store, sender, config, now, clock=None):
    started = time.monotonic()
    clock = clock or (lambda: now + timedelta(seconds=time.monotonic() - started))
    state = validate_state(store.load(), config)
    observations, errors = client.check(config, clock())
    reconcile(state, observations, errors, clock())
    # A conflict/storage failure here must prevent any outgoing notification.
    store.save(state)
    result = {'checked_at': state['checked_at'], 'observations': [x.to_dict() for x in observations],
              'sent': 0, 'errors': list(state['health']['errors'])}
    for event in pending_alerts(state, observations, clock()):
        if event['kind'] == 'availability' and aware_time(event['observation']['departure_at']) <= clock():
            del state['pending'][event['id']]
            store.save(state)
            continue
        try:
            sender.send(event)
        except RuntimeError:
            result['errors'].append('Discord delivery failed; pending event retained')
            break
        acknowledge(state, event)
        store.save(state)
        result['sent'] += 1
    result['pending'] = len(state['pending'])
    return result
