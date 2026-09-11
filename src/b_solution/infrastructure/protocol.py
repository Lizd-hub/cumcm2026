"""Serial, idempotent, four-command client for the supplied simulator protocol."""
import json
import http.client
import math
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
import numpy as np


class HTTPTransport:
    def __init__(self, base_url='http://127.0.0.1:32026'):
        u = urlparse(base_url)
        if u.scheme != 'http' or u.hostname not in ('127.0.0.1', 'localhost') or u.path not in ('', '/'):
            raise ValueError('Only the documented local simulator endpoint is supported.')
        self.base_url = base_url.rstrip('/')

    def request(self, path, payload, deadline=math.inf):
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
        # The SAME bytes and request_id are retried after ambiguous transport errors.
        for attempt in range(3):
            available = deadline - time.monotonic()
            if available <= 0:
                raise TimeoutError('No real-time budget remains for an idempotent retry.')
            req = urllib.request.Request(self.base_url + path, data=data,
                                         headers={'Content-Type': 'application/json; charset=utf-8'}, method='POST')
            try:
                with urllib.request.urlopen(req, timeout=min(4., available)) as r:
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError as exc:
                if exc.code >= 500 and attempt < 2:
                    continue
                raise RuntimeError(f'HTTP {exc.code}; no new action was substituted.') from exc
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError,
                    http.client.HTTPException):
                if attempt == 2:
                    raise
        raise RuntimeError('Unreachable retry state')


class Session:
    def __init__(self, transport, robot_id='offline', log_path=None):
        self.transport, self.robot_id = transport, robot_id
        self.position = np.zeros(2)
        self.channel, self.virtual_time = 1, 0.
        self.deadline = math.inf
        self.max_virtual_duration = 360000.
        self.started = False
        self.log_path = Path(log_path) if log_path else None
        self.stats = {'distance_m': 0., 'measurements': 0, 'switches': 0, 'clear_success': 0, 'clear_failed': 0}
        self.records = []

    def action(self, path, position=None, channel=None):
        if path not in ('/enter', '/measure', '/clear', '/exit'):
            raise ValueError('Undocumented action rejected.')
        if path not in ('/enter', '/exit') and time.monotonic() > self.deadline - 15:
            raise TimeoutError('Safety deadline reached; completion must NOT be claimed.')
        payload = {'arena_id': 'default', 'robot_id': self.robot_id, 'request_id': uuid.uuid4().hex}
        if position is not None:
            p = np.asarray(position, float)
            if p.shape != (2,) or not np.all(np.isfinite(p)) or np.any(np.abs(p) > 2_000_000):
                raise ValueError('Invalid coordinate')
            if not isinstance(channel, (int, np.integer)) or not 1 <= channel <= 20:
                raise ValueError('Invalid channel')
            payload.update(position={'x': float(p[0]), 'y': float(p[1])}, channel=int(channel))
            worst_cost = np.linalg.norm(p - self.position) / 5 + 5 + int(path == '/measure' and channel != self.channel)
            if self.virtual_time + worst_cost >= self.max_virtual_duration:
                raise TimeoutError('Next action could exceed the virtual-time budget.')
        start = time.monotonic()
        if isinstance(self.transport, HTTPTransport):
            deadline = self.deadline - (2 if path not in ('/enter', '/exit') else 0)
            response = self.transport.request(path, payload, deadline=deadline)
        else:
            response = self.transport.request(path, payload)
        record = {'path': path, 'request': payload, 'response': response, 'latency_s': time.monotonic() - start}
        self.records.append(record)
        if self.log_path:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open('a', encoding='utf-8') as f:
                f.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')
        if not response.get('accepted'):
            # accepted=false reports vt=0; retain the last accepted time.
            raise RuntimeError('Request rejected; retain prior state and inspect the action log.')
        if path == '/enter':
            self.started = True
            self.deadline = start + float(response['remaining_real_duration_s'])
            self.max_virtual_duration = float(response.get('max_virtual_duration_s', 360000.))
        if position is not None:
            self.stats['distance_m'] += float(np.linalg.norm(p - self.position))
            self.position = p.copy()
        if path == '/measure':
            self.stats['measurements'] += 1
            self.stats['switches'] += int(channel != self.channel)
            self.channel = int(channel)
        if path == '/clear':
            self.stats['clear_success' if response['clear_result'] == 'success' else 'clear_failed'] += 1
            # /clear must NOT change the receiver channel.
        self.virtual_time = float(response['virtual_time_s'])
        return response

    def enter(self):
        return self.action('/enter')

    def exit(self):
        result = self.action('/exit')
        self.started = False
        return result
