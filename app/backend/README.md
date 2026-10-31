# Milestone 12: authenticated RAG API

Run from the repository root with Python 3.14 (validated). Install into a virtual environment:

```sh
python -m pip install -r app/backend/requirements.lock.txt
# Export the values in app/backend/.env.example using your environment manager.
# The application intentionally does not automatically load .env files.
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
python -m pytest app/backend/tests app/ingestion/tests -q
```

Startup fails if identity settings are missing or malformed. The example is deliberately invalid until your actual IDs are supplied. Never commit bearer tokens or local environment files. GET /health is unauthenticated liveness only; it does not claim Azure readiness. POST /query requires `Authorization: Bearer <access_token>` and JSON `{"question":"What is the leave policy?"}`. It returns only `answer` and `request_id`; no raw documents, ACLs, usernames, or group IDs. Unknown request fields are rejected. 401 means invalid/missing authentication, 403 means claims do not authorize access, 422 means invalid input, and 503 means a sanitized service failure.

## Entra setup

1. Create a single-tenant API app registration. Record its Directory (tenant) ID and Application (client) ID. Set `api.requestedAccessTokenVersion` to 2 in its manifest. Expose a delegated scope `Query.Read` under its Application ID URI (usually `api://<api-client-id>`). The API validates the v2 token audience as the API's client GUID, not that URI.
2. Create a separate client app registration. Configure its correct platform redirect URI and authorization-code flow with PKCE (use MSAL). Add delegated permission for the API scope and grant the required consent. Add this client's GUID to `ENTRA_ALLOWED_CLIENT_IDS`. Do not enable implicit flow or use client-credentials tokens for user queries. Request `api://<api-client-id>/Query.Read` and send the returned access token, never the ID token. Keeping caller and API registrations separate also prevents audience confusion.
3. Configure the API registration's access-token group claims to emit group object IDs (security groups or groups assigned to the application). Check assignment/licensing and nested-membership behavior for your tenant. Do not emit display names or on-premises group names.
4. Obtain the actual finance and employees group object IDs from your tenant administrator. Populate `ENTRA_GROUP_ACL_MAP` server-side to map them to existing index labels `finance-team` and `employees`. Membership of finance does not implicitly grant employees: configure mappings/memberships deliberately. Unknown group IDs grant no labels. Empty, missing, malformed, or overage claims deny access, even if another mapped group appears. No Graph fallback or token-supplied claim-source URL is followed.
5. Populate the remaining environment settings with the existing Azure endpoints and deployment name. Tenant, API, caller, and group IDs must come from your own registration; none are assumed by the application.

## Backend workload identity

User access tokens authenticate API callers only. Azure Search and Azure OpenAI calls use the existing DefaultAzureCredential flow, independently of caller credentials. Locally use `az login` in the intended tenant with the developer's Azure RBAC assignments. In Azure enable managed identity or configure a federated workload identity and grant only Search Index Data Reader on the search service and Cognitive Services OpenAI User on the OpenAI resource. Provisioning/ingestion permissions belong to a separate identity. No API keys are used. Confirm service networking and identity permissions before the live smoke test.

## Security and verification boundaries

JWT validation pins RS256, the tenant JWKS URL and issuer, exact audience, expiry/not-before/issued-at, v2 tenant, object identity, delegated scope and caller app. JWKS caches for five minutes, has a five-second network timeout and refreshes on unknown signing keys; signature/key-fetch failures deny access. Token headers cannot choose a key URL. Missing scope rejects ID tokens and app-only tokens. The test suite uses locally signed RSA tokens and mocks Azure, including claim failures, invalid signatures, key-fetch failure, caller identity spoofing, ACL enforcement, malformed input, content-filter/truncated/empty responses and sanitized failures.

CLI `answer_question("alice", ...)` and `hybrid_search("bob", ...)` remain for existing demo regression scripts only. The API constructs VerifiedIdentity from the validator and accepts neither usernames nor groups in its request schema. Retrieval applies ACL prefilters in every search mode and rechecks returned document ACLs before model use. VerifiedIdentity is an internal Python context, not a cryptographic capability for arbitrary code running in-process.

Audit events retain pseudonymous tenant/object IDs, document IDs, outcomes and fixed reason codes; they omit prompts, document contents, answers and bearer tokens. Protect log access and retention. Keep SDK wire/body debug logging disabled. Disable proxy request-body and authorization-header logging. Model answers are plain untrusted text: any UI must escape HTML and avoid interpreting generated commands/links. Grounding prompts and citation instructions do not prove factual correctness or eliminate prompt injection.

Offline checks do not validate tenant registration, actual group issuance, RBAC, live model behavior or network access. With real configuration, acquire a delegated access token through your client and verify finance and employees users separately, then run the existing opt-in live scripts from app/ingestion (`python src/test_rag_security.py`, `python src/test_document_injection.py`). They incur Azure calls and require the original synthetic documents. Existing live scripts are preserved and are not part of the offline pytest invocation.

References: [Microsoft claims validation](https://learn.microsoft.com/en-us/entra/identity-platform/claims-validation), [access-token claims](https://learn.microsoft.com/en-us/entra/identity-platform/access-token-claims-reference), [PyJWT API](https://pyjwt.readthedocs.io/en/stable/api.html).
