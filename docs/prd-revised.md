# CodeKnowl: Product Requirements Document (PRD) — Revised (No ITDs)

## 1. Overview

CodeKnowl is an on-prem, local-first “codebase analyst” product. Given one or more Git repositories, CodeKnowl ingests source code and maintains:

- A **structural relationship store** for code entities and relationships (e.g., files, symbols, call relationships, dependencies).
- A **knowledge base** suitable for retrieval, summarization, and analyst workflows.

CodeKnowl exposes an AI Software Analyst experience to end users primarily through an IDE extension, with optional CI-oriented workflows, designed to operate without required cloud dependencies (beyond access to Git hosts).

This PRD is expected to evolve as implementation proceeds through MVP and v1 deliverables. When new features, constraints, or better technical alternatives are discovered, the change-management process is:

1. Add the discovered features or technical alternatives to the core documents (PRD, Architecture & Design, and Implementation Plan).
2. Review all milestones marked as Done to determine whether deliverables must be revisited based on the change; if so, add the required work items to the tracker.
3. Complete any required backfill work for previously completed milestones before resuming the milestone that was in progress when the change was introduced.

### 1.1 At a glance

| Area | Summary |
| --- | --- |
| Primary user experience | IDE-first (initially VS Code) Q&A with citations and navigation |
| Primary outputs | Evidence-grounded answers, navigable relationships, and indexed snapshots |
| Core stores | Structured relationship store + semantic index |
| Operating posture | On-prem, local-first; no required cloud runtime dependencies |
| OSS posture | MIT-licensed project with permissive, redistribution-safe dependencies |

```mermaid
flowchart TB
  IDE[IDE Extension] -->|Questions / Navigation| API[Backend API]
  API -->|Submit jobs| JOBS[Indexing Jobs]
  JOBS --> ING[Ingestion]
  JOBS --> PIPE[Indexing / Analysis]
  PIPE --> GRAPH[Structured Relationship Store]
  PIPE --> VEC[Semantic Index]
  API -->|Retrieve evidence| GRAPH
  API -->|Retrieve evidence| VEC
  API -->|Answer w/ citations| IDE
```

## 2. Problem Statement

Teams need fast, trustworthy answers about their codebases:

- What does this module do?
- Where is a given behavior implemented?
- What are the dependencies / call chains / data flows?
- What will likely break if I change this function?
- How do I onboard a new engineer quickly?

Cloud-based code assistants are often not viable due to:

- Compliance / data residency requirements
- IP protection concerns
- Latency, cost, and reliability constraints

## 3. Goals and Non-Goals

### 3.1 Goals

- Ingest one or more Git repositories and build a persistent, queryable representation of the codebase.
- Maintain an up-to-date relationship store and knowledge base as new commits land on the default branch.
- Provide interactive “code analyst” experiences inside the IDE.
- Support multiple Git hosting providers.
- Favor local-first operation, with no required runtime cloud dependency other than reaching Git remotes.
- Be viable as an MIT-licensed open-source project, including a recommended on-prem deployment and sizing story.

### 3.2 Non-Goals (initial releases)

- Building a fully managed SaaS offering.
- Building a general-purpose “chat with your company” product beyond code analysis.
- Perfect language coverage for all languages on day one.
- Guaranteeing complete correctness of all AI responses (focus is on traceability and citations rather than perfection).

## 4. Target Users

- **Software engineers** working in medium-to-large codebases.
- **Tech leads / architects** performing dependency analysis and refactoring planning.
- **Security and compliance teams** requiring on-prem operation.
- **SRE / platform engineers** who maintain developer tooling and internal platforms.

## 5. User Experience (UX) and Primary Workflows

### 5.1 IDE extension (primary interface)

Core workflows:

- **Ask questions with citations**
  - Natural language queries about code.
  - Responses include links/locations back to source and/or relationship paths.

- **Navigate code relationships**
  - Jump from symbol to dependents/callers/callees.
  - View high-level module summaries.

- **Impact analysis**
  - “If I change X, what might break?”
  - Uses relationship traversal + indexed references.

- **(Optional) Agentic coding workflows (guardrailed)**
  - Multi-step tasks (search, plan, propose changes) executed locally.
  - Strong controls: require confirmation before changes.

### 5.2 Repository onboarding workflow

- Register one or more repositories with CodeKnowl.
- MVP onboarding input is an already-cloned local checkout path (local-first).
- Run initial indexing.
- Verify indexing status and health.

### 5.3 Repository off-boarding workflow

