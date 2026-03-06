"""File: backend/src/codeknowl/auth.py
Purpose: Provide Keycloak OIDC authentication + simple, operator-configurable authorization.
Product/business importance: Enables Milestone 4 access control using ITD-04 (Keycloak) without hardcoding
customer policy decisions in CodeKnowl.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
import jwt


@dataclass(frozen=True)
class AuthContext:
    subject: str
    username: str | None
    groups: set[str]


@dataclass(frozen=True)
class OidcConfig:
    issuer_url: str
    audience: str | None

    @staticmethod
    def from_env(env: dict[str, str]) -> "OidcConfig | None":
        mode = env.get("CODEKNOWL_AUTH_MODE", "").strip().lower()
        if mode not in {"oidc", "keycloak"}:
            return None

        issuer_url = env.get("CODEKNOWL_OIDC_ISSUER_URL", "").strip().rstrip("/")
        if not issuer_url:
            raise ValueError("CODEKNOWL_OIDC_ISSUER_URL is required when CODEKNOWL_AUTH_MODE=oidc")

        aud = env.get("CODEKNOWL_OIDC_AUDIENCE")
        aud = aud.strip() if aud else None
        return OidcConfig(issuer_url=issuer_url, audience=aud)


@dataclass(frozen=True)
class GroupAuthzConfig:
    group_prefix: str
    read_suffix: str
    write_suffix: str
    admin_group: str

    @staticmethod
    def from_env(env: dict[str, str]) -> "GroupAuthzConfig":
        prefix = env.get("CODEKNOWL_AUTHZ_GROUP_PREFIX", "/codeknowl/repos").strip().rstrip("/")
        read_suffix = env.get("CODEKNOWL_AUTHZ_READ_SUFFIX", "read").strip().strip("/")
        write_suffix = env.get("CODEKNOWL_AUTHZ_WRITE_SUFFIX", "write").strip().strip("/")
        admin_group = env.get("CODEKNOWL_AUTHZ_ADMIN_GROUP", "/codeknowl/admin").strip()
        return GroupAuthzConfig(
            group_prefix=prefix,
            read_suffix=read_suffix,
            write_suffix=write_suffix,
            admin_group=admin_group,
        )


class OidcVerifier:
    def __init__(
        self,
        *,
        cfg: OidcConfig,
        http_timeout_seconds: float = 5.0,
        cache_ttl_seconds: float = 300.0,
    ):
        self._cfg = cfg
        self._http_timeout_seconds = http_timeout_seconds
        self._cache_ttl_seconds = cache_ttl_seconds

        self._discovery_cached_at: float | None = None
        self._discovery: dict[str, Any] | None = None

        self._jwks_cached_at: float | None = None
        self._jwks: dict[str, Any] | None = None

    def _now(self) -> float:
        return time.time()

    def _http_get_json(self, url: str) -> dict[str, Any]:
        resp = httpx.get(url, timeout=self._http_timeout_seconds)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError(f"unexpected JSON from {url}")
        return data

    def _get_discovery(self) -> dict[str, Any]:
        if (
            self._discovery
            and self._discovery_cached_at
            and (self._now() - self._discovery_cached_at) < self._cache_ttl_seconds
        ):
            return self._discovery

        doc = self._http_get_json(f"{self._cfg.issuer_url}/.well-known/openid-configuration")
        self._discovery = doc
        self._discovery_cached_at = self._now()
        return doc

    def _get_jwks(self) -> dict[str, Any]:
        if self._jwks and self._jwks_cached_at and (self._now() - self._jwks_cached_at) < self._cache_ttl_seconds:
            return self._jwks

        discovery = self._get_discovery()
        jwks_uri = discovery.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise ValueError("OIDC discovery document missing jwks_uri")

        jwks = self._http_get_json(jwks_uri)
        self._jwks = jwks
        self._jwks_cached_at = self._now()
        return jwks

    def _find_jwk_by_kid(self, jwks: dict[str, Any], *, kid: str) -> dict[str, Any] | None:
        keys = jwks.get("keys")
        if not isinstance(keys, list):
            raise ValueError("invalid JWKS")
        for k in keys:
            if isinstance(k, dict) and k.get("kid") == kid:
                return k
        return None

    def _get_jwk_for_kid(self, *, kid: str) -> dict[str, Any]:
        jwks = self._get_jwks()
        jwk = self._find_jwk_by_kid(jwks, kid=kid)
        if jwk is not None:
            return jwk

        # Refresh once in case of key rotation.
        self._jwks_cached_at = None
        jwks = self._get_jwks()
        jwk = self._find_jwk_by_kid(jwks, kid=kid)
        if jwk is None:
            raise ValueError("unknown kid")
        return jwk

    def _decode_and_validate(self, token: str, *, public_key) -> dict[str, Any]:
        options = {
            "verify_signature": True,
            "verify_exp": True,
            "verify_aud": self._cfg.audience is not None,
            "verify_iss": True,
        }

        try:
            claims = jwt.decode(
                token,
                key=public_key,
                algorithms=["RS256"],
                audience=self._cfg.audience,
                issuer=self._cfg.issuer_url,
                options=options,
            )
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid token") from exc

        if not isinstance(claims, dict):
            raise ValueError("invalid token")
        return claims

    def _claims_to_ctx(self, claims: dict[str, Any]) -> AuthContext:
        sub = claims.get("sub")
        if not isinstance(sub, str) or not sub:
            raise ValueError("token missing sub")

        username = None
        preferred_username = claims.get("preferred_username")
        if isinstance(preferred_username, str) and preferred_username:
            username = preferred_username

        groups: set[str] = set()
        raw_groups = claims.get("groups")
        if isinstance(raw_groups, list):
            for g in raw_groups:
                if isinstance(g, str) and g:
                    groups.add(g)

        return AuthContext(subject=sub, username=username, groups=groups)

    def verify_bearer_token(self, token: str) -> AuthContext:
        try:
            header = jwt.get_unverified_header(token)
        except Exception as exc:  # noqa: BLE001
            raise ValueError("invalid token header") from exc

        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise ValueError("token missing kid")

        jwk = self._get_jwk_for_kid(kid=kid)
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(jwk)
        claims = self._decode_and_validate(token, public_key=public_key)
        return self._claims_to_ctx(claims)


def parse_bearer_token(authz_header: str | None) -> str | None:
    if not authz_header:
        return None
    raw = authz_header.strip()
    if not raw:
        return None
    if not raw.lower().startswith("bearer "):
        return None
    token = raw.split(" ", 1)[1].strip()
    return token or None


def group_for_repo(*, cfg: GroupAuthzConfig, repo_id: str, op: str) -> str:
    suffix = cfg.read_suffix if op == "read" else cfg.write_suffix
    return f"{cfg.group_prefix}/{repo_id}/{suffix}"


def is_admin(*, cfg: GroupAuthzConfig, ctx: AuthContext) -> bool:
    return cfg.admin_group in ctx.groups


def is_allowed_for_repo(*, cfg: GroupAuthzConfig, ctx: AuthContext, repo_id: str, op: str) -> bool:
    if is_admin(cfg=cfg, ctx=ctx):
        return True
    expected = group_for_repo(cfg=cfg, repo_id=repo_id, op=op)
    return expected in ctx.groups
