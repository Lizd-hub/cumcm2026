"""HTTP contract test for the user-started official simulator adapter.

The real simulator is deliberately not contacted by the default test suite:
entering a formal session is an externally visible action.  This test uses a
local HTTP server that implements the documented four-endpoint response
contract, so serialization, state accounting, and clear/channel semantics are
still exercised end to end.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from threading import Thread

import pytest

from b_solution.protocol import HTTPTransport, Session


class _OfficialContractHandler(BaseHTTPRequestHandler):
    requests = []
    virtual_time = 0.0

    def do_POST(self):  # noqa: N802 - stdlib handler API
        size = int(self.headers["Content-Length"])
        payload = json.loads(self.rfile.read(size))
        self.__class__.requests.append((self.path, payload))
        if self.path == "/enter":
            body = {
                "accepted": True,
                "virtual_time_s": 0.0,
                "remaining_real_duration_s": 1200.0,
            }
        elif self.path == "/measure":
            self.__class__.virtual_time = 105.0
            body = {
                "accepted": True,
                "virtual_time_s": self.__class__.virtual_time,
                "measure_result": "no_signal",
            }
        elif self.path == "/clear":
            self.__class__.virtual_time = 108.0
            body = {
                "accepted": True,
                "virtual_time_s": self.__class__.virtual_time,
                "clear_result": "no_target_in_range",
            }
        elif self.path == "/exit":
            body = {"accepted": True, "virtual_time_s": self.__class__.virtual_time}
        else:
            self.send_error(404)
            return
        raw = json.dumps(body).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        return


def test_official_http_contract_round_trip():
    _OfficialContractHandler.requests = []
    _OfficialContractHandler.virtual_time = 0.0
    server = ThreadingHTTPServer(("127.0.0.1", 0), _OfficialContractHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        transport = HTTPTransport(f"http://127.0.0.1:{server.server_port}")
        session = Session(transport, robot_id="practice-team")
        session.enter()
        session.action("/measure", (300, 400), 1)
        session.action("/clear", (300, 0), 1)
        session.exit()
    finally:
        server.shutdown()
        thread.join(timeout=2)
        server.server_close()

    assert [path for path, _ in _OfficialContractHandler.requests] == [
        "/enter", "/measure", "/clear", "/exit"
    ]
    assert all(payload["arena_id"] == "default" for _, payload in _OfficialContractHandler.requests)
    assert all(payload["robot_id"] == "practice-team" for _, payload in _OfficialContractHandler.requests)
    assert session.virtual_time == 108.0
    assert session.channel == 1
    assert session.stats["clear_failed"] == 1


@pytest.mark.official
@pytest.mark.skipif(
    not (os.getenv("CUMCM_OFFICIAL_BASE_URL") and os.getenv("CUMCM_OFFICIAL_TEAM_ID")),
    reason="set CUMCM_OFFICIAL_BASE_URL and CUMCM_OFFICIAL_TEAM_ID to opt in",
)
def test_live_official_simulator_smoke():
    """Enter and leave the UI-selected session without consuming a target action."""

    session = Session(
        HTTPTransport(os.environ["CUMCM_OFFICIAL_BASE_URL"]),
        robot_id=os.environ["CUMCM_OFFICIAL_TEAM_ID"],
    )
    session.enter()
    try:
        assert session.started
    finally:
        session.exit()
    assert not session.started