- Remove a repository from CodeKnowl so it is no longer queryable.
- Off-boarding must be explicit and operator-driven (no automatic removal).
- The system must support re-adding the repository later.
- Off-boarding must support migration scenarios (e.g., Bitbucket to GitLab, monorepo split into smaller repos) where operators replace repositories over time.

### 5.4 Continuous update workflow

- Detect new commits merged into the default branch.
- Incrementally update:
  - the relationship store
  - the knowledge base (including semantic indexes)
- Provide status and alerting when indexing fails.

```mermaid
sequenceDiagram
  participant U as User (IDE)
  participant A as Backend API
  participant R as Retrieval
  participant L as LLM
  U->>A: Ask question (repo-scoped)
  A->>R: Retrieve evidence (semantic + traversal)
  R-->>A: Evidence bundle (citations)
  A->>L: Generate answer constrained to evidence
  L-->>A: Answer text + references
  A-->>U: Render answer with clickable citations
```

## 6. Functional Requirements

### 6.1 Repository ingestion

- Support adding multiple repos.
- Support Git providers (initial):
  - GitHub
  - GitLab
  - Bitbucket
  - Gitea
  - “Generic Git” via clone URL
- Support multiple auth methods for Git access (initial):
  - personal access tokens
  - SSH keys
- Support air-gapped / offline operation except for Git access.

MVP note:
- For Milestones 0–2, CodeKnowl onboards repositories by local filesystem path to an existing clone.
- URL onboarding (clone/pull without CodeKnowl-managed credentials) is deferred to a later milestone.
  - Decision note: we explicitly do not request or store Git credentials inside CodeKnowl.
  - Discover-and-register workflow supersedes “manual onboarding” by deriving repo metadata (accepted branch, preferred remote) from the local checkout and asking the user to confirm.

#### 6.1.1 Repository off-boarding

- Support removing a repository from the index so it is no longer queryable.
- Off-boarding must have a clear scope and behavior:
  - remove from active query scope and listing
  - prevent future queries from returning results for the off-boarded repo
  - define whether stored artifacts are deleted or retained (implementation-specific), but the behavior must be documented and operator-visible
- Support re-onboarding a previously off-boarded repository.

### 6.2 Indexing and analysis

- Build and maintain a **structured representation of code** suitable for deterministic relationship queries (e.g., symbols, containment, calls/imports/references where feasible).
- Maintain a **knowledge base** suitable for retrieval-augmented generation (RAG).
- Support incremental updates on new commits.

#### 6.2.1 Minimum bar

- Support hybrid retrieval:
  - semantic retrieval over code/text
  - relationship traversal retrieval over the structured representation
- Support hybrid search experiences (not only semantic search):
  - deterministic symbol navigation (definitions/references) where feasible
  - regex/text search for “find all occurrences” workflows
- Provide first-class citations in all answers:
  - file path
  - line ranges
  - symbol identity (where applicable)
- Support an incremental re-index strategy:
  - detect changed files and update derived indexes without full re-ingest
- Support per-repo isolation in storage and indexing (avoid cross-contamination between repos by default).

#### 6.2.2 Competitor parity requirements

- Multi-repo indexing and navigation:
  - support indexing and querying across multiple repositories
  - preserve repo-level boundaries and allow users to scope queries to a repo
- Access control alignment (enterprise expectations):
  - repository-level access control
  - audit logging for security and compliance review
- Report-oriented outputs:
  - generate standard “codebase understanding” reports (summary, dependency highlights, risk areas)
  - results must be reproducible and traceable (citations + stored query inputs)

### 6.3 Data storage and retrieval services (capabilities)

CodeKnowl must provide the following storage capabilities (implementation choices are captured in the ITD register):

- A **relationship store** for structured queries and traversals across code entities.
- A **semantic index** for vector-based retrieval.
- A **document store** (or equivalent capability) for persisted artifacts such as:
  - indexing metadata
  - extracted facts
  - prompts/queries (for reproducibility)
  - audit events

### 6.4 Local models / inference (capabilities)

CodeKnowl must support fully on-prem inference for the following model roles:

- A **general-purpose LLM**
  - Used for summarization, explanation, and non-coding analyst tasks.
- A **coding-specialized LLM**
  - Used for code-aware Q&A, impact analysis narratives, and optional agentic coding workflows.
- A **synthesizer LLM**
  - Used to merge and reconcile multiple model outputs into a single, high-quality answer grounded in a shared evidence bundle.
- An **embeddings model**
  - Used to embed code and related text for semantic retrieval.
