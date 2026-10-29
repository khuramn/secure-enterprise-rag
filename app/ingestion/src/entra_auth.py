
import os
from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError


TENANT_ID = os.environ["ENTRA_TENANT_ID"]
API_CLIENT_ID = os.environ["ENTRA_API_CLIENT_ID"]

FINANCE_GROUP_ID = os.environ["ENTRA_FINANCE_GROUP_ID"]
EMPLOYEES_GROUP_ID = os.environ["ENTRA_EMPLOYEES_GROUP_ID"]

ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"

JWKS_URL = (
    f"https://login.microsoftonline.com/{TENANT_ID}"
    "/discovery/v2.0/keys"
)

REQUIRED_SCOPE = "Rag.Query"

GROUP_MAPPING = {
    FINANCE_GROUP_ID: "finance-team",
    EMPLOYEES_GROUP_ID: "employees",
}

bearer_scheme = HTTPBearer(auto_error=False)
jwks_client = PyJWKClient(JWKS_URL)


@dataclass(frozen=True)
class AuthenticatedUser:
    user_id: str
    tenant_id: str
    groups: tuple[str, ...]


def unauthorized(message: str):
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden(message: str):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message,
    )


def validate_access_token(token: str) -> AuthenticatedUser:
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=API_CLIENT_ID,
            issuer=ISSUER,
            options={
                "require": [
                    "exp",
                    "iat",
                    "nbf",
                    "iss",
                    "aud",
                    "tid",
                    "oid",
                    "ver",
                ],
            },
            leeway=60,
        )

    except (InvalidTokenError, ValueError) as exc:
        unauthorized("Invalid or expired access token")
    except Exception:
        unauthorized("Token validation unavailable")

    if claims.get("ver") != "2.0":
        unauthorized("Unsupported token version")

    if claims.get("tid") != TENANT_ID:
        unauthorized("Invalid tenant")

    scopes = claims.get("scp", "").split()

    if REQUIRED_SCOPE not in scopes:
        forbidden("Required Rag.Query scope is missing")

    # Reject group overage rather than silently granting
    # access based on incomplete group information.
    if claims.get("hasgroups") or claims.get("_claim_names", {}).get("groups"):
        forbidden("Group membership requires secure resolution")

    token_groups = claims.get("groups")

    if not isinstance(token_groups, list):
        forbidden("Group membership claims are missing")

    if not all(isinstance(group, str) for group in token_groups):
        forbidden("Invalid group claims")

    allowed_groups = tuple(
        sorted(
            {
                GROUP_MAPPING[group_id]
                for group_id in token_groups
                if group_id in GROUP_MAPPING
            }
        )
    )

    if not allowed_groups:
        forbidden("User has no authorized RAG groups")

    return AuthenticatedUser(
        user_id=claims["oid"],
        tenant_id=claims["tid"],
        groups=allowed_groups,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> AuthenticatedUser:
    if credentials is None:
        unauthorized("Bearer access token required")

    return validate_access_token(credentials.credentials)
