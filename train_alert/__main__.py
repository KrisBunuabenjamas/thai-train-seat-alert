import argparse
from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import sys

from .discord import Discord
from .dticket import BANGKOK, DTicketClient
from .http import HttpError
from .runner import run_once
from .state import fresh_state
from .storage import GitHubStore, LocalStore


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    for field in ('origin', 'destination'):
        if not isinstance(config.get(field), str) or not re.fullmatch(r'\d+', config[field]):
            raise ValueError('Invalid station configuration')
    if config['origin'] == config['destination']:
        raise ValueError('Origin and destination must differ')
    days = config.get('dates')
    if not isinstance(days, list) or not days or len(days) != len(set(days)):
        raise ValueError('Invalid date configuration')
    for day in days:
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError('Dates must use YYYY-MM-DD')
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description='D-Ticket sleeper availability → Discord')
    parser.add_argument('--mode', choices=['dry-run', 'initialize', 'check', 'test-discord'], default='dry-run')
    parser.add_argument('--store', choices=['local', 'github'], default='local')
    parser.add_argument('--state', default='state.json')
    parser.add_argument('--config', default='config.json')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        now = datetime.now(BANGKOK)
        if args.mode in ('check', 'dry-run') and max(config['dates']) < now.date().isoformat():
            print(json.dumps({'expired': True, 'message': 'All travel dates have passed; no network calls'}))
            return 0
        if args.mode == 'dry-run':
            rows, errors = DTicketClient().check(config, now)
            result = {'mode': 'dry-run', 'checked_at': now.isoformat(),
                      'observations': [x.to_dict() for x in rows], 'errors': errors}
        elif args.mode == 'test-discord':
            Discord(os.environ.get('DISCORD_WEBHOOK_URL', '')).send({'kind': 'test'})
            result = {'test_notification': 'acknowledged', 'errors': []}
        else:
            store = (GitHubStore(os.environ.get('GITHUB_REPOSITORY', ''), os.environ.get('GITHUB_TOKEN', ''))
                     if args.store == 'github' else LocalStore(args.state))
            if args.mode == 'initialize':
                if args.store == 'github':
                    store.initialize(fresh_state(config), os.environ.get('GITHUB_SHA'))
                else:
                    store.initialize(fresh_state(config))
                result = {'initialized': True, 'monitoring_started': False, 'errors': []}
            else:
                sender = Discord(os.environ.get('DISCORD_WEBHOOK_URL', ''))
                result = run_once(DTicketClient(), store, sender, config, now)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('errors') else 0
    except (ValueError, RuntimeError, OSError, HttpError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
