import pytest

from schema import DocumentMetadata


def make_metadata(
    document_id="FIN-001",
    classification="confidential",
    allowed_groups=None,
):
    return DocumentMetadata(
        document_id=document_id,
        title="Test Document",
        department="finance",
        classification=classification,
        allowed_groups=(
            ["finance-team"]
            if allowed_groups is None
            else allowed_groups
        ),
        region="uks",
    )


def test_approved_document_acl():
    metadata = make_metadata()
    metadata.validate()


def test_acl_expansion_is_rejected():
    metadata = make_metadata(
        allowed_groups=["employees"],
    )

    with pytest.raises(
        ValueError,
        match="Document ACL does not match approved access policy",
    ):
        metadata.validate()


def test_unknown_document_is_rejected():
    metadata = make_metadata(document_id="FIN-TEST")

    with pytest.raises(
        ValueError,
        match="No approved access policy",
    ):
        metadata.validate()


def test_classification_change_is_rejected():
    metadata = make_metadata(classification="public")

    with pytest.raises(
        ValueError,
        match="Document classification does not match approved policy",
    ):
        metadata.validate()


def test_duplicate_acl_groups_are_rejected():
    metadata = make_metadata(
        allowed_groups=["finance-team", "finance-team"],
    )

    with pytest.raises(
        ValueError,
        match="Document ACL does not match approved access policy",
    ):
        metadata.validate()