- A **reranking model**
  - Used to improve retrieval precision/ordering for top candidate contexts.

Requirements:

- All model roles must be runnable without required external network calls.
- The system must allow **model routing** by task type (coding vs general vs embedding vs rerank).
- For evidence-grounded Q&A, the system must support a **multi-model synthesis pipeline**:
  - retrieve evidence once (semantic + structured)
  - generate candidate answers using multiple LLM roles (e.g., coding + general)
  - synthesize a final answer using a synthesizer model that resolves conflicts and preserves citations
- The system must support swapping models over time without breaking external APIs (stable contracts for:
  - chat completion
  - embeddings
  - reranking)

### 6.5 IDE extension requirements

- Provide a chat-style interface.
- Provide commands for:
  - “Index current workspace/repo”
  - “Search symbol / relationship”
  - “Explain file/module”
  - “Impact analysis”
- Provide citations (file paths + line ranges) for answers.

#### 6.5.1 Optional agentic change workflow (guardrailed)

- When proposing code changes, CodeKnowl must:
  - present a diff/preview
  - require explicit user approval before writing to disk
- When running commands (tests/linters/builds), CodeKnowl must:
  - require explicit user approval before execution
  - capture command output as part of the task trace

### 6.6 Administration / observability

- Show indexing state per repository:
  - last indexed commit
  - last successful run time
  - errors and retries
- Provide operator controls for repository lifecycle:
  - onboard/register
  - trigger indexing
  - off-board/remove
- Provide basic health endpoints and metrics.
- Provide an operator-friendly deployment and sizing story:
  - document instance sizing guidance for common deployment sizes
  - provide resource estimates for indexing workloads

## 7. Quality Attributes (Non-Functional Requirements)

- **On-prem first**: no required cloud dependency beyond Git remote access.
- **Performance**: incremental updates should be faster than full re-index.
- **Scalability**: support multiple repos; ability to scale ingestion/indexing workers.
- **Reliability**: resilient to indexing failures; retry and resume.
- **Security**:
  - secure storage of Git credentials
    - Decision note: CodeKnowl does not store Git credentials; Git access (if/when required) relies on operator-managed system configuration (e.g., SSH agent, git credential helper).
  - least-privilege principles
  - local network-only by default
- **Traceability**: answers should cite sources; relationship queries should be inspectable.

## 7.1 Assumptions and Constraints

- CodeKnowl must have a credible recommended deployment configuration that balances cost and performance for on-prem buyers.
- The system must operate without required cloud dependencies beyond access to Git repositories.
- The project should remain viable as an MIT-licensed open-source solution.

## 8. Architecture (Conceptual)

### 8.1 Core components (capabilities)

- **Ingestion service**
  - MVP: reads from an already-cloned local checkout
  - resolves snapshots (commit hash) and tracks last indexed commit
  - URL onboarding (clone/pull without CodeKnowl-managed credentials) and remote update detection are deferred to a later milestone
    - Decision note: CodeKnowl must not request or store Git credentials; any clone/pull would rely on operator-managed system Git authentication.

- **Analysis/indexing pipeline**
  - parsing, symbol extraction
  - relationship extraction
  - chunking + embedding
  - indexing + incremental updates

- **Structured relationship service**
  - supports traversal queries for impact analysis and navigation

- **Semantic retrieval service**
  - vector search + optional reranking

- **Model services**
  - general LLM
  - coding LLM
  - embeddings
  - reranker

- **Developer interface**
  - IDE extension
  - optional admin UI

## 9. Buy vs Build Evaluation

CodeKnowl should include a structured buy-vs-build assessment early.

Evaluation criteria:

- On-prem support and licensing
- Extensibility (structured relationships + RAG + IDE integration)
- Total cost (license + hardware)
- Data residency/compliance
- Ability to integrate local models and local stores

Deliverable:

- A short comparison document and a recommendation (continue building vs adopt/extend an existing tool).

## 10. Release Plan (Milestones)

### Milestone 0: PRD + architecture baseline

- revised PRD approved
- initial architecture diagram + component boundaries
- buy-vs-build evaluation plan created
- coding standards and Definition of Done (DoD) documented
- CI quality gates scaffolded for backend and IDE extension

Acceptance criteria:
- The revised PRD is approved by product stakeholders.
- A high-level component diagram exists and is understandable by non-engineering stakeholders.
- The buy-vs-build evaluation plan clearly defines evaluation criteria, comparison scope, and decision owners.
- Coding standards and milestone DoD expectations are written down and applied consistently.
- CI runs the minimum quality gates for the MVP components (lint, typecheck, and tests/smoke where applicable).

