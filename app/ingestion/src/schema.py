from dataclasses import dataclass
from typing import List

try:
    from document_access_policy import DOCUMENT_ACCESS_POLICY
except ModuleNotFoundError as exc:
    if exc.name != "document_access_policy":
        raise
    from .document_access_policy import DOCUMENT_ACCESS_POLICY


VALID_CLASSIFICATIONS = {
    "public",
    "internal",
    "confidential",
    "restricted",
}


@dataclass
class DocumentMetadata:
    document_id: str
    title: str
    department: str
    classification: str
    allowed_groups: List[str]
    region: str

    def validate(self) -> None:
        if not isinstance(self.document_id, str) or not self.document_id.strip():
            raise ValueError("document_id is required")

        if not isinstance(self.title, str) or not self.title.strip():
            raise ValueError("title is required")

        if self.classification not in VALID_CLASSIFICATIONS:
            raise ValueError(
                f"Invalid classification: {self.classification}"
            )

        if (
            not isinstance(self.allowed_groups, list)
            or not self.allowed_groups
            or not all(
                isinstance(group, str) and group.strip()
                for group in self.allowed_groups
            )
        ):
            raise ValueError("Invalid allowed_groups metadata")

        policy = DOCUMENT_ACCESS_POLICY.get(self.document_id)

        if policy is None:
            raise ValueError(
                f"No approved access policy for {self.document_id}"
            )

        if self.classification != policy["classification"]:
            raise ValueError(
                "Document classification does not match approved policy"
            )

        if (
            len(self.allowed_groups) != len(set(self.allowed_groups))
            or set(self.allowed_groups) != policy["allowed_groups"]
        ):
            raise ValueError(
                "Document ACL does not match approved access policy"
            )
