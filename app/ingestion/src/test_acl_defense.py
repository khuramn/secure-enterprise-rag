from unittest.mock import Mock

from hybrid_search import retrieve


def test_unauthorized_document_is_rejected():
    """
    Simulate Azure AI Search returning a finance document
    to a user who belongs only to the employees group.
    """

    fake_search_client = Mock()

    fake_search_client.search.return_value = [
        {
            "document_id": "FIN-001",
            "title": "Q4 Financial Forecast",
            "classification": "confidential",
            "allowed_groups": ["finance-team"],
            "content": "Confidential financial information",
        }
    ]

    try:
        retrieve(
            client=fake_search_client,
            groups=("employees",),
            query="What is the Q4 financial forecast?",
            mode="keyword",
        )

    except PermissionError:
        print("PASS: Unauthorized finance document rejected")

    else:
        raise AssertionError(
            "SECURITY FAILURE: Unauthorized document was accepted"
        )


def test_authorized_document_is_accepted():
    """
    Verify that legitimate finance access still works.
    """

    fake_search_client = Mock()

    fake_search_client.search.return_value = [
        {
            "document_id": "FIN-001",
            "title": "Q4 Financial Forecast",
            "classification": "confidential",
            "allowed_groups": ["finance-team"],
            "content": "Confidential financial information",
        }
    ]

    results = retrieve(
        client=fake_search_client,
        groups=("finance-team", "employees"),
        query="What is the Q4 financial forecast?",
        mode="keyword",
    )

    assert len(results) == 1
    assert results[0]["document_id"] == "FIN-001"

    print("PASS: Authorized finance document accepted")

def test_invalid_acl_metadata():
    cases = [
        ("missing ACL", {}),
        ("empty ACL", {"allowed_groups": []}),
        ("malformed ACL", {"allowed_groups": "employees"}),
        ("null ACL", {"allowed_groups": None}),
    ]

    for name, metadata in cases:
        fake_client = Mock()
        fake_client.search.return_value = [
            {
                "document_id": "SEC-TEST-001",
                "title": "Test document",
                "content": "Sensitive test content",
                **metadata,
            }
        ]

        try:
            retrieve(
                client=fake_client,
                groups=("employees",),
                query="Sensitive test content",
                mode="keyword",
            )
        except PermissionError:
            print(f"PASS: {name} rejected")
        else:
            raise AssertionError(
                f"SECURITY FAILURE: {name} accepted"
            )
if __name__ == "__main__":
    test_unauthorized_document_is_rejected()
    test_authorized_document_is_accepted()
    test_invalid_acl_metadata()

    print("\nAll ACL defense-in-depth tests passed.")