### Milestone 1: Single-repo indexing MVP

- ingest one repo
- generate basic structured representation (files, symbols, imports, calls at minimum)
- simple query API (internal)
- basic CLI/API for repo lifecycle (register, list, index, status)
- repository off-boarding (operator-driven)

Acceptance criteria:
- Given a local filesystem path to an already-cloned git repository, the system can complete an initial indexing run and report completion.
- A user can ask at least:
  - “What does this file/module do?”
  - “Where is this function/symbol defined?”
  - “What calls this function?”
- Each answer includes citations to source locations (file path + line range).
- Index state is visible for the repo (last indexed commit and last successful run time).
- An operator can off-board a repository so it is no longer queryable.
- Backend smoke test(s) and CI gates are documented and pass for this milestone.

### Milestone 2: IDE extension MVP

- chat with citations
- explain file / symbol
- simple relationship navigation
- IDE-to-backend integration is validated via CI gates

Acceptance criteria:
- From within the IDE, a user can:
  - index the current repo/workspace (MVP: by registering the local filesystem path to an already-cloned repository)
  - ask a question and receive an answer with citations
  - request “explain file/module” and receive a summary with citations
  - navigate at least one relationship query (e.g., callers/callees/definitions) with clickable locations.
- The IDE experience clearly indicates indexing status and failure states.
- The VS Code extension passes linting, typechecking, and tests in CI.

### Milestone 3: Incremental updates

- build semantic index (chunks + embeddings + vector retrieval)
- detect and process new commits
- update relationship store + semantic index incrementally
- indexing status UI/commands

Acceptance criteria:
- After a new commit is merged to the default branch, the system updates its indexes without requiring a full re-index.
- The system surfaces indexing failures and retry status in a user-visible way.
- A user can verify that answers reflect the latest indexed commit.

### Milestone 4: Multi-repo support + hardening

- multiple repos
- access control for repos
- observability + reliability improvements

Acceptance criteria:
- A user can add and index multiple repositories and scope queries to a selected repo.
- Access to repositories is enforced (users cannot query repos they are not authorized to access).
- Operators can observe:
  - indexing throughput and failures
  - system health status
- The system meets a defined reliability target for indexing jobs over a representative time window.

### Milestone 5: Durable job queue + workers

- Move indexing/update workloads into a durable job queue with retries.
- Keep HTTP endpoints as thin job enqueuers with status polling.

Acceptance criteria:
- Indexing and update operations run asynchronously via a worker queue and are retryable.
- Job status and failure reasons are visible to operators.

### Milestone 6: Observability stack alignment

- Align metrics/logs export for Loki + Prometheus/Grafana.
- Provide operator guidance for dashboards/alerts.

Acceptance criteria:
- Metrics and logs are exportable/consumable by the chosen observability stack.
- Operator runbook documents how to observe indexing throughput, failures, and job lag.

### Milestone 7: Graph relationship store (NebulaGraph)

- Implement the structured relationship store in NebulaGraph (nGQL) for traversal queries.

Acceptance criteria:
- Structured entities/edges are persisted in the graph store and queryable for relationship navigation.

### Milestone 8: Findings ingestion (scanner integrations)

- Ingest scanner outputs (e.g., SARIF/JSON) as optional enrichment linked to repos/snapshots.

Acceptance criteria:
- Findings can be ingested and queried by repo/snapshot with traceable file/location links.

### Milestone 9: Admin UI + non-engineer access

- Provide a basic web UI for operators and non-engineers to access repo status and Q&A.

Acceptance criteria:
- Operators can manage repo lifecycle and view indexing status via a web UI.
- Non-engineers can access Q&A with citations via a web UI (within authorized scope).

### Milestone 10: URL onboarding (no credential storage)

- Optional repo onboarding by clone URL, without CodeKnowl requesting or storing Git credentials.

Acceptance criteria:
- Repos can be registered by URL and (if/when clone/pull is implemented) Git authentication relies on operator-managed system Git configuration.

### Milestone 11: Optional agentic workflows (guardrailed)

- Add multi-step agentic workflows that propose changes and require explicit user approval.

Acceptance criteria:
- Proposed code changes are shown as diffs/previews and require explicit approval before writing.
- Any command execution requires explicit approval and captured output.

### 10.1 Milestone summary (table)

