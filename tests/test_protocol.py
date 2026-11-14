"""Baseline: core.protocol — tokens, wire caller, response shapes."""
import json
import socket
import unittest

from tests import __init__ as _path  # noqa: F401  (inserts source/ path)
from core import protocol


def _closed_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestTokens(unittest.TestCase):
    def test_roundtrip(self):
        tok = protocol.build_tool_token("files", "read", {"path": "/x"})
        self.assertTrue(protocol.is_tool_call(tok))
        svc, act, params = protocol.parse_tool_token(tok)
        self.assertEqual((svc, act), ("files", "read"))
        self.assertEqual(params, {"path": "/x"})

    def test_is_tool_call_false(self):
        self.assertFalse(protocol.is_tool_call("just text"))

    def test_parse_malformed_raises(self):
        with self.assertRaises((IndexError, ValueError)):
            protocol.parse_tool_token("TOOL:onlyonepart")

    def test_response_shapes(self):
        self.assertEqual(protocol.ok(a=1), {"status": "ok", "a": 1})
        self.assertEqual(protocol.pong(), {"status": "pong"})
        self.assertEqual(protocol.error("no"),
                         {"status": "error", "message": "no"})


class TestWire(unittest.TestCase):
    def test_mcp_call_failure_shape(self):
        resp = protocol.mcp_call(_closed_port(), {"action": "ping"},
                                 timeout=1)
        self.assertEqual(resp["status"], "error")
        self.assertIn("message", resp)

    def test_service_ports_complete(self):
        self.assertEqual(sorted(protocol.SERVICE_PORTS),
                         ["coding", "files", "memory", "shell",
                          "sound", "vision", "voice", "web"])
        ports = list(protocol.SERVICE_PORTS.values())
        self.assertEqual(len(set(ports)), 8)


if __name__ == "__main__":
    unittest.main()
