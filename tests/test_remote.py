from __future__ import annotations

import subprocess
import sys
import threading
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from robo_evals import evaluate, load_policy
from robo_evals.remote import (
    HTTPPolicy,
    RemotePolicyError,
    decode,
    encode,
    make_http_server,
    serve_websocket,
)

ROOT = Path(__file__).resolve().parents[1]


def test_encode_decode_round_trip() -> None:
    image = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
    obs = {"ee_pos": np.array([0.1, 0.2, 0.3]), "image": image, "instruction": "go", "n": 3}
    wire = encode(obs)
    assert wire["ee_pos"] == [0.1, 0.2, 0.3]
    assert set(wire["image"]) == {"__ndarray__", "dtype", "shape"}
    back = decode(wire)
    np.testing.assert_array_equal(back["image"], image)
    assert back["image"].dtype == np.uint8
    np.testing.assert_allclose(back["ee_pos"], obs["ee_pos"])
    assert back["instruction"] == "go"


@pytest.fixture
def http_server() -> Iterator[str]:
    server = make_http_server(load_policy("scripted"), "127.0.0.1", 0, "oracle")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def test_http_info(http_server: str) -> None:
    import json

    with urllib.request.urlopen(http_server + "/info") as r:
        assert json.loads(r.read()) == {
            "protocol": "robo-evals/1",
            "name": "oracle",
        }


def test_remote_scripted_matches_local(http_server: str) -> None:
    kwargs: dict[str, Any] = {"tasks": ["reach", "push"], "episodes": 2, "seed": 4}
    remote = evaluate(load_policy(http_server), **kwargs)
    local = evaluate(load_policy("scripted"), **kwargs)
    assert [e.steps for t in remote.tasks for e in t.episodes] == [
        e.steps for t in local.tasks for e in t.episodes
    ]
    assert remote.tasks[0].successes == 2


def test_http_server_reports_policy_errors(http_server: str) -> None:
    client = HTTPPolicy(http_server)
    client.reset("not-a-task", 0)
    with pytest.raises(RemotePolicyError, match="HTTP 400"):
        client({"ee_pos": np.zeros(3)})


def test_http_unreachable() -> None:
    client = HTTPPolicy("http://127.0.0.1:9", timeout=2)
    with pytest.raises(RemotePolicyError):
        client({"ee_pos": np.zeros(3)})


def test_websocket_round_trip() -> None:
    pytest.importorskip("websockets")
    server = serve_websocket(load_policy("scripted"), "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.socket.getsockname()[1]
        policy = load_policy(f"ws://127.0.0.1:{port}")
        try:
            r = evaluate(policy, tasks=["reach"], episodes=2, seed=0)
            assert r.tasks[0].successes == 2
            policy.reset("not-a-task", 0)  # type: ignore[attr-defined]
            with pytest.raises(RemotePolicyError, match="no controller"):
                policy({"ee_pos": np.zeros(3)})
        finally:
            policy.close()  # type: ignore[attr-defined]
    finally:
        server.shutdown()


def test_example_server_speaks_the_protocol() -> None:
    import socket

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "examples" / "policy_server.py"), "--port", str(port)],
        stdout=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                urllib.request.urlopen(url + "/info", timeout=1).close()
                break
            except OSError:
                time.sleep(0.05)
        r = evaluate(load_policy(url), tasks=["reach"], episodes=3, seed=0)
        assert r.tasks[0].successes == 3
    finally:
        proc.terminate()
        proc.wait(timeout=10)
