import copy
import unittest
from datetime import datetime, timezone
from train_alert.runner import run_once
from train_alert.state import fresh_state
from test_state import CONFIG, NOW, obs


class MemoryStore:
    def __init__(self):
        self.state = fresh_state(CONFIG)
        self.saved = []
        self.fail = False

    def load(self):
        return copy.deepcopy(self.state)

    def save(self, state):
        if self.fail:
            raise RuntimeError('state conflict')
        self.state = copy.deepcopy(state)
        self.saved.append(copy.deepcopy(state))


class Client:
    def __init__(self, count=1, errors=None):
        self.count, self.errors = count, errors or []

    def check(self, config, now):
        return ([obs(self.count)] if self.count is not None else []), self.errors


class Sender:
    def __init__(self, store, fail=False):
        self.store, self.fail, self.events = store, fail, []

    def send(self, event):
        if event['id'] not in self.store.state['pending']:
            raise AssertionError('Event was not durably saved before delivery')
        if self.fail:
            raise RuntimeError('delivery failed')
        self.events.append(event)


class RunTests(unittest.TestCase):
    def test_event_durably_saved_before_send_and_acknowledged_after(self):
        store = MemoryStore()
        sender = Sender(store)
        result = run_once(Client(), store, sender, CONFIG, NOW)
        self.assertEqual(result['sent'], 1)
        self.assertEqual(len(store.saved[0]['pending']), 1)
        self.assertEqual(store.state['pending'], {})
        self.assertEqual(run_once(Client(), store, sender, CONFIG, NOW)['sent'], 0)

    def test_failed_delivery_retained_and_retried_when_fresh(self):
        store = MemoryStore()
        result = run_once(Client(), store, Sender(store, fail=True), CONFIG, NOW)
        self.assertTrue(result['errors'])
        self.assertEqual(len(store.state['pending']), 1)
        sender = Sender(store)
        self.assertEqual(run_once(Client(0), store, sender, CONFIG, NOW)['sent'], 0)
        self.assertEqual(store.state['pending'], {})

    def test_state_conflict_prevents_delivery(self):
        store = MemoryStore()
        store.fail = True
        sender = Sender(store)
        with self.assertRaises(RuntimeError):
            run_once(Client(), store, sender, CONFIG, NOW)
        self.assertEqual(sender.events, [])

    def test_remote_failure_returns_nonzero_health_without_seat_alert(self):
        store = MemoryStore()
        sender = Sender(store)
        for _ in range(3):
            result = run_once(Client(None, ['network']), store, sender, CONFIG, NOW)
        self.assertTrue(result['errors'])
        self.assertEqual([x['kind'] for x in sender.events], ['health_failure'])

    def test_departure_crossed_during_state_write_prevents_send(self):
        store = MemoryStore()
        sender = Sender(store)
        before = datetime(2026, 12, 30, 13, 24, tzinfo=timezone.utc)
        after = datetime(2026, 12, 30, 13, 26, tzinfo=timezone.utc)
        def clock():
            return after if store.saved else before
        result = run_once(Client(), store, sender, CONFIG, before, clock=clock)
        self.assertEqual(result['sent'], 0)
        self.assertEqual(sender.events, [])


if __name__ == '__main__':
    unittest.main()
