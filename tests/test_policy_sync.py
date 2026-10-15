import unittest
from backend.ai.rag.vector_store import plan_sync
from backend.ai.settings import Config


class PolicyPlanTests(unittest.TestCase):
    def test_unchanged_document_skips_embedding(self):
        docs = {"doc1": ("content", {}, "hash1")}
        indexed = {"doc1": ("hash1", Config.EMBEDDING_MODEL)}
        self.assertEqual(plan_sync(docs, indexed), (set(), set()))

    def test_changed_document_is_selected(self):
        docs = {"doc1": ("updated", {}, "hash2")}
        indexed = {"doc1": ("hash1", Config.EMBEDDING_MODEL)}
        self.assertEqual(plan_sync(docs, indexed)[0], {"doc1"})

    def test_removed_document_is_deleted(self):
        indexed = {"doc1": ("hash1", Config.EMBEDDING_MODEL)}
        self.assertEqual(plan_sync({}, indexed)[1], {"doc1"})
