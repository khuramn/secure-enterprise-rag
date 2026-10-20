"""Live authorization and retrieval checks; exits nonzero on any failure."""
import json
import os
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from hybrid_search import INDEX_NAME, retrieve
from secure_search import TEST_USERS


def main():
    evidence = []
    with DefaultAzureCredential() as credential, SearchClient(
        os.environ["AZURE_SEARCH_ENDPOINT"], INDEX_NAME, credential
    ) as client:
        count = client.get_document_count()
        assert count == 5, f"Expected five synthetic chunks, got {count}"
        for mode in ("keyword", "vector", "hybrid"):
            for user in ("alice", "bob"):
                results = retrieve(client, TEST_USERS[user],
                                   "How much revenue is the company expecting in Q4?", mode)
                ids = [r["document_id"] for r in results]
                assert all(set(r["allowed_groups"]) & set(TEST_USERS[user]) for r in results)
                assert ("FIN-001" in ids) == (user == "alice"), (mode, user, ids)
                if user == "alice" and mode != "keyword":
                    assert ids[0] == "FIN-001", (mode, ids)
                evidence.append(dict(mode=mode, user=user, document_ids=ids, authorization="PASS"))
        for mode in ("keyword", "vector", "hybrid"):
            ids = [r["document_id"] for r in retrieve(
                client, TEST_USERS["alice"], "anticipated turnover", mode)]
            if mode == "keyword":
                assert "FIN-001" not in ids, ids
            else:
                assert ids[0] == "FIN-001", ids
            evidence.append(dict(mode=mode, query="anticipated turnover", document_ids=ids))
        for groups in ([], None):
            try:
                retrieve(client, groups, "forecast")
            except PermissionError:
                continue
            raise AssertionError("Missing groups did not deny access")
    print(json.dumps(dict(index=INDEX_NAME, chunks=count, checks=evidence,
                         empty_groups="DENIED"), indent=2))


if __name__ == "__main__":
    main()
