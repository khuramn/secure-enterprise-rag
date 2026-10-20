
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient

from chunker import chunk_text
from embeddings import generate_embedding
from parser import parse_document


SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME = "enterprise-documents"

DOCUMENT_PATH = (
    Path(__file__).resolve().parent.parent / "documents"
)


def main():
    credential = DefaultAzureCredential()

    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=credential,
    )

    files = sorted(DOCUMENT_PATH.glob("*.md"))

    if not files:
        raise RuntimeError(
            f"No documents found in {DOCUMENT_PATH}"
        )

    indexed_documents = []
    rejected_documents = []
    seen_document_ids = set()

    # Step 1: Parse and validate all documents
    for file_path in files:
        print(f"Processing: {file_path.name}")

        try:
            metadata, content = parse_document(file_path)

            if metadata.document_id in seen_document_ids:
                raise ValueError(
                    f"Duplicate document_id: {metadata.document_id}"
                )

            chunks = chunk_text(content)

            if not chunks:
                raise ValueError("Document generated no chunks")

            if any(not chunk.strip() for chunk in chunks):
                raise ValueError("Document contains an empty chunk")

            seen_document_ids.add(metadata.document_id)

            print(
                f"  Document: {metadata.document_id}, "
                f"Chunks generated: {len(chunks)}"
            )

            # Step 2: Prepare each chunk for indexing
            for chunk_number, chunk in enumerate(chunks):
                chunk_id = (
                    f"{metadata.document_id}-"
                    f"{chunk_number:04d}"
                )

                indexed_documents.append(
                    {
                        "id": chunk_id,
                        "document_id": metadata.document_id,
                        "title": metadata.title,
                        "content": chunk,
                        "department": metadata.department,
                        "classification": metadata.classification,
                        "allowed_groups": metadata.allowed_groups,
                        "region": metadata.region,
                    }
                )

        except (ValueError, TypeError, KeyError) as exc:
            print(f"REJECTED {file_path.name}: {exc}")
            rejected_documents.append(file_path.name)

    # Security control: reject incomplete ingestion batches
    if rejected_documents:
        raise RuntimeError(
            "Ingestion stopped because documents were rejected: "
            + ", ".join(rejected_documents)
        )

    if not indexed_documents:
        raise RuntimeError(
            "No valid documents available for indexing"
        )

    # Step 3: Generate embeddings after validation succeeds
    print(
        f"\nGenerating embeddings for "
        f"{len(indexed_documents)} chunk(s)..."
    )

    for document in indexed_documents:
        document["content_vector"] = generate_embedding(
            document["content"]
        )

        print(f"  Embedded: {document['id']}")

    # Step 4: Upload the complete batch to Azure AI Search
    print("\nUploading documents to Azure AI Search...")

    result = search_client.upload_documents(
        documents=indexed_documents
    )

    failed = [
        item for item in result
        if not item.succeeded
    ]

    if failed:
        for item in failed:
            print(
                f"FAILED: {item.key}: "
                f"{item.error_message}"
            )

        raise RuntimeError(
            "One or more chunks failed to index"
        )

    print(
        f"\nSuccessfully indexed "
        f"{len(indexed_documents)} chunk(s)"
    )


if __name__ == "__main__":
    main()
