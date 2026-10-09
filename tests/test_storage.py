import base64
import json
import tempfile
import unittest
from pathlib import Path
from train_alert.http import HttpError
from train_alert.storage import LocalStore, GitHubStore
from train_alert.state import fresh_state
from test_dticket import ScriptedHTTP
from test_state import CONFIG


class StorageTests(unittest.TestCase):
    def test_missing_local_state_requires_explicit_initialize(self):
        with tempfile.TemporaryDirectory() as directory:
            store = LocalStore(Path(directory) / 'state.json')
            with self.assertRaises(RuntimeError):
                store.load()
            store.initialize(fresh_state(CONFIG))
            self.assertEqual(store.load()['entries'], {})
            with self.assertRaises(RuntimeError):
                store.initialize(fresh_state(CONFIG))

    def test_remote_write_uses_loaded_sha_and_conflict_aborts(self):
        content = base64.b64encode(json.dumps(fresh_state(CONFIG)).encode()).decode()
        http = ScriptedHTTP([{'content': content, 'sha': 'old'}, HttpError(409)])
        store = GitHubStore('owner/repo', 'token', http=http)
        state = store.load()
        with self.assertRaises(RuntimeError):
            store.save(state)
        self.assertEqual(http.calls[-1][2]['json_body']['sha'], 'old')
        self.assertEqual(http.calls[-1][2]['json_body']['branch'], 'monitor-state')

    def test_acknowledgement_updates_sha_for_next_write(self):
        content = base64.b64encode(json.dumps(fresh_state(CONFIG)).encode()).decode()
        http = ScriptedHTTP([{'content': content, 'sha': 'old'}, {'content': {'sha': 'new'}},
                             {'content': {'sha': 'latest'}}])
        store = GitHubStore('owner/repo', 'token', http=http)
        state = store.load()
        store.save(state)
        store.save(state)
        self.assertEqual(http.calls[-1][2]['json_body']['sha'], 'new')


if __name__ == '__main__':
    unittest.main()
