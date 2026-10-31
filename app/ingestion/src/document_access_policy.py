"""Trusted access policy for the synthetic RAG document collection.

This policy must be maintained separately from document content.
Production systems should use an approved policy source with
controlled changes and document ownership.
"""

DOCUMENT_ACCESS_POLICY = {
    "LEG-001": {
        "classification": "restricted",
        "allowed_groups": frozenset({"legal-team"}),
    },
    "HR-001": {
        "classification": "internal",
        "allowed_groups": frozenset({"employees"}),
    },
    "FIN-001": {
        "classification": "confidential",
        "allowed_groups": frozenset({"finance-team"}),
    },
    "PUB-001": {
        "classification": "public",
        "allowed_groups": frozenset({"everyone"}),
    },
    "SEC-001": {
        "classification": "confidential",
        "allowed_groups": frozenset({"security-team"}),
    },
}
