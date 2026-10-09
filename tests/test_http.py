import io
import unittest
from http.client import IncompleteRead
from unittest.mock import patch
from urllib.error import HTTPError

from train_alert.http import HTTP, HttpError


class Opener:
    def __init__(self, replies):
        self.replies = list(replies)
        self.count = 0

    def open(self, request, timeout):
        self.count += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply)


class HTTPTests(unittest.TestCase):
    def test_rate_limit_obeys_retry_after(self):
        http = HTTP()
        http.opener = Opener([HTTPError('https://example.org/SECRET', 429, 'limit', {'Retry-After': '7'}, None), b'ok'])
        with patch('train_alert.http.time.sleep') as sleep:
            self.assertEqual(http.request('GET', 'https://example.org'), b'ok')
            sleep.assert_called_once_with(7)

    def test_long_retry_after_is_deferred_without_early_retry(self):
        http = HTTP()
        http.opener = Opener([HTTPError('https://example.org/SECRET', 429, 'limit', {'Retry-After': '120'}, None)])
        with self.assertRaises(HttpError) as error:
            http.request('GET', 'https://example.org')
        self.assertEqual(http.opener.count, 1)
        self.assertNotIn('SECRET', str(error.exception))

    def test_truncated_http_response_is_classified_as_network_error(self):
        http = HTTP(attempts=1)
        http.opener = Opener([IncompleteRead(b'partial', 20)])
        with self.assertRaises(HttpError):
            http.request('GET', 'https://example.org')


if __name__ == '__main__':
    unittest.main()
