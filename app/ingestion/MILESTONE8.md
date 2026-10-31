# Milestone 8: authorization-aware hybrid retrieval

Implemented 14 October 2026 using the existing free Azure AI Search service.
No Terraform changes or Azure OpenAI resources are needed.

## Architecture

Synthetic Markdown → validated metadata and chunks → local FastEmbed
BAAI/bge-small-en-v1.5 embeddings (384 dimensions) → Azure Search index
`enterprise-documents-vector-v1`.

A query uses the same local model. Hybrid mode sends keyword text and a
VectorizedQuery in one request. The top-level allowed_groups filter applies
to the whole request; vector_filter_mode="preFilter" restricts vector matching.
There are no per-vector filter overrides. Every chunk retains its ACL metadata.
The original enterprise-documents index remains available for Milestone 7.

First use downloads the model; later calls use app/ingestion/.cache (ignored
by Git). FASTEMBED_CACHE_PATH can override this location. Embedding inference
runs locally; no embedding endpoint, static secret, or inference API charge.
Existing Azure subscription charges outside this change are unaffected.

## Run

From the repository root after `az login`:

```sh
source app/ingestion/.venv/bin/activate
export AZURE_SEARCH_ENDPOINT=https://srch-ai-rag-dev-nkihn6.search.windows.net
python -m pip install -r app/ingestion/requirements.txt
python app/ingestion/src/hybrid_search.py alice 'anticipated turnover'
python app/ingestion/src/hybrid_search.py bob 'anticipated turnover'
python app/ingestion/src/verify_vector_search.py
python -m unittest discover -s app/ingestion/tests -v
```

The vector index is already populated. For a fresh environment, run
prepare_vector_index.py once. It copies the live keyword index schema, validates
all sources and generates vectors before creating the separate target index.
It refuses to overwrite an existing target. An upload failure can leave a partial
new index: inspect it before recovery; the keyword index stays usable. Changes
to source documents require an explicit re-ingestion/versioning procedure.
Do not mix embeddings from different models or dimensions in this index.

## Verification on Azure

All five chunks uploaded. The Q4 question returned FIN-001 first for Alice in
vector and hybrid modes. Bob received only HR-001 in keyword/vector/hybrid
modes, never FIN-001. Empty groups were denied before embedding or search.

For the paraphrase `anticipated turnover`, keyword mode returned no documents;
vector and hybrid modes ranked FIN-001 first for Alice. This demonstrates a
semantic retrieval benefit on the tiny synthetic corpus, not a general benchmark.

Three unit tests pass: malformed/empty groups fail closed before any search,
OData quotes are escaped, and every retrieval mode carries its server-side ACL.
Terraform validate and dependency compatibility checks pass.

## Security boundary and limitations

Alice/Bob are trusted local test fixtures, not authenticated user identities.
Do not expose the CLI username as a web authentication mechanism. Production
must validate Entra tokens and resolve group membership server-side, including
handling group overage. Azure Search authenticates the application's identity;
it does not infer the end user's permissions from allowed_groups. Any client
with Search data access can bypass this application's filter. End users must
not receive those credentials or direct Search data roles.

DefaultAzureCredential supports local Entra development and managed identity
in Azure. No runtime identity is provisioned by this milestone. A hosted runtime
should have Search Index Data Reader; ingestion uses separate data contributor
and index-management access.

Vector retrieval returns nearest authorized documents even if unrelated. Bob
can receive HR-001 for a finance question; that must not be interpreted as a
supported answer. Answerability checks and grounded LLM generation remain future
work. No paid semantic reranker or LLM generation is enabled here.

References:
- https://learn.microsoft.com/en-us/azure/search/vector-search-filters
- https://learn.microsoft.com/en-us/azure/search/hybrid-search-how-to-query
- https://qdrant.tech/documentation/fastembed/fastembed-quickstart/
