
import os

from azure.identity import DefaultAzureCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME = "enterprise-documents"

EMBEDDING_DIMENSIONS = 1536


def main():
    credential = DefaultAzureCredential()

    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=credential,
    )

    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),

        SimpleField(
            name="document_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        SearchableField(
            name="title",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
        ),

        # NEW: Vector embeddings
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.Single
            ),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="rag-vector-profile",
        ),

        SimpleField(
            name="department",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),

        SimpleField(
            name="classification",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),

        # Security metadata used for authorization filtering
        SearchField(
            name="allowed_groups",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.String
            ),
            filterable=True,
        ),

        SimpleField(
            name="region",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
    ]

    # NEW: HNSW vector search configuration
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="rag-hnsw"
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="rag-vector-profile",
                algorithm_configuration_name="rag-hnsw",
            )
        ],
    )

    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
    )

    result = index_client.create_or_update_index(index)

    print(f"Index ready: {result.name}")
    print("Vector search enabled")
    print(f"Embedding dimensions: {EMBEDDING_DIMENSIONS}")


if __name__ == "__main__":
    main()
