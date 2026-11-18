"""Baseline: core.ring_service — the shared register/serve/report scaffold."""
import json
import unittest

from tests import __init__ as _path  # noqa: F401
from core.ring_service import RingService
from core import ring_service


def _svc(**kw):
    return RingService("demo", "state", 9999,
                       {"ping": lambda req: {"status": "pong"}}, **kw)


class TestScaffold(unittest.TestCase):
    def test_ping_dispatch(self):
        resp = _svc().handle(json.dumps({"action": "ping"}))
        self.assertEqual(resp, {"status": "pong"})

    def test_health_auto_report(self):
        resp = _svc().handle('{"action": "health"}')
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["service"], "demo")
        self.assertEqual(resp["ring"], "state")
        self.assertEqual(resp["port"], 9999)
        self.assertIn("uptime_s", resp)

    def test_own_health_preserved(self):
        svc = RingService(
            "webby", "atmosphere", 9998,
            {"ping": lambda req: {"status": "pong"},
             "health": lambda req: {"status": "ok",
                                    "reachable": True}})
        resp = svc.handle('{"action": "health"}')
        self.assertEqual(resp, {"status": "ok", "reachable": True})

    def test_unknown_action_format(self):
        resp = _svc().handle('{"action": "dance"}')
        self.assertEqual(resp["status"], "error")
        self.assertEqual(resp["message"], "Unknown action: dance")

    def test_invalid_json_generic(self):
        resp = _svc().handle("not json")
        self.assertEqual(resp["status"], "error")

    def test_invalid_json_custom_message(self):
        resp = _svc(json_error="Invalid JSON").handle("not json")
        self.assertEqual(resp["message"], "Invalid JSON")

    def test_handler_exception_becomes_error(self):
        def boom(req):
            raise RuntimeError("kaboom")

        svc = RingService("demo", "state", 9999, {"ping": boom})
        resp = svc.handle('{"action": "ping"}')
        self.assertEqual(resp["status"], "error")
        self.assertIn("kaboom", resp["message"])


class TestLabelsAndRoutes(unittest.TestCase):
    def test_parse_label_docstring_and_comment_forms(self):
        doc = ('"""\nLabel-Name: memory\nLabel-Origin: build\n'
               'Label-Version: 1\nLabel-Does: kv store\n"""\n')
        lab = ring_service.parse_label(doc)
        self.assertTrue(ring_service.label_complete(lab))
        block = ring_service.label_block("memory", "build", "1",
                                         "kv store")
        self.assertTrue(ring_service.label_complete(
            ring_service.parse_label(block)))
        self.assertIsNone(ring_service.parse_label("no label"))

    def test_serve_route_resolves_port_constant(self):
        src = ('PORT = 9108\n'
               'serve("memory", "state", PORT, {"get": g})\n')
        route = ring_service.serve_route(src)
        self.assertEqual(route["port"], 9108)
        self.assertEqual(route["actions"], ["get"])

    def test_real_services_are_labeled_and_routed(self):
        import pathlib
        root = pathlib.Path(__file__).resolve().parents[1]
        for path in sorted((root / "source" / "rings").glob(
                "*/*.py")):
            text = path.read_text()
            self.assertTrue(ring_service.label_complete(
                ring_service.parse_label(text)), path.name)
            route = ring_service.serve_route(text)
            self.assertIsNotNone(route, path.name)
            from core.protocol import SERVICE_PORTS
            self.assertEqual(SERVICE_PORTS[route["name"]],
                             route["port"], path.name)


if __name__ == "__main__":
    unittest.main()
