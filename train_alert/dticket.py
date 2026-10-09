"""Verified anonymous D-Ticket booking search endpoints (2026-10-09)."""
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
import re
import time as monotonic_time

from .http import HTTP, HttpError, decode_json

BASE = 'https://dticket.railway.co.th/DTicketPublicWeb/'
BANGKOK = timezone(timedelta(hours=7))


@dataclass(frozen=True)
class Observation:
    key: str
    date: str
    train: str
    coach: str
    description: str
    count: int
    departure_at: str
    arrival_time: str

    def to_dict(self):
        return asdict(self)


def required_string(obj, key):
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'Missing/invalid {key}')
    return value


def departure(trip, day):
    clock = required_string(trip, 'departureTime')
    if not re.fullmatch(r'\d{2}:\d{2}', clock):
        raise ValueError('Invalid departure time')
    return datetime.combine(date.fromisoformat(day), time.fromisoformat(clock), BANGKOK)


def parse_trips(rows, day):
    if not isinstance(rows, list) or not rows:
        raise ValueError('No verified trips returned')
    seen, train_numbers = set(), set()
    for trip in rows:
        if not isinstance(trip, dict):
            raise ValueError('Invalid trip record')
        for field in ('tripId', 'trainNo', 'arrivalTime', 'departureDate'):
            required_string(trip, field)
        if trip['departureDate'][:10] != day or trip['tripId'] in seen or trip['trainNo'] in train_numbers:
            raise ValueError('Wrong date or duplicate trip')
        departure(trip, day)
        seen.add(trip['tripId'])
        train_numbers.add(trip['trainNo'])
    return rows


def parse_coaches(rows, trip, day, config):
    if not isinstance(rows, list) or not rows:
        raise ValueError('No verified coaches returned')
    observations, seen = [], set()
    for coach in rows:
        if not isinstance(coach, dict):
            raise ValueError('Invalid coach record')
        cid = required_string(coach, 'coachId')
        if cid in seen:
            raise ValueError('Duplicate coach')
        seen.add(cid)
        kind = required_string(coach, 'coachSeatTypeTh')
        if kind not in ('นอน', 'นั่ง'):
            raise ValueError('Unknown seat type')
        if kind != 'นอน':
            continue
        if coach.get('coachSeatType') != '1':
            raise ValueError('Inconsistent sleeper classification')
        count = coach.get('availableSeatCount')
        if type(count) is not int or count < 0:
            raise ValueError('Invalid availableSeatCount')
        observations.append(Observation(
            key='|'.join((day, config['origin'], config['destination'], trip['trainNo'], cid)),
            date=day, train=trip['trainNo'], coach=cid,
            description=required_string(coach, 'coachDesc'), count=count,
            departure_at=departure(trip, day).isoformat(), arrival_time=trip['arrivalTime']))
    return observations


class DTicketClient:
    def __init__(self, http=None, clock=None):
        self.http = http or HTTP()
        self.clock = clock
        self.page_state = ''

    def api(self, path, fields):
        result = decode_json(self.http.request('POST', BASE + path,
            form={**fields, 'viewStateHolder': self.page_state},
            headers={'X-Requested-With': 'XMLHttpRequest'}))
        if not isinstance(result, dict) or result.get('errorCode') != 'S_SUCCESS':
            raise ValueError('D-Ticket did not return S_SUCCESS')
        if isinstance(result.get('viewStateHolder'), str):
            self.page_state = result['viewStateHolder']
        return result.get('data')

    def check(self, config, now):
        started = monotonic_time.monotonic()
        clock = self.clock or (lambda: now + timedelta(seconds=monotonic_time.monotonic() - started))
        observations, errors = [], []
        for day in config['dates']:
            if date.fromisoformat(day) < now.astimezone(BANGKOK).date():
                continue
            try:
                self.http.request('GET', BASE + 'home/Home')
                d = date.fromisoformat(day)
                search_date = d.strftime('%d/%m/%Y')
                page = self.http.request('POST', BASE + 'booking/booking', form={
                    'provinceStart': config['origin'], 'provinceEnd': config['destination'],
                    'date-start': search_date, 'date-start-picker': f'{d.day:02}/{d.month:02}/{d.year + 543}',
                    'date-end': '', 'date-end-picker': '', 'seatperson': '1', 'tripType': '1', 'lineId': '0'})
                match = re.search(r'SmartUtil\.hiddenParams\.viewStateHolder\s*=\s*"([^"]+)"', page.decode('utf-8'))
                if not match:
                    raise ValueError('Anonymous booking page state missing')
                self.page_state = match.group(1)
                trips = parse_trips(self.api('booking/booking/getTrip', {
                    'tripType': '1', 'provinceStartId': config['origin'],
                    'provinceEndId': config['destination'], 'dateStart': search_date, 'dateEnd': ''}), day)
                for trip in trips:
                    if departure(trip, day) <= clock():
                        continue
                    try:
                        data = self.api('booking/booking/getTrainCoach', {
                            'tripId': trip['tripId'], 'provinceStartId': config['origin'],
                            'provinceEndId': config['destination']})
                        if not isinstance(data, dict):
                            raise ValueError('Invalid coach response')
                        observations.extend(parse_coaches(data.get('results'), trip, day, config))
                    except (ValueError, HttpError) as exc:
                        errors.append(f'{day} train {trip["trainNo"]}: {exc}')
            except (ValueError, HttpError) as exc:
                errors.append(f'{day}: {exc}')
        return observations, errors
