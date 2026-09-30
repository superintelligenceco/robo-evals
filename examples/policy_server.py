"""A standalone policy server that speaks the ``robo-evals/1`` HTTP protocol.

It uses only the Python standard library, so you can copy it next to any model
(LeRobot, OpenVLA, your own checkpoint) and replace ``act`` with a forward pass.

Start it, then point the harness at it::

    python examples/policy_server.py --port 8765
    robo-evals run --policy http://127.0.0.1:8765 --tasks reach
"""

from __future__ import annotations

import argparse
import contextlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


def act(observation: dict[str, Any]) -> list[float]:
    """Replace this with your model. Here: a proportional controller for ``reach``."""
    ee = observation["ee_pos"]
    goal = observation.get("goal_pos", ee)
    move = [max(-1.0, min(1.0, 30.0 * (g - e))) for g, e in zip(goal, ee, strict=True)]
    return [*move, -1.0]


class Handler(BaseHTTPRequestHandler):
    def _send(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/info":
            self._send(200, {"protocol": "robo-evals/1", "name": "example-server"})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        message = json.loads(self.rfile.read(length) or b"{}")
        if self.path == "/reset":
            # message has "task", "seed" and "instruction"; reset model state here.
            self._send(200, {})
        elif self.path == "/act":
            self._send(200, {"action": act(message["observation"])})
        else:
            self._send(404, {"error": "not found"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Serving on http://{args.host}:{args.port}")
    with contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


if __name__ == "__main__":
    main()
