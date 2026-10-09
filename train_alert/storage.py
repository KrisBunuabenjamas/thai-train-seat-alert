import base64
import json
import os
import re
from pathlib import Path

from .http import HTTP, HttpError, decode_json


class LocalStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            return json.loads(self.path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise RuntimeError('State missing/unreadable; initialize explicitly only on first setup') from None

    def initialize(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self.path.open('x', encoding='utf-8') as out:
                json.dump(state, out, ensure_ascii=False, indent=2)
        except FileExistsError:
            raise RuntimeError('State already exists; refusing to reset') from None

    def save(self, state):
        temporary = self.path.with_name(self.path.name + '.tmp')
        with temporary.open('w', encoding='utf-8') as out:
            json.dump(state, out, ensure_ascii=False, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, self.path)


class GitHubStore:
    def __init__(self, repository, token, http=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) or not token:
            raise ValueError('GitHub repository/token not configured')
        self.base = f'https://api.github.com/repos/{repository}'
        self.http = http or HTTP(attempts=1)
        self.headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/vnd.github+json',
                        'X-GitHub-Api-Version': '2022-11-28'}
        self.sha = None

    def call(self, method, path, body=None):
        return decode_json(self.http.request(method, self.base + path,
                            headers=self.headers, json_body=body))

    def load(self):
        try:
            result = self.call('GET', '/contents/state.json?ref=monitor-state')
            self.sha = result['sha']
            return json.loads(base64.b64decode(result['content']).decode('utf-8'))
        except (HttpError, KeyError, ValueError, TypeError):
            raise RuntimeError('Cannot load GitHub state; check permissions and explicit initialization') from None

    def initialize(self, state, seed_sha=None):
        if not seed_sha or not re.fullmatch(r'[0-9a-f]{40}', seed_sha):
            raise ValueError('Initialization requires a valid GITHUB_SHA')
        try:
            self.call('GET', '/git/ref/heads/monitor-state')
        except HttpError as exc:
            if exc.status != 404:
                raise RuntimeError('Cannot inspect GitHub state branch') from None
            self.call('POST', '/git/refs', {'ref': 'refs/heads/monitor-state', 'sha': seed_sha})
        try:
            self.call('GET', '/contents/state.json?ref=monitor-state')
        except HttpError as exc:
            if exc.status != 404:
                raise RuntimeError('Cannot inspect existing GitHub state') from None
        else:
            raise RuntimeError('State already exists; refusing to reset')
        self._write(state, create=True)

    def _write(self, state, create=False):
        body = {'message': 'chore: persist monitor heartbeat and pending alerts',
                'branch': 'monitor-state', 'content': base64.b64encode(
                    json.dumps(state, ensure_ascii=False, indent=2).encode()).decode()}
        if not create:
            if not self.sha:
                raise RuntimeError('Load state before saving')
            body['sha'] = self.sha
        try:
            result = self.call('PUT', '/contents/state.json', body)
            self.sha = result['content']['sha']
        except (HttpError, KeyError, TypeError):
            raise RuntimeError('GitHub state write failed/conflicted; stop before further delivery') from None

    def save(self, state):
        self._write(state)
