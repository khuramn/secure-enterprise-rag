
import os
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from embeddings import generate_embedding
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from secure_search import (
    TEST_USERS,
    build_authorization_filter,
)


INDEX_NAME = "enterprise-documents"


def retrieve(client, groups, query, mode="hybrid", *, embed=None):
    authorization_filter = build_authorization_filter(groups)
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Search query cannot be empty")
    if mode not in {"keyword", "vector", "hybrid"}:
        raise ValueError("Unknown search mode")
    options = dict(filter=authorization_filter, select=[
        "document_id", "title", "classification", "allowed_groups", "content"
    ], top=5)
    if mode != "keyword":
        if embed is None:
            from embeddings import generate_embedding
            embed = generate_embedding
        options.update(vector_queries=[VectorizedQuery(
            vector=embed(query), k_nearest_neighbors=5, fields="content_vector"
        )], vector_filter_mode="preFilter")
    documents = list(client.search(search_text=query if mode != "vector" else None, **options))
    # Defense in depth: enforce the same ACL policy after retrieval.
    # "everyone" permits access to authenticated users, not anonymous callers.
    effective_groups = set(groups) | {"everyone"}

    for document in documents:
        acl = document.get("allowed_groups")

        if (
            not isinstance(acl, list)
            or not acl
            or not all(isinstance(g, str) and g.strip() for g in acl)
            or not set(acl).intersection(effective_groups)
        ):
            raise PermissionError(
                "Search returned an unauthorized document"
            )
    return documents


def hybrid_search(username, query):
    from identity import VerifiedIdentity
    if isinstance(username, VerifiedIdentity):
        groups = username.acl_labels
    elif isinstance(username, str) and username in TEST_USERS:
        # Compatibility for local CLI regression scripts only; API accepts no username.
        groups = TEST_USERS[username]
    else:
        raise PermissionError("Unknown user")
    build_authorization_filter(groups)
    with DefaultAzureCredential() as credential:
        with SearchClient(endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
                          index_name=INDEX_NAME, credential=credential) as client:
            return retrieve(client, groups, query)


def hybrid_search_for_groups(
    allowed_groups: tuple[str, ...],
    query: str,
):
    """
    Perform authorization-aware retrieval using groups
    derived from a validated Microsoft Entra access token.
    """

    trusted_groups = set(allowed_groups)

    valid_groups = {
        "finance-team",
        "employees",
    }

    if not trusted_groups:
        raise PermissionError("No authorized groups")

    if not trusted_groups.issubset(valid_groups):
        raise PermissionError("Unknown authorization group")

    with DefaultAzureCredential() as credential:
        with SearchClient(
            endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
            index_name=INDEX_NAME,
            credential=credential,
        ) as client:
            return retrieve(
                client,
                tuple(sorted(trusted_groups)),
                query,
                mode="hybrid",
            )


if __name__ == "__main__":
    question = (
        "How much revenue is the company "
        "expecting in the final quarter?"
    )

    alice_results = hybrid_search("alice", question)
    bob_results = hybrid_search("bob", question)

    alice_ids = {
        doc["document_id"] for doc in alice_results
    }

    bob_ids = {
        doc["document_id"] for doc in bob_results
    }

    assert "FIN-001" in alice_ids, (
        "FAILED: Alice cannot retrieve the finance document"
    )

    assert "FIN-001" not in bob_ids, (
        "SECURITY FAILURE: Bob retrieved confidential finance data"
    )

    print("\nPASS: Authorization-aware hybrid search")