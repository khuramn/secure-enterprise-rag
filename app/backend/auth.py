"""Single-tenant, delegated v2 access tokens only. No token-directed URLs."""
import json
import os
from dataclasses import dataclass
from uuid import UUID

import jwt
from identity import VerifiedIdentity


def guid(value):
    if not isinstance(value, str):
        raise ValueError("Expected object ID")
    return str(UUID(value))


@dataclass(frozen=True)
class Settings:
    tenant: str
    audience: str
    scope: str
    clients: frozenset[str]
    group_map: dict[str, tuple[str, ...]]

    @classmethod
    def from_env(cls):
        tenant = guid(os.environ["ENTRA_TENANT_ID"])
        audience = guid(os.environ["ENTRA_API_CLIENT_ID"])
        clients = frozenset(guid(x.strip()) for x in os.environ["ENTRA_ALLOWED_CLIENT_IDS"].split(","))
        if audience in clients:
            raise ValueError("Use separate API and caller app registrations")
        scope = os.environ["ENTRA_REQUIRED_SCOPE"]
        if not scope or len(scope.split()) != 1:
            raise ValueError("Expected one delegated scope")
        raw = json.loads(os.environ["ENTRA_GROUP_ACL_MAP"])
        if not isinstance(raw, dict) or not raw:
            raise ValueError("Group mapping required")
        mapping = {}
        for key, labels in raw.items():
            if not isinstance(labels, list) or not labels or not all(isinstance(x, str) and x.strip() for x in labels):
                raise ValueError("Invalid ACL labels")
            mapping[guid(key)] = tuple(labels)
        return cls(tenant, audience, scope, clients, mapping)


class Forbidden(Exception):
    pass


class TokenValidator:
    def __init__(self, settings):
        self.settings = settings
        self.issuer = f"https://login.microsoftonline.com/{settings.tenant}/v2.0"
        self.keys = jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{settings.tenant}/discovery/v2.0/keys",
            timeout=5, lifespan=300,
        )

    def validate(self, token):
        if len(token) > 32768:
            raise jwt.InvalidTokenError("Invalid token")
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str) or not header["kid"]:
            raise jwt.InvalidTokenError("Invalid token header")
        key = self.keys.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=self.settings.audience,
                            issuer=self.issuer, options={"strict_aud": True, "require": [
                                "exp", "iat", "nbf", "iss", "aud", "tid", "oid", "sub", "ver", "azp"
                            ]})
        if claims["tid"] != self.settings.tenant or claims["ver"] != "2.0":
            raise jwt.InvalidTokenError("Invalid tenant or token version")
        try:
            oid = guid(claims["oid"])
        except ValueError as exc:
            raise jwt.InvalidTokenError("Invalid subject") from exc
        # ID tokens have no delegated scp; app-only tokens are also refused.
        scope = claims.get("scp")
        if not isinstance(scope, str) or self.settings.scope not in scope.split():
            raise Forbidden()
        if claims.get("idtyp") == "app" or claims["azp"] not in self.settings.clients:
            raise Forbidden()
        if "hasgroups" in claims or "_claim_names" in claims or "_claim_sources" in claims:
            raise Forbidden()
        groups = claims.get("groups")
        if not isinstance(groups, list) or not groups or len(groups) > 200:
            raise Forbidden()
        try:
            groups = [guid(g) for g in groups]
        except ValueError as exc:
            raise Forbidden() from exc
        labels = tuple(sorted({label for g in groups for label in self.settings.group_map.get(g, ())}))
        if not labels:
            raise Forbidden()
        return VerifiedIdentity(self.settings.tenant, oid, labels)
