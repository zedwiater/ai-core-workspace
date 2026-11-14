"""core.models — stacks: sanitize, discovery, probe, resolve, chat."""
import json
import unittest

from tests import __init__ as _path  # noqa: F401
from core import models


class _Opener:
    """Fake transport: routes (method, url-fragment) -> (code, json)
    or an Exception instance to raise."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def __call__(self, method, url, payload=None, timeout=5, headers=None):
        self.calls.append((method, url, payload, headers))
        for fragment, resp in self.routes.items():
            if fragment in url:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        raise RuntimeError(f"no route for {url}")


TAGS = (200, {"models": [{"name": "qwen3.5:9b"}, {"name": "llava:7b"}]})
OLLAMA_CHAT = (200, {"message": {"content": "  hello  "}})
OPENAI_MODELS = (200, {"data": [{"id": "m1"}]})
OPENAI_CHAT = (200, {"choices": [{"message": {"content": "hi there"}}]})


def _mem_call(store):
    def call(port, payload, timeout=2):
        if payload["action"] == "set":
            store[payload["key"]] = payload["value"]
            return {"status": "ok"}
        return {"status": "ok", "value": store.get(payload["key"])}
    return call


class TestStacks(unittest.TestCase):
    def test_defaults(self):
        s = models.default_stacks("qwen3.5:9b")
        self.assertEqual(s["chat"],
                         [{"kind": "ollama", "model": "qwen3.5:9b"}])
        self.assertEqual(s["reason"], [])
        self.assertEqual(s["summarizer"], [])

    def test_load_sanitizes(self):
        store = {"app:model-stacks": json.dumps({
            "chat": [{"kind": "ollama", "model": "a"},
                     {"kind": "openai", "model": "b"},  # no base_url
                     {"kind": "mystery", "model": "c"},
                     {"kind": "openai", "model": "d",
                      "base_url": "http://lan:9000/v1/"}],
            "reason": "not-a-list"})}
        s = models.load_stacks("qwen3.5:9b", call=_mem_call(store))
        self.assertEqual(len(s["chat"]), 2)
        self.assertEqual(s["chat"][1]["base_url"], "http://lan:9000/v1")
        self.assertEqual(s["reason"], [])  # fell back to default

    def test_save_load_roundtrip(self):
        store = {}
        s = models.default_stacks("m")
        s["reason"] = [{"kind": "ollama", "model": "deep:30b"}]
        self.assertTrue(models.save_stacks(s, call=_mem_call(store)))
        back = models.load_stacks("m", call=_mem_call(store))
        self.assertEqual(back["reason"], s["reason"])

    def test_labels_and_locality(self):
        self.assertTrue(models.is_local({"kind": "ollama"}))
        e = {"kind": "openai", "model": "m", "base_url": "http://x/v1"}
        self.assertFalse(models.is_local(e))
        self.assertIn("http://x/v1", models.entry_label(e))


class TestProbeResolve(unittest.TestCase):
    def test_discover(self):
        op = _Opener({"/api/tags": TAGS})
        self.assertEqual(models.discover_ollama(opener=op),
                         ["qwen3.5:9b", "llava:7b"])
        down = _Opener({"/api/tags": RuntimeError("refused")})
        self.assertEqual(models.discover_ollama(opener=down), [])

    def test_probe_states(self):
        op = _Opener({"/api/tags": TAGS})
        ok = models.probe_entry({"kind": "ollama", "model": "llava:7b"},
                                opener=op)
        self.assertEqual(ok["state"], "reachable")
        missing = models.probe_entry(
            {"kind": "ollama", "model": "ghost:1b"}, opener=op)
        self.assertEqual(missing["state"], "model-missing")
        dead = models.probe_entry(
            {"kind": "openai", "model": "m", "base_url": "http://x/v1"},
            opener=_Opener({"/models": RuntimeError("no")}))
        self.assertEqual(dead["state"], "unreachable")

    def test_resolve_skips_missing_to_endpoint(self):
        stacks = {"chat": [
            {"kind": "ollama", "model": "ghost:1b"},
            {"kind": "openai", "model": "m",
             "base_url": "http://lan:9000/v1"}]}
        op = _Opener({"/api/tags": TAGS, "/models": OPENAI_MODELS})
        entry, report = models.resolve_chat_entry(stacks, opener=op)
        self.assertEqual(entry["model"], "m")
        self.assertEqual([v for _e, v in report],
                         ["model-missing", "served"])

    def test_resolve_policy_never_blocks_cloud(self):
        stacks = {"chat": [
            {"kind": "openai", "model": "m",
             "base_url": "http://lan:9000/v1"},
            {"kind": "ollama", "model": "qwen3.5:9b"}]}
        op = _Opener({"/api/tags": TAGS, "/models": OPENAI_MODELS})
        entry, report = models.resolve_chat_entry(
            stacks, policy="never", opener=op)
        self.assertEqual(entry["kind"], "ollama")
        self.assertEqual(report[0][1], "blocked by cloud policy")

    def test_resolve_budget_blocks_cloud(self):
        stacks = {"chat": [
            {"kind": "openai", "model": "m",
             "base_url": "http://lan:9000/v1"}]}
        op = _Opener({"/models": OPENAI_MODELS})
        entry, report = models.resolve_chat_entry(
            stacks, policy="allowed", budget_ok=False, opener=op)
        self.assertIsNone(entry)
        self.assertEqual(report[0][1], "blocked by session budget")

    def test_resolve_none_reachable(self):
        stacks = {"chat": [{"kind": "ollama", "model": "qwen3.5:9b"}]}
        op = _Opener({"/api/tags": RuntimeError("down")})
        entry, report = models.resolve_chat_entry(stacks, opener=op)
        self.assertIsNone(entry)
        self.assertEqual(report[0][1], "unreachable")


class TestChatCompletion(unittest.TestCase):
    def test_ollama_chat(self):
        op = _Opener({"/api/chat": OLLAMA_CHAT})
        out = models.chat_completion(
            {"kind": "ollama", "model": "qwen3.5:9b"},
            [{"role": "user", "content": "hi"}], opener=op)
        self.assertEqual(out, "hello")

    def test_openai_chat_sends_key(self):
        op = _Opener({"/chat/completions": OPENAI_CHAT})
        entry = {"kind": "openai", "model": "m",
                 "base_url": "http://x/v1", "api_key": "k123"}
        out = models.chat_completion(entry, [], opener=op)
        self.assertEqual(out, "hi there")
        _m, _u, _p, headers = op.calls[0]
        self.assertEqual(headers.get("Authorization"), "Bearer k123")

    def test_failure_is_honest_runtime_error(self):
        op = _Opener({"/api/chat": RuntimeError("refused")})
        with self.assertRaises(RuntimeError) as ctx:
            models.chat_completion({"kind": "ollama", "model": "m"},
                                   [], opener=op)
        self.assertIn("didn't answer", str(ctx.exception))

    def test_empty_choices_raise(self):
        op = _Opener({"/chat/completions": (200, {"choices": []})})
        with self.assertRaises(RuntimeError):
            models.chat_completion(
                {"kind": "openai", "model": "m",
                 "base_url": "http://x/v1"}, [], opener=op)


if __name__ == "__main__":
    unittest.main()
