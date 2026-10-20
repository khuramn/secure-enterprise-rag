from pathlib import Path

import frontmatter

from schema import DocumentMetadata


def parse_document(file_path: Path):
    """
    Parse a Markdown document and validate
    its security metadata.
    """

    post = frontmatter.load(file_path)

    metadata = DocumentMetadata(
        document_id=post.metadata.get("document_id", ""),
        title=post.metadata.get("title", ""),
        department=post.metadata.get("department", ""),
        classification=post.metadata.get(
            "classification", ""
        ),
        allowed_groups=post.metadata.get(
            "allowed_groups", []
        ),
        region=post.metadata.get("region", ""),
    )

    # Security control: reject invalid metadata
    metadata.validate()

    content = post.content.strip()

    if not content:
        raise ValueError(
            f"{file_path.name}: document content is empty"
        )

    return metadata, content