import copy
import unittest
from datetime import datetime, timezone
from train_alert.dticket import Observation
from train_alert.state import fresh_state, reconcile, pending_alerts, acknowledge, validate_state

CONFIG = {'origin': '1679', 'destination': '141', 'dates': ['2026-12-29', '2026-12-30']}
NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)


def obs(count):
    return Observation('2026-12-30|1679|141|25|148', '2026-12-30', '25', '148',
                       'ชั้น 2 ผู้โดยสารทั่วไป', count, '2026-12-30T20:25:00+07:00', '05:39')


class StateTests(unittest.TestCase):
    def setUp(self):
        self.state = fresh_state(CONFIG)

    def step(self, count):
        rows = [obs(count)]
        reconcile(self.state, rows, [], NOW)
        return pending_alerts(self.state, rows, NOW)

    def test_initial_full_is_silent_and_available_alerts_once(self):
        self.assertEqual(self.step(0), [])
        events = self.step(1)
        self.assertEqual(len(events), 1)
        acknowledge(self.state, events[0])
        self.assertEqual(self.step(3), [])

    def test_first_check_available_and_second_release_notify(self):
        first = self.step(1)[0]
        acknowledge(self.state, first)
        self.assertEqual(self.step(0), [])
        second = self.step(1)[0]
        self.assertNotEqual(first['id'], second['id'])

    def test_error_does_not_reset_last_known_available(self):
        event = self.step(1)[0]
        acknowledge(self.state, event)
        reconcile(self.state, [], ['network error'], NOW)
        self.assertEqual(self.state['entries'][obs(1).key]['count'], 1)
        self.assertEqual(self.step(1), [])

    def test_missing_coach_is_error_and_not_full(self):
        self.step(1)
        reconcile(self.state, [], [], NOW)
        self.assertEqual(self.state['health']['failures'], 1)
        self.assertEqual(self.state['entries'][obs(1).key]['count'], 1)

    def test_pending_requires_fresh_availability_and_drops_when_full(self):
        self.step(1)
        self.assertEqual(pending_alerts(self.state, [], NOW), [])
        self.assertEqual(len(self.step(2)), 1)
        self.assertEqual(self.step(0), [])
        self.assertEqual(self.state['pending'], {})

    def test_expired_pending_never_sends(self):
        self.step(1)
        later = datetime(2026, 12, 31, tzinfo=timezone.utc)
        reconcile(self.state, [], [], later)
        self.assertEqual(pending_alerts(self.state, [obs(1)], later), [])

    def test_health_alert_after_three_failures_then_one_recovery(self):
        for _ in range(2):
            reconcile(self.state, [], ['network'], NOW)
            self.assertEqual(pending_alerts(self.state, [], NOW), [])
        reconcile(self.state, [], ['network'], NOW)
        event = pending_alerts(self.state, [], NOW)[0]
        self.assertEqual(event['kind'], 'health_failure')
        acknowledge(self.state, event)
        reconcile(self.state, [], ['network'], NOW)
        self.assertEqual(pending_alerts(self.state, [], NOW), [])
        reconcile(self.state, [obs(0)], [], NOW)
        recovery = pending_alerts(self.state, [obs(0)], NOW)[0]
        self.assertEqual(recovery['kind'], 'health_recovery')
        acknowledge(self.state, recovery)
        self.assertEqual(self.step(0), [])

    def test_corrupt_state_and_config_change_rejected(self):
        self.step(0)
        for field, bad in [('count', None), ('cycle', -1), ('departure_at', 'bad')]:
            broken = copy.deepcopy(self.state)
            broken['entries'][obs(0).key][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_state(broken, CONFIG)
        with self.assertRaises(ValueError):
            validate_state(self.state, dict(CONFIG, destination='1'))
        with self.assertRaises(ValueError):
            validate_state({}, CONFIG)


if __name__ == '__main__':
    unittest.main()
