"""Remote policies over HTTP or WebSocket.

Protocol ``robo-evals/1``. Every message is a JSON object. Numeric arrays with
one dimension travel as JSON lists. Arrays with two or more dimensions (camera
images) travel as ``{"__ndarray__": <base64>, "dtype": "uint8", "shape": [...]}``
holding the raw C-order bytes.

HTTP:

* ``GET  /info``  returns ``{"protocol": "robo-evals/1", "name": "..."}``.
* ``POST /reset`` with ``{"task": str, "seed": int, "instruction": str}``.
* ``POST /act``   with ``{"observation": {...}}`` returns ``{"action": [4 floats]}``.

WebSocket: send ``{"type": "reset", ...}`` or ``{"type": "act", "observation": ...}``
and receive one reply per message, ``{"type": "ok"}`` or
``{"type": "action", "action": [...]}``. Errors come back as
``{"type": "error", "message": str}``.
"""

from __future__ import annotations

import base64
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import numpy as np

from robo_evals.policy import Policy, reset_policy

PROTOCOL = "robo-evals/1"


class RemotePolicyError(RuntimeError):
    """Raised when a remote policy server fails or returns a malformed reply."""


def encode(value: Any) -> Any:
    """Converts observations into JSON-safe values."""
    if isinstance(value, np.ndarray):
        if value.ndim <= 1:
            return value.tolist()
        arr = np.ascontiguousarray(value)
        return {
            "__ndarray__": base64.b64encode(arr.tobytes()).decode("ascii"),
            "dtype": str(arr.dtype),
            "shape": list(arr.shape),
        }
    if isinstance(value, Mapping):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, list | tuple):
        return [encode(v) for v in value]
    return value


def decode(value: Any) -> Any:
    """Inverts ``encode``. One-dimensional lists become float arrays."""
    if isinstance(value, Mapping):
        if "__ndarray__" in value:
            raw = base64.b64decode(value["__ndarray__"])
            return np.frombuffer(raw, dtype=np.dtype(value["dtype"])).reshape(value["shape"]).copy()
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list) and all(isinstance(v, int | float) for v in value):
        return np.asarray(value, dtype=np.float64)
    return value


def _parse_action(reply: Mapping[str, Any]) -> np.ndarray:
    try:
        action = np.asarray(reply["action"], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise RemotePolicyError(f"malformed action reply: {reply!r}") from exc
    return action


class HTTPPolicy:
    """Client for a policy served over HTTP."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout

    def _post(self, path: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.url + path, data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                result: dict[str, Any] = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")
            raise RemotePolicyError(f"{path} failed with HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RemotePolicyError(f"{path} failed: {exc}") from exc
        return result

    def reset(self, task: str, seed: int) -> None:
        from robo_evals.tasks import TASKS

        instruction = TASKS[task].instruction if task in TASKS else ""
        self._post("/reset", {"task": task, "seed": seed, "instruction": instruction})

    def __call__(self, obs: Mapping[str, Any]) -> np.ndarray:
        return _parse_action(self._post("/act", {"observation": encode(obs)}))


class WebSocketPolicy:
    """Client for a policy served over WebSocket. Needs ``robo-evals[ws]``."""

    def __init__(self, url: str, timeout: float = 30.0) -> None:
        try:
            from websockets.sync.client import connect as ws_connect
        except ImportError as exc:
            raise RemotePolicyError(
                "WebSocket policies need the 'websockets' package: pip install 'robo-evals[ws]'"
            ) from exc
        self.timeout = timeout
        # Enter the connection's context explicitly; newer websockets releases
        # deprecate using a sync connection outside of one.
        self._ws = ws_connect(url, open_timeout=timeout, max_size=None).__enter__()

    def _call(self, message: Mapping[str, Any]) -> dict[str, Any]:
        self._ws.send(json.dumps(message))
        reply: dict[str, Any] = json.loads(self._ws.recv(timeout=self.timeout))
        if reply.get("type") == "error":
            raise RemotePolicyError(str(reply.get("message")))
        return reply

    def reset(self, task: str, seed: int) -> None:
        from robo_evals.tasks import TASKS

        instruction = TASKS[task].instruction if task in TASKS else ""
        self._call({"type": "reset", "task": task, "seed": seed, "instruction": instruction})

    def __call__(self, obs: Mapping[str, Any]) -> np.ndarray:
        return _parse_action(self._call({"type": "act", "observation": encode(obs)}))

    def close(self) -> None:
        self._ws.__exit__(None, None, None)


def connect(url: str, timeout: float = 30.0) -> HTTPPolicy | WebSocketPolicy:
    """Returns a client for ``url`` based on its scheme."""
    if url.startswith(("ws://", "wss://")):
        return WebSocketPolicy(url, timeout)
    return HTTPPolicy(url, timeout)


# -- servers ------------------------------------------------------------------------


class _PolicyHandle:
    """Serializes access to one policy instance across server threads."""

    def __init__(self, policy: Policy, name: str) -> None:
        self.policy = policy
        self.name = name
        self.lock = threading.Lock()

    def handle(self, message: Mapping[str, Any]) -> dict[str, Any]:
        kind = message.get("type")
        with self.lock:
            if kind == "reset":
                reset_policy(self.policy, str(message["task"]), int(message["seed"]))
                return {"type": "ok"}
            if kind == "act":
                obs = decode(message["observation"])
                action = np.asarray(self.policy(obs), dtype=np.float64).reshape(-1)
                return {"type": "action", "action": action.tolist()}
            if kind == "info":
                return {"type": "info", "protocol": PROTOCOL, "name": self.name}
        raise ValueError(f"unknown message type {kind!r}")


def make_http_server(
    policy: Policy, host: str = "127.0.0.1", port: int = 8765, name: str = "policy"
) -> ThreadingHTTPServer:
    """Builds (but does not start) an HTTP server that serves ``policy``."""
    handle = _PolicyHandle(policy, name)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _reply(self, status: int, payload: Mapping[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path == "/info":
                reply = handle.handle({"type": "info"})
                reply.pop("type", None)
                self._reply(200, reply)
            else:
                self._reply(404, {"error": f"no route {self.path}"})

        def do_POST(self) -> None:
            routes = {"/reset": "reset", "/act": "act"}
            if self.path not in routes:
                self._reply(404, {"error": f"no route {self.path}"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                message = dict(json.loads(self.rfile.read(length)))
                message["type"] = routes[self.path]
                reply = handle.handle(message)
            except Exception as exc:
                self._reply(400, {"error": f"{type(exc).__name__}: {exc}"})
                return
            reply.pop("type", None)
            self._reply(200, reply)

    return ThreadingHTTPServer((host, port), Handler)


def serve_websocket(
    policy: Policy, host: str = "127.0.0.1", port: int = 8765, name: str = "policy"
) -> Any:
    """Builds a WebSocket server for ``policy``. Call ``serve_forever()`` on the result."""
    try:
        from websockets.sync.server import serve
    except ImportError as exc:
        raise RemotePolicyError(
            "WebSocket serving needs the 'websockets' package: pip install 'robo-evals[ws]'"
        ) from exc
    handle = _PolicyHandle(policy, name)

    def handler(ws: Any) -> None:
        for raw in ws:
            try:
                reply = handle.handle(json.loads(raw))
            except Exception as exc:
                reply = {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
            ws.send(json.dumps(reply))

    return serve(handler, host, port, max_size=None)
