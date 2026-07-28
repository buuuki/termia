import unittest
from types import SimpleNamespace

from termia.session_registry import SessionRegistry


class SessionRegistryTests(unittest.TestCase):
    def test_register_lookup_remove_and_snapshot(self) -> None:
        first = SimpleNamespace(id="first")
        second = SimpleNamespace(id="second")
        registry = SessionRegistry()

        registry.register(first)
        registry.register(second)

        self.assertTrue(registry)
        self.assertTrue(registry.contains("first"))
        self.assertIs(registry.get("second"), second)
        self.assertEqual(registry.sessions(), (first, second))
        self.assertIs(registry.remove("first"), first)
        self.assertFalse(registry.contains("first"))
        self.assertIsNone(registry.remove("missing"))

    def test_register_rejects_duplicate_session_id(self) -> None:
        registry = SessionRegistry([SimpleNamespace(id="duplicate")])

        with self.assertRaisesRegex(ValueError, "already registered"):
            registry.register(SimpleNamespace(id="duplicate"))
