"""Create a separate, model-specific vector index from validated synthetic sources."""
import os
from pathlib import Path

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchField, SearchFieldDataType, VectorSearch,
    VectorSearchProfile, HnswAlgorithmConfiguration,
)
from azure.core.exceptions import ResourceNotFoundError

from chunker import chunk_text
from embeddings import DIMENSIONS, embed_documents
from hybrid_search import INDEX_NAME
from parser import parse_document


def main():
    documents = []
    for path in sorted((Path(__file__).resolve().parent.parent / "documents").glob("*.md")):
        metadata, content = parse_document(path)
        if not isinstance(metadata.allowed_groups, list) or not all(
            isinstance(g, str) and g.strip() for g in metadata.allowed_groups
        ):
            raise ValueError(f"Invalid groups in {path.name}")
        for number, chunk in enumerate(chunk_text(content)):
            documents.append(dict(
                vars(metadata), id=f"{metadata.document_id}-{number:04d}", content=chunk
            ))
    if not documents:
        raise ValueError("No source documents")
    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    with DefaultAzureCredential() as credential, SearchIndexClient(endpoint, credential) as indexes:
        # Copy the actual live schema, preserving all metadata field definitions.
        source = indexes.get_index("enterprise-documents")
        try:
            existing = indexes.get_index(INDEX_NAME)
        except ResourceNotFoundError:
            existing = None
        if existing is not None:
            raise RuntimeError("Target index already exists; inspect it before re-ingesting")
        source.name = INDEX_NAME
        source.e_tag = None
        source.fields.append(SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True, vector_search_dimensions=DIMENSIONS,
            vector_search_profile_name="local-bge-v1",
        ))
        source.vector_search = VectorSearch(
            algorithms=[HnswAlgorithmConfiguration(name="hnsw-cosine", parameters={"metric": "cosine"})],
            profiles=[VectorSearchProfile(name="local-bge-v1", algorithm_configuration_name="hnsw-cosine")],
        )
        vectors = embed_documents([d["title"] + "\n" + d["content"] for d in documents])
        for document, vector in zip(documents, vectors, strict=True):
            if len(vector) != DIMENSIONS:
                raise ValueError("Embedding dimension mismatch")
            document["content_vector"] = vector
        indexes.create_index(source)
        with SearchClient(endpoint, INDEX_NAME, credential) as client:
            results = client.upload_documents(documents)
            failures = [r.key for r in results if not r.succeeded]
            if failures:
                raise RuntimeError(f"Failed uploads: {failures}")
        print(f"Indexed {len(documents)} chunks into {INDEX_NAME}")


if __name__ == "__main__":
    main()
