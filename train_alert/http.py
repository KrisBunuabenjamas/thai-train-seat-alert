"""Bounded HTTP transport; exception messages deliberately exclude URLs/tokens."""
import http.cookiejar
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone


class HttpError(RuntimeError):
    def __init__(self, status=0):
        self.status = status
        super().__init__(f'HTTP {status}' if status else 'Network request failed')


class HTTP:
    def __init__(self, attempts=3, timeout=25):
        self.attempts, self.timeout = attempts, timeout
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, method, url, *, form=None, json_body=None, headers=None):
        body = None
        hdr = {'User-Agent': 'ThaiTrainSeatAlert/1.0', **(headers or {})}
        if form is not None:
            body = urllib.parse.urlencode(form).encode()
            hdr['Content-Type'] = 'application/x-www-form-urlencoded; charset=utf-8'
        elif json_body is not None:
            body = json.dumps(json_body, ensure_ascii=False).encode()
            hdr['Content-Type'] = 'application/json'
        for attempt in range(self.attempts):
            delay = 2 ** attempt
            try:
                req = urllib.request.Request(url, body, hdr, method=method)
                with self.opener.open(req, timeout=self.timeout) as response:
                    return response.read()
            except urllib.error.HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get('Retry-After')
                exc.close()
                if status not in (429, 500, 502, 503, 504):
                    raise HttpError(status) from None
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        try:
                            delay = max(delay, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                        except (ValueError, TypeError):
                            raise HttpError(status) from None
                if delay > 60 or attempt == self.attempts - 1:
                    raise HttpError(status) from None
            except (urllib.error.URLError, TimeoutError, OSError):
                if attempt == self.attempts - 1:
                    raise HttpError() from None
            time.sleep(delay)


def decode_json(raw):
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError):
        raise ValueError('Invalid JSON response') from None