| Milestone | Theme | User-visible outcome |
| --- | --- | --- |
| 0 | Baseline docs | PRD + architecture baseline and buy-vs-build plan |
| 1 | Single-repo indexing | Index one repo, answer core questions with citations |
| 2 | IDE extension MVP | IDE chat + explain + basic relationship navigation |
| 3 | Incremental updates | Keep indexes fresh as commits land |
| 4 | Multi-repo + hardening | Multiple repos, access control, reliability/observability |
| 5 | Job queue + workers | Durable indexing/update jobs with retries and operator-visible status |
| 6 | Observability alignment | Prometheus/Grafana + Loki-aligned metrics/logs and operator guidance |
| 7 | Graph store integration | NebulaGraph-backed structured relationship storage and traversal queries |
| 8 | Findings ingestion | Scanner findings ingested and linked to snapshots with citations |
| 9 | Admin + non-engineer UI | Web UI for operators and non-engineers (authorized) |
| 10 | URL onboarding | Register by URL; no CodeKnowl credential storage |
| 11 | Agentic workflows | Guardrailed multi-step workflows with explicit approvals |

```mermaid
gantt
  title CodeKnowl release plan (conceptual)
  dateFormat  YYYY-MM-DD
  axisFormat  %b
  section Milestones
  Milestone 0 (baseline) :m0, 2026-01-01, 14d
  Milestone 1 (single-repo) :m1, after m0, 28d
  Milestone 2 (IDE MVP) :m2, after m1, 28d
  Milestone 3 (incremental) :m3, after m2, 28d
  Milestone 4 (multi-repo) :m4, after m3, 28d
  Milestone 5 (jobs) :m5, after m4, 28d
  Milestone 6 (observability) :m6, after m5, 28d
  Milestone 7 (graph store) :m7, after m6, 28d
  Milestone 8 (findings) :m8, after m7, 28d
  Milestone 9 (web UI) :m9, after m8, 28d
  Milestone 10 (URL onboarding) :m10, after m9, 28d
  Milestone 11 (agentic) :m11, after m10, 28d
```

## 11. Success Metrics

- **Time-to-first-answer** after indexing completes.
- **Index freshness**: time from commit merge to updated indexes.
- **User satisfaction**: usefulness of answers + accuracy with citations.
- **Adoption**: number of active IDE users per deployment.
- **Reliability**: indexing job success rate.

## 12. Risks and Mitigations

- **Language coverage risk**
  - Mitigation: start with a limited set of languages; expand iteratively.

- **Correctness risk (relationships and citations)**
  - Mitigation: prioritize deterministic parsing and citations; make AI-derived relationships clearly marked.

- **Performance on limited hardware**
  - Mitigation: task routing, batching, incremental indexing, configurable embeddings/reranking.

- **Security of credentials**
  - Mitigation: support enterprise identity integration; secure secret storage.

## 13. Open Questions

The following items were previously open questions. They are now captured as the current plan/intent and can be revised as research and implementation proceeds.

- MVP language set:
  - MVP indexing and deterministic relationship extraction will target: Python, JavaScript, TypeScript, Java.
  - Additional languages (e.g., Go, Rust, etc.) are deferred until after the MVP proves end-to-end value.
- Authoritative schema for structured relationships:
  - We do not expect to define a fully authoritative schema upfront.
  - The schema will evolve incrementally as we incorporate analysis/extraction tools, with explicit versioning and provenance, extending the internal representation as needed.
- Multi-tenant / multi-team access model:
  - Deferred for now.
  - Deployment expectation: CodeKnowl services will run inside a Kubernetes cluster and be reachable by IDE extensions via an operator-managed ingress pattern (e.g., Cloudflare Tunnel or equivalent).
- “Agentic” roadmap scope:
  - MVP: ask questions about the codebase with citations and traceability.
  - Later versions: recommend refactors for security, scalability, performance, and anti-pattern/design-pattern alignment.
  - Long-term: extract business rules and architectural patterns, produce PRD-like artifacts, and enable re-implementation against alternative ITDs/tech stacks for major scale shifts (e.g., replacing a Java monolith with an HTAP/event pipeline architecture to support 100x–1000x event volume).
- Packaging / installation:
  - VS Code extension will be packaged and distributed through the standard VS Code mechanism.
  - Backend/services will target Kubernetes deployments, with Helm charts as the primary packaging mechanism; consider an operator pattern (deployed by Helm) where instances are managed by CRDs.

## 14. Parking Lot (Post-MVP / Post-v1)

- Higher-order agent workflows:
  - “How should we scale this system to handle 100x more events?” style multi-step architecture reasoning.
  - Organization-level refactoring and modernization planning workflows.
