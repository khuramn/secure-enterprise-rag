import os

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient



INDEX_NAME = "enterprise-documents"


# Simulated users for security testing.
# In production, these groups must come from
# validated Microsoft Entra identity information.
TEST_USERS = {
    "alice": ["finance-team", "employees"],
    "bob": ["employees"],
}


def build_authorization_filter(groups):
    """
    Build an Azure AI Search authorization filter
    from trusted group memberships.
    """

    if (not isinstance(groups, (list, tuple)) or not groups
            or not all(isinstance(g, str) and g.strip() for g in groups)):
        raise PermissionError(
            "Access denied: no authorized groups"
        )

    # Public documents are accessible to authenticated users.
    # Caller groups must originate from a trusted identity source.
    effective_groups = tuple(groups) + ("everyone",)

    # Escape single quotes for OData filter safety.
    escaped_groups = [
        group.replace("'", "''")
        for group in effective_groups
    ]

    clauses = [
        f"allowed_groups/any(g: g eq '{group}')"
        for group in escaped_groups
    ]

    return " or ".join(clauses)


def secure_search(username, query):

    if username not in TEST_USERS:
        raise PermissionError("Unknown user")

    # Group memberships are resolved server-side
    # from our trusted test-user mapping.
    user_groups = TEST_USERS[username]

    authorization_filter = build_authorization_filter(
        user_groups
    )

    credential = DefaultAzureCredential()

    search_client = SearchClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        index_name=INDEX_NAME,
        credential=credential,
    )

    results = search_client.search(
        search_text=query,
        filter=authorization_filter,
        select=[
            "document_id",
            "title",
            "classification",
            "allowed_groups",
        ],
        top=5,
    )

    documents = list(results)

    print(f"\nUser: {username}")
    print(f"Groups: {user_groups}")
    print(f"Query: {query}")
    print(f"Authorization filter: {authorization_filter}")

    if not documents:
        print("Result: No authorized documents")
        return

    for document in documents:
        print(
            f"Result: {document['document_id']} "
            f"- {document['title']}"
        )


if __name__ == "__main__":

    secure_search(
        "alice",
        "financial forecast",
    )

    secure_search(
        "bob",
        "financial forecast",
    )