import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hybrid_search import retrieve
from secure_search import build_authorization_filter


class AuthorizationTests(unittest.TestCase):
    def test_fail_closed_before_embedding_or_search(self):
        for groups in ([], None, "employees", [""], [None]):
            client, embed = Mock(), Mock()
            with self.assertRaises(PermissionError):
                retrieve(client, groups, "forecast", embed=embed)
            client.search.assert_not_called()
            embed.assert_not_called()

    def test_escape_odata(self):
        self.assertEqual(
            build_authorization_filter(["x' or true"]),
            "allowed_groups/any(g: g eq 'x'' or true') "
            "or allowed_groups/any(g: g eq 'everyone')",
        )

    def test_filter_on_every_mode(self):
        for mode in ("keyword", "vector", "hybrid"):
            client = Mock()
            client.search.return_value = []
            retrieve(client, ["employees"], "forecast", mode, embed=lambda q: [0.1] * 384)
            options = client.search.call_args.kwargs
            self.assertEqual(
                options["filter"],
                "allowed_groups/any(g: g eq 'employees') "
                "or allowed_groups/any(g: g eq 'everyone')",
            )
            if mode != "keyword":
                self.assertEqual(options["vector_filter_mode"], "preFilter")
                self.assertIsNone(getattr(options["vector_queries"][0], "filter_override", None))


    def test_public_document_access(self):
        client = Mock()
        client.search.return_value = [
            {"document_id": "PUB-001", "allowed_groups": ["everyone"]}
        ]

        documents = retrieve(
            client, ["employees"], "product overview", mode="keyword"
        )

        self.assertEqual(documents[0]["document_id"], "PUB-001")

    def test_confidential_document_rejected(self):
        client = Mock()
        client.search.return_value = [
            {"document_id": "FIN-001", "allowed_groups": ["finance-team"]}
        ]

        with self.assertRaises(PermissionError):
            retrieve(client, ["employees"], "finance", mode="keyword")

    def test_missing_acl_rejected(self):
        client = Mock()
        client.search.return_value = [
            {"document_id": "BAD-001"}
        ]

        with self.assertRaises(PermissionError):
            retrieve(client, ["employees"], "test", mode="keyword")


if __name__ == "__main__":
    unittest.main()
