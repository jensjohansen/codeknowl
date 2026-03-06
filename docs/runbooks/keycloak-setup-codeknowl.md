# Keycloak setup for CodeKnowl (Milestone 4)

This runbook describes how to configure Keycloak for CodeKnowl using the `ai-agents` realm and a `codeknowl` client.

## Summary

CodeKnowl uses:

- OIDC Bearer JWT authentication against the realm issuer.
- Group-based authorization based on the `groups` claim in the access token.

CodeKnowl does not decide your org’s security policy. You enforce policy in Keycloak by controlling which users are members of which groups.

## 1. Create the client

In realm `ai-agents`:

- Create a client with:
  - Client ID: `codeknowl`
  - Client type: OpenID Connect

Token type expectations:

- CodeKnowl validates tokens signed by the realm.
- CodeKnowl can optionally validate an `aud` claim.

## 2. Ensure the access token contains `groups`

CodeKnowl expects the access token to include a `groups` claim that is a JSON array of group paths, for example:

- `"groups": ["/codeknowl/admin", "/codeknowl/repos/<repo_id>/read"]`

Configure a protocol mapper so the token contains group membership.

## 3. Create groups for CodeKnowl

CodeKnowl’s default convention is:

- Admin group:
  - `/codeknowl/admin`
- Repo read access:
  - `/codeknowl/repos/<repo_id>/read`
- Repo write access:
  - `/codeknowl/repos/<repo_id>/write`

Where `<repo_id>` is the CodeKnowl repo identifier (UUID) returned by the backend on repo registration.

### Admin behavior

Users in `/codeknowl/admin` are allowed to:

- Register repos (`POST /repos`)
- Offboard repos (`DELETE /repos/{repo_id}`)

### Repo read behavior

Users in `/codeknowl/repos/<repo_id>/read` are allowed to:

- List the repo in `GET /repos`
- Run read-only QA endpoints under `/repos/{repo_id}/...`

### Repo write behavior

Users in `/codeknowl/repos/<repo_id>/write` are allowed to:

- Trigger indexing and updates for the repo (`/index`, `/update`)

## 4. Configure the CodeKnowl backend

Set these environment variables for the backend process:

- `CODEKNOWL_AUTH_MODE=oidc`
- `CODEKNOWL_OIDC_ISSUER_URL=https://auth.ai-agents.private/realms/ai-agents`
- `CODEKNOWL_OIDC_AUDIENCE=codeknowl` (recommended if your tokens include `aud=codeknowl`)

Optional (defaults shown):

- `CODEKNOWL_AUTHZ_GROUP_PREFIX=/codeknowl/repos`
- `CODEKNOWL_AUTHZ_READ_SUFFIX=read`
- `CODEKNOWL_AUTHZ_WRITE_SUFFIX=write`
- `CODEKNOWL_AUTHZ_ADMIN_GROUP=/codeknowl/admin`

## 5. Client fallback (optional)

If you also set `CODEKNOWL_API_KEY`, the backend will accept `X-CodeKnowl-Api-Key` as a fallback. Requests authorized by API key bypass group enforcement and are intended for operator use.
