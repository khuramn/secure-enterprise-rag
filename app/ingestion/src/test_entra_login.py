
import os
import msal
import requests

TENANT_ID = os.environ["ENTRA_TENANT_ID"]
CLIENT_ID = os.environ["ENTRA_TEST_CLIENT_ID"]

API_SCOPE = (
    "api://267524de-f8ef-4c7d-8f4c-66ac04138598/Rag.Query"
)

AUTHORITY = (
    f"https://login.microsoftonline.com/{TENANT_ID}"
)

if __name__ == "__main__":
    client = msal.PublicClientApplication(
        client_id=CLIENT_ID,
        authority=AUTHORITY,
    )

    result = client.acquire_token_interactive(
        scopes=[API_SCOPE],
        port=8400,
        prompt="select_account",
    )

    if "access_token" not in result:
        print("Authentication failed")
        print("Error:", result.get("error"))
        print("Description:", result.get("error_description"))
        raise SystemExit(1)

    print("Microsoft Entra authentication successful")
    print("Access token received (not displayed)")
    import base64
    import json

    token_payload = result["access_token"].split(".")[1]
    token_payload += "=" * (-len(token_payload) % 4)

    claims = json.loads(
        base64.urlsafe_b64decode(token_payload)
    )

    print("Authenticated username:", claims.get("preferred_username"))
    print("Authenticated user ID:", claims.get("oid"))
    print("Token group count:", len(claims.get("groups", [])))
    print("Group overage:", "hasgroups" in claims or "_claim_names" in claims)
    response = requests.post(
        "http://127.0.0.1:8000/query",
        headers={
            "Authorization": (
                f"Bearer {result['access_token']}"
            )
        },
        json={
            "question": "What is the Q4 financial forecast?"
        },
        timeout=120,
    )

    print("HTTP status:", response.status_code)
    print("API response:", response.text)
