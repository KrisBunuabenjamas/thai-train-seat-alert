import json
import unittest
from datetime import datetime, timezone

from train_alert.dticket import DTicketClient, parse_coaches, parse_trips

NOW = datetime(2026, 10, 9, tzinfo=timezone.utc)
TRIP = {'tripId': '609129', 'trainNo': '25', 'departureTime': '20:25',
        'arrivalTime': '05:39', 'departureDate': '2026-12-30T00:00:00+07:00'}
COACH = {'coachId': '148', 'coachDesc': 'ชั้น 2 ผู้โดยสารทั่วไป',
         'coachSeatType': '1', 'coachSeatTypeTh': 'นอน', 'availableSeatCount': 0}
CONFIG = {'origin': '1679', 'destination': '141', 'dates': ['2026-12-30']}


class ScriptedHTTP:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result.encode() if isinstance(result, str) else json.dumps(result).encode()


class ReaderTests(unittest.TestCase):
    def test_counts_must_be_real_nonnegative_integers(self):
        for bad in (None, -1, True, '2', 1.5):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                parse_coaches([dict(COACH, availableSeatCount=bad)], TRIP, '2026-12-30', CONFIG)

    def test_sleeper_filter_and_distinct_group_keys(self):
        rows = [COACH, dict(COACH, coachId='150', coachDesc='สตรีและเด็ก', availableSeatCount=2),
                dict(COACH, coachId='10', coachSeatType='2', coachSeatTypeTh='นั่ง')]
        result = parse_coaches(rows, TRIP, '2026-12-30', CONFIG)
        self.assertEqual([x.count for x in result], [0, 2])
        self.assertNotEqual(result[0].key, result[1].key)
        self.assertEqual(result[1].description, 'สตรีและเด็ก')

    def test_duplicate_coach_and_missing_count_fail_closed(self):
        with self.assertRaises(ValueError):
            parse_coaches([COACH, COACH], TRIP, '2026-12-30', CONFIG)
        bad = dict(COACH)
        del bad['availableSeatCount']
        with self.assertRaises(ValueError):
            parse_coaches([bad], TRIP, '2026-12-30', CONFIG)

    def test_wrong_date_or_missing_trip_information_rejected(self):
        with self.assertRaises(ValueError):
            parse_trips([TRIP], '2026-12-29')
        with self.assertRaises(ValueError):
            parse_trips([dict(TRIP, departureTime='bad')], '2026-12-30')

    def test_duplicate_train_numbers_cannot_collapse_observation_keys(self):
        with self.assertRaises(ValueError):
            parse_trips([TRIP, dict(TRIP, tripId='different')], '2026-12-30')

    def test_train_expiring_during_search_is_not_polled(self):
        http = ScriptedHTTP(['home', 'SmartUtil.hiddenParams.viewStateHolder = "initial";',
                             {'errorCode': 'S_SUCCESS', 'data': [TRIP]}])
        after_departure = datetime(2026, 12, 30, 14, tzinfo=timezone.utc)
        rows, errors = DTicketClient(http, clock=lambda: after_departure).check(CONFIG, NOW)
        self.assertEqual((rows, errors), ([], []))
        self.assertEqual(len(http.calls), 3)

    def test_verified_request_sequence_and_rotating_state(self):
        http = ScriptedHTTP(['home', 'SmartUtil.hiddenParams.viewStateHolder = "initial";',
            {'errorCode': 'S_SUCCESS', 'viewStateHolder': 'next', 'data': [TRIP]},
            {'errorCode': 'S_SUCCESS', 'data': {'results': [COACH]}}])
        observations, errors = DTicketClient(http).check(CONFIG, NOW)
        self.assertFalse(errors)
        self.assertEqual(observations[0].count, 0)
        form = http.calls[1][2]['form']
        self.assertEqual((form['lineId'], form['date-start']), ('0', '30/12/2026'))
        self.assertEqual(http.calls[2][2]['form']['provinceEndId'], '141')
        self.assertEqual(http.calls[3][2]['form']['viewStateHolder'], 'next')

    def test_error_response_never_becomes_zero_observation(self):
        http = ScriptedHTTP(['home', 'SmartUtil.hiddenParams.viewStateHolder = "initial";',
                             {'errorCode': 'E_INVALID_SESSION', 'data': []}])
        observations, errors = DTicketClient(http).check(CONFIG, NOW)
        self.assertEqual(observations, [])
        self.assertTrue(errors)

    def test_expired_date_does_not_make_network_calls(self):
        http = ScriptedHTTP([])
        observations, errors = DTicketClient(http).check(CONFIG, datetime(2026, 12, 31, tzinfo=timezone.utc))
        self.assertEqual((observations, errors, http.calls), ([], [], []))

    def test_departed_train_not_polled(self):
        http = ScriptedHTTP(['home', 'SmartUtil.hiddenParams.viewStateHolder = "initial";',
                             {'errorCode': 'S_SUCCESS', 'data': [TRIP]}])
        observations, errors = DTicketClient(http).check(CONFIG, datetime(2026, 12, 30, 14, tzinfo=timezone.utc))
        self.assertEqual((observations, errors), ([], []))
        self.assertEqual(len(http.calls), 3)


if __name__ == '__main__':
    unittest.main()
