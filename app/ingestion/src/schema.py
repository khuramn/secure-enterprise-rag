from dataclasses import dataclass
from typing import List


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
        if not self.document_id:
            raise ValueError("document_id is required")

        if not self.title:
            raise ValueError("title is required")

        if self.classification not in VALID_CLASSIFICATIONS:
            raise ValueError(
                f"Invalid classification: {self.classification}"
            )

        if not self.allowed_groups:
            raise ValueError(
                "At least one allowed group is required"
            )