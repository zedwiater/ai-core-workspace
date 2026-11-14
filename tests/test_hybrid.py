"""core.hybrid — chain, briefs, queue/drain, parent ingest.

The two-instance tests run a REAL RingService with dict-backed
memory handlers on an ephemeral port and move briefs over real
TCP through core.protocol.mcp_call — the same transport the app
uses. Hybrid self-pair is the same shape against one service.
"""
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path

from tests import __init__ as _path  # noqa: F401
from core import hybrid
from core.ring_service import RingService

SNAP = {"aligned": True, "up": ["files"], "down": [],
        "mismatches": [], "beat": "dwell", "processes": 42}


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_memory_service(port):
    store = {}

    def get(req):
        return {"status": "ok", "value": store.get(req["key"])}

    def set_(req):
        store[req["key"]] = req["value"]
        return {"status": "ok"}

    def list_(req):
        return {"status": "ok",
                "entries": [{"key": k, "ts": ""} for k in store]}

    svc = RingService("memory", "state", port,
                      {"ping": lambda r: {"status": "pong"},
                       "get": get, "set": set_, "list": list_})
    threading.Thread(target=svc.serve, daemon=True).start()
    for _ in range(50):
        try:
            with socket.create_connection(("127.0.0.1", port),
                                          timeout=0.2):
                break
        except OSError:
            time.sleep(0.05)
    return store


def _runtime(td, port, secret="s3cret"):
    return hybrid.DaughterRuntime(
        "pi-lab", hybrid.ChainStore(Path(td) / "chain.json"),
        hybrid.BriefQueue(Path(td) / "queue.jsonl"),
        "127.0.0.1", parent_port=port, pair_secret=secret)


class TestChain(unittest.TestCase):
    def test_append_and_verify(self):
        chain = []
        for i in range(3):
            chain.append(hybrid.chain_append(
                chain, {"ts": f"t{i}", "n": i}))
        ok, bad = hybrid.verify_chain(chain)
        self.assertTrue(ok)
        self.assertIsNone(bad)
        self.assertEqual(chain[0]["prev"], hybrid.GENESIS)

    def test_tamper_breaks_at_seq(self):
        chain = []
        for i in range(3):
            chain.append(hybrid.chain_append(
                chain, {"ts": f"t{i}", "n": i}))
        chain[1]["body"]["n"] = 999
        ok, bad = hybrid.verify_chain(chain)
        self.assertFalse(ok)
        self.assertEqual(bad, 2)

    def test_store_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            store = hybrid.ChainStore(Path(td) / "c.json")
            e = store.append({"ts": "t0"})
            again = hybrid.ChainStore(Path(td) / "c.json")
            self.assertEqual(again.head(), e["hash"])
            ok, _ = hybrid.verify_chain(again.chain)
            self.assertTrue(ok)


class TestQueue(unittest.TestCase):
    def test_drain_in_order_stops_at_failure(self):
        with tempfile.TemporaryDirectory() as td:
            q = hybrid.BriefQueue(Path(td) / "q.jsonl")
            for n in (1, 2, 3):
                q.enqueue({"n": n})
            seen = []
            sent = q.drain(
                lambda p: seen.append(p["n"]) or p["n"] < 3)
            self.assertEqual(seen, [1, 2, 3])
            self.assertEqual(sent, 2)
            self.assertEqual(q.pending(), 1)


class TestTwoInstances(unittest.TestCase):
    def test_daughter_to_parent_over_real_wire(self):
        port = _free_port()
        _start_memory_service(port)
        with tempfile.TemporaryDirectory() as td:
            rt = _runtime(td, port)
            result = rt.beat(SNAP)
            self.assertTrue(result["sent"])
            daughters = hybrid.read_daughters(
                port=port, pair_secret="s3cret", stale_minutes=45)
            self.assertIn("pi-lab", daughters)
            d = daughters["pi-lab"]
            self.assertTrue(d["chain_ok"])
            self.assertTrue(d["verified"])
            self.assertFalse(d["stale"])
            self.assertEqual(d["brief"]["floor"]["processes"], 42)
            self.assertEqual(d["entry"]["seq"], 1)

    def test_unverified_without_secret(self):
        port = _free_port()
        _start_memory_service(port)
        with tempfile.TemporaryDirectory() as td:
            rt = _runtime(td, port)
            rt.beat(SNAP)
            daughters = hybrid.read_daughters(
                port=port, pair_secret="wrong", stale_minutes=45)
            self.assertFalse(daughters["pi-lab"]["verified"])

    def test_parent_down_queues_then_drains(self):
        port = _free_port()  # nothing listening yet
        with tempfile.TemporaryDirectory() as td:
            rt = _runtime(td, port)
            first = rt.beat(SNAP)
            self.assertFalse(first["sent"])
            self.assertEqual(first["queued"], 1)
            _start_memory_service(port)  # parent arrives
            second = rt.beat(SNAP)
            self.assertTrue(second["sent"])
            self.assertGreaterEqual(second["drained"], 1)
            self.assertEqual(second["queued"], 0)
            daughters = hybrid.read_daughters(
                port=port, pair_secret="s3cret")
            self.assertEqual(daughters["pi-lab"]["entry"]["seq"], 2)
            ok, _ = hybrid.verify_chain(rt.store.chain)
            self.assertTrue(ok)

    def test_hybrid_self_pair(self):
        # One box, both roles: daughter briefs its OWN memory
        # service; the parent surface reads them back from it.
        port = _free_port()
        _start_memory_service(port)
        with tempfile.TemporaryDirectory() as td:
            rt = _runtime(td, port)
            rt.beat(SNAP)
            rt.beat(SNAP)
            probe = hybrid.daughters_floor_probe(
                port=port, pair_secret="s3cret", stale_minutes=45)
            self.assertIn("pi-lab", probe)
            self.assertFalse(probe["pi-lab"]["stale"])
            self.assertTrue(probe["pi-lab"]["chain_ok"])
            self.assertEqual(probe["pi-lab"]["head"],
                             rt.store.head()[:12])

    def test_stale_after_threshold(self):
        port = _free_port()
        _start_memory_service(port)
        with tempfile.TemporaryDirectory() as td:
            rt = _runtime(td, port)
            rt.beat(SNAP)
            daughters = hybrid.read_daughters(
                port=port, pair_secret="s3cret", stale_minutes=45,
                now=time.time() + 46 * 60)
            self.assertTrue(daughters["pi-lab"]["stale"])

    def test_brief_carries_no_raw_media(self):
        body = hybrid.build_brief("pi-lab", SNAP, pair_secret="x")
        text = str(body).lower()
        for banned in ("base64", "audio", "image", "frame"):
            self.assertNotIn(banned, text)


if __name__ == "__main__":
    unittest.main()
