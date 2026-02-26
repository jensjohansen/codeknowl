# Engineering Standards: Coding Standards & Definition of Done (CodeKnowl)

## Purpose
This document defines repository-wide coding standards and Definition of Done (DoD) requirements for CodeKnowl.

---

## Automated CI Quality Gates

1. No linting errors from Ruff (Python).
2. Rust code must pass `cargo fmt --check` and `cargo clippy` with no warnings.
3. TypeScript code for the VS Code extension must pass linting and typechecking when present.
4. Unit tests all pass.
5. Integration or end-to-end tests requiring real-world connections to services outside the code are marked appropriately so CI doesn't try to run them as unit tests.
6. Target 80% code coverage for the core indexing and retrieval logic.
7. Security-oriented static checks are enabled where appropriate for the languages in use (e.g., Bandit for Python, Rust dependency audits).
8. Code complexity <= 10 for new/modified Python code.
9. Rust dependency audits are clean (e.g., `cargo audit`/`cargo deny` if enabled in CI).

| Gate | Applies to |
| --- | --- |
| Ruff lint | Python |
| rustfmt + clippy | Rust |
| ESLint + typecheck | TypeScript (VS Code extension) |
| Tests | All |

---

## Manual Coding Standards (Python and Rust)

1. No abbreviations in variable names. The code should read like a narrative; non-programmers should be able to follow the general logic.
2. Every method that can be imported from the module requires doc comments (e.g., docstrings or Rust doc comments `///`) that explain:
   - what it is,
   - why an importing module would use it,
   - and (when appropriate) links to supporting documentation like release notes.
   - A single supporting link is acceptable at the module level if it applies to the entire module.
3. Do not introduce non-permissive license dependencies for the open-source offering.
   - CodeKnowl is MIT-licensed.
   - If a tool/library is not redistributable-safe for the OSS posture, it must be excluded.
   - Third-party notices must be updated as needed in `THIRD_PARTY_NOTICES.md`.
4. To encourage simplicity, files should be kept to 1200 lines of code or fewer. Larger files require management approval.

```mermaid
flowchart LR
  Plan[Plan change] --> Implement[Implement]
  Implement --> Test[Tests]
  Test --> Review[Review]
  Review --> Merge[Merge]
  Merge --> Track[Update tracker]
```

---

## Rust-Specific Standards

1. Formatting: Rust code must be formatted with `rustfmt`.
2. Clippy: no warnings; prefer fixing at the source over allow-listing.
3. Error handling: avoid `unwrap()`/`expect()` in production code. Use `Result` and map errors to domain errors.
4. Unsafe: `unsafe` is prohibited unless explicitly reviewed and documented with a justification comment.
5. Ownership: avoid unnecessary cloning; prefer borrowing. Use `Arc`/`Mutex` only when required and document shared-state usage.
6. Async: avoid blocking inside async contexts. When using a runtime inside sync methods, document why and keep blocking sections minimal.
7. Logging/observability: error paths must log actionable context (error + identifiers) without leaking secrets.
8. Public APIs: document public structs/functions with `///` doc comments and include examples when helpful.
9. Tests: new behavior requires Rust unit tests or integration tests where appropriate.

---

## Python-Specific Standards

1. Formatting/linting: Ruff is the source of truth. Avoid suppressions; fix root causes.
2. Typing: add type hints to all public functions and data structures. Use `from __future__ import annotations` where needed.
3. Exceptions: raise explicit, typed exceptions with clear messages; avoid bare `except:`.
4. Resource handling: use context managers for files and network resources.
5. Serialization: all JSON boundaries must validate and sanitize inputs.
6. Logging: error paths must log actionable context (error + identifiers) without leaking secrets.
7. Tests: new behavior requires Python unit tests or integration tests where appropriate.

8. Evidence and citations: when implementing code-understanding features, ensure the system can always trace results back to:
   - repository
   - snapshot (commit hash)
   - file path and line ranges

---

## TypeScript / VS Code Extension Standards

1. Language: VS Code extension code is written in TypeScript.
2. Formatting/linting: enforce a single formatter/linter configuration for the extension and avoid suppressions; fix root causes.
3. Types: avoid `any` in new code; prefer explicit types and narrow unions.
4. VS Code API usage:
   - never block the extension host event loop with long-running work
   - delegate indexing and heavy operations to the backend services
   - all backend calls must have timeouts and clear user-facing error messages
5. Telemetry: do not add default-on external telemetry.
6. Secrets: do not log tokens, credentials, file contents, or PII.
7. UI scope:
   - default to minimal UI (commands + chat + clickable citations)
   - Webview UI is allowed only when necessary for UX; keep it simple
   - React is a parking-lot choice unless explicitly adopted for a specific UX milestone
8. Testing:
   - add tests for command wiring and key flows where feasible
   - ensure citation links and file navigation behave correctly for representative paths

---

## Additional Recommended Standards (Commonly Missed)

These are not intended to add process overhead; they are here to prevent common production and security failures.

1. Dependency hygiene
   - Pin and review dependency changes.
   - Ensure dependency vulnerability scanning is enabled via redistributable tooling where appropriate.

2. Secrets and credentials
   - Never commit secrets.
   - Ensure code does not log credentials, tokens, or sensitive PII.

3. Backwards compatibility and migrations
   - When changing API or storage schemas, ensure backwards compatibility for consumers or provide a migration/bridge plan.
   - Any data migrations must have a documented rollback strategy.

4. Observability requirements for production changes
   - New or changed pipeline behavior must include appropriate logging and metrics.
   - Error paths must be observable and actionable (clear error messages + diagnostic fields).

5. Deterministic behavior and reproducibility
   - Prefer deterministic parsing and precedence rules (documented in PRDs) and add tests to lock behavior.

---

## Definition of Done (DoD)

1. The relevant PRD milestone acceptance criteria are satisfied (see `docs/prd-revised.md`).
2. The change is consistent with the Architecture & Design doc (see `docs/architecture-and-design.md`) or the deviation is documented.
3. The relevant items in the implementation tracker are updated (see `docs/implementation-plan-tracker.md`).
4. Tests added/updated to cover the change.
5. No secrets are introduced.
6. The OSS packaging stance is preserved for MVP:
   - source code only
   - no bundled scanner binaries
   - no official Docker images

| DoD area | Check |
| --- | --- |
| Product | PRD milestone acceptance criteria satisfied |
| Design | Consistent with Architecture & Design doc (or deviation documented) |
| Planning | Implementation tracker updated |
| Quality | Tests updated and passing |
| Security | No secrets introduced |
| OSS posture | Packaging stance preserved |
