import unittest
from train_alert.discord import Discord, payload
from train_alert.http import HttpError
from test_dticket import ScriptedHTTP
from test_state import obs


class DeliveryTests(unittest.TestCase):
    def test_alert_contains_actionable_route_seat_and_no_mass_mentions(self):
        p = payload({'kind': 'availability', 'observation': obs(2).to_dict(),
                     'checked_at': '2026-10-09T18:14:00+07:00'})
        self.assertIn('2', p['content'])
        self.assertIn('2026-12-30', p['content'])
        self.assertIn('25', p['content'])
        self.assertIn('dticket.railway.co.th', p['content'])
        self.assertEqual(p['allowed_mentions'], {'parse': []})

    def test_webhook_failure_is_redacted(self):
        sender = Discord('https://discord.com/api/webhooks/123/SECRET', ScriptedHTTP([HttpError(429)]))
        with self.assertRaisesRegex(RuntimeError, '^Discord delivery failed') as error:
            sender.send({'kind': 'test'})
        self.assertNotIn('SECRET', str(error.exception))

    def test_webhook_rejects_other_destinations(self):
        for url in ('http://discord.com/api/webhooks/1/x', 'https://example.com/api/webhooks/1/x', ''):
            with self.subTest(url=url), self.assertRaises(ValueError):
                Discord(url)


if __name__ == '__main__':
    unittest.main()
