
import os

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from embeddings import generate_embedding
from secure_search import (
    TEST_USERS,
    build_authorization_filter,
)


SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME = "enterprise-documents"


def hybrid_search(username: str, query: str):
    # Demo identities only.
    # Never accept group memberships directly from users.
    if username not in TEST_USERS:
        raise PermissionError("Unknown user")

    if not query or not query.strip():
        raise ValueError("Search query cannot be empty")

    user_groups = TEST_USERS[username]

    # Server-side authorization based on trusted group membership
    authorization_filter = build_authorization_filter(
        user_groups
    )

    # Generate a vector for the user's question
    query_vector = generate_embedding(query)

    credential = DefaultAzureCredential()

    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )

    vector_query = VectorizedQuery(
        vector=query_vector,
        k_nearest_neighbors=5,
        fields="content_vector",
    )

    results = search_client.search(
        search_text=query,
        vector_queries=[vector_query],
        vector_filter_mode="preFilter",
        filter=authorization_filter,
        select=[
            "document_id",
            "title",
            "classification",
            "allowed_groups",
            "content",
        ],
        top=5,
        include_total_count=True,
    )

    documents = list(results)

    print(f"\nUser: {username}")
    print(f"Groups: {user_groups}")
    print(f"Question: {query}")
    print(f"Authorization filter: {authorization_filter}")
    print(f"Authorized results: {len(documents)}")

    for document in documents:
        print(
            f"  {document['document_id']} "
            f"- {document['title']}"
        )

    return documents


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