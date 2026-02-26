# CodeKnowl — ITD Register (Important Technical Decisions)

## Purpose
This document tracks the major technical decisions (ITDs) for CodeKnowl and the status of each decision.

Status values:
- Completed: Decision made / direction chosen
- Pending: Not yet decided

## ITDs

### ITD-01 — Code representation pattern: Code Property Graph (CPG)
- Status: Completed
- Business problem:
  - The PRD requires impact analysis, dependency/call-chain navigation, and traceable “why” answers across large repos.
- Options considered:
  - Code Property Graph (CPG) (chosen)
  - Text-only RAG (chunks + embeddings only)
  - Pure symbol index (definitions/refs only)
- Chosen option:
  - Code Property Graph (CPG)
- Primary reason:
  - Enables deterministic, explainable traversal-based retrieval that supports traceability and impact analysis beyond what vector search alone can reliably provide.
- Impacts:
  - Requires an AST/semantic extraction strategy; drives graph schema decisions; drives choice of graph database and query layer.

### ITD-02 — Primary UX surface: VS Code extension
- Status: Completed
- Business problem:
  - The PRD requires interactive code understanding inside developers’ primary environment.
- Options considered:
  - VS Code extension (chosen)
  - Web-only UI
- Chosen option:
  - VS Code extension
- Primary reason:
  - Maximizes adoption by meeting developers where they already work, enabling citations and navigation workflows directly in-editor.
- Impacts:
  - Requires stable backend APIs, streaming responses, and symbol/citation navigation contracts.

### ITD-03 — API framework: BlackSheep
- Status: Completed
- Business problem:
  - We need a high-performance API layer for VS Code and admin workflows.
- Options considered:
  - BlackSheep (chosen)
  - FastAPI
- Chosen option:
  - BlackSheep
- Primary reason:
  - Aligns with the team’s framework preference while supporting an async-first service architecture.
- Impacts:
  - Influences worker/job framework compatibility and middleware/auth approaches.

### ITD-04 — Authentication/authorization integration: Keycloak (OIDC) with optional OpenLDAP
- Status: Completed
- Business problem:
  - On-prem deployments require secure access control aligned to enterprise identity providers.
- Options considered:
  - Keycloak (OIDC) with optional OpenLDAP integration (chosen)
  - OIDC-first with optional IdP bridges to LDAP/SAML
  - LDAP-first
  - SAML-first
- Chosen option:
  - Keycloak (OIDC) with optional OpenLDAP integration
- Primary reason:
  - Provides a standard on-prem identity control plane (OIDC) with an integration path to LDAP when required, reducing enterprise adoption friction.
- Impacts:
  - Impacts repo-level RBAC, auditing, and multi-repo access control.

### ITD-05 — Graph database: NebulaGraph + nGQL
- Status: Completed
- Business problem:
  - We need a disk-backed, scalable graph store for large code graphs with on-prem friendliness and acceptable total cost.
- Options considered:
  - NebulaGraph + nGQL (chosen)
  - Neo4j
  - Memgraph
- Chosen option:
  - NebulaGraph + nGQL
- Primary reason:
  - Best alignment with on-prem scale-out requirements while keeping licensing/TCO compatible with an MIT-licensed project and “local-first” deployments.
- Impacts:
  - Graph schema and query templates must map cleanly to nGQL; operational runbooks and backup/restore procedures must match NebulaGraph.

### ITD-06 — Vector database: Qdrant
- Status: Completed
- Business problem:
  - We need semantic retrieval across code and derived documentation with manageable on-prem operations.
- Options considered:
  - Qdrant (chosen)
  - Postgres + pgvector
  - Milvus
  - LanceDB
- Chosen option:
  - Qdrant
- Primary reason:
  - Good OSS/on-prem operational fit with strong adoption and a clean separation from the relational/graph layers.
- Impacts:
  - Influences chunking strategy and embedding dimensionality; requires backup/restore strategy and PVC sizing.

### ITD-07 — Inference runtime: lemonade-server (llama.cpp)
- Status: Completed
- Business problem:
  - We need reliable on-prem model serving without sending code outside the environment.
- Options considered:
  - lemonade-server (llama.cpp) (chosen)
  - vLLM
  - TGI
- Chosen option:
  - lemonade-server
- Primary reason:
  - Aligns with the chosen GGUF model formats and supports a self-hosted deployment posture with controllable hardware requirements.
- Impacts:
  - Constrains model formats (GGUF) and affects concurrency/latency planning; influences model routing design.

### ITD-08 — Coding LLM: Qwen3-Coder-30B-A3B-Instruct
- Status: Completed
- Business problem:
  - The PRD includes code-aware Q&A and optional agentic coding workflows requiring strong coding competence.
- Options considered:
  - Qwen3-Coder-30B-A3B-Instruct (chosen)
  - TBD other coder models
- Chosen option:
  - Qwen3-Coder-30B-A3B-Instruct
- Primary reason:
  - Better alignment with code-specific tasks while remaining self-hostable for on-prem deployments.
- Impacts:
  - Increases inference hardware requirements; impacts token budgets for RAG context and response streaming.

### ITD-09 — General-purpose LLM: GPT-OSS-20B
- Status: Completed
- Business problem:
  - We need a general reasoning model for summarization, explanations, and non-coding tasks in an on-prem environment.
- Options considered:
  - GPT-OSS-20B (chosen)
  - TBD other open models
- Chosen option:
  - GPT-OSS-20B
- Primary reason:
  - Provides a self-hostable baseline model that supports local-first deployments and predictable cost.
- Impacts:
  - Affects serving capacity requirements and routing logic (general vs coding).

### ITD-10 — Embeddings model: nomic-embed-text-v2-moe-GGUF
- Status: Completed
- Business problem:
  - We need semantic retrieval for code and derived text with a self-hosted embeddings model.
- Options considered:
  - nomic-embed-text-v2-moe-GGUF (chosen)
  - code-specific embedding models (evaluate later)
- Chosen option:
  - nomic-embed-text-v2-moe-GGUF
- Primary reason:
  - Acceptable quality with local-first deployment constraints and manageable inference footprint.
- Impacts:
  - Influences chunking strategy and Qdrant collection configuration.

### ITD-11 — Reranking model: bge-reranker-v2-m3-GGUF
- Status: Completed
- Business problem:
  - We need better precision in retrieval to reduce hallucinations and improve answer quality.
- Options considered:
  - bge-reranker-v2-m3-GGUF (chosen)
  - No reranker
- Chosen option:
  - bge-reranker-v2-m3-GGUF
- Primary reason:
  - Improves retrieval precision without requiring cloud calls, which supports the PRD’s traceability and quality requirements.
- Impacts:
  - Adds latency/capacity considerations; impacts retrieval fusion pipeline.

### ITD-12 — AST parsing approach for MVP languages: Tree-sitter + custom extraction
- Status: Completed
- Business problem:
  - The CPG requires reliable syntax trees and locations for citations, symbols, and relationships.
- Options considered:
  - Tree-sitter based parsing + custom extraction (chosen)
  - LSP-driven indexing
  - SCIP/LSIF-based indexing
  - Joern-first for supported languages
- Chosen option:
  - Tree-sitter based parsing + custom extraction
- Primary reason:
  - Lowest integration and operational risk way to deliver multi-language AST coverage with deterministic locations/citations on an on-prem stack.
- Impacts:
  - Affects symbol accuracy, incremental indexing complexity, and language coverage.

### ITD-13 — Authoritative semantic model: CodeKnowl “semantic facts” contract
- Status: Completed
- Business problem:
  - We need consistent semantics across languages and extractors to support cross-feature correctness.
- Options considered:
  - Build a CodeKnowl semantic-fact contract (chosen)
  - Treat LSP output as authoritative
  - Treat a single CPG extractor as authoritative
- Chosen option:
  - Build a CodeKnowl semantic-fact contract
- Primary reason:
  - Minimizes long-term integration risk by allowing multiple extractors while keeping a stable, provenance-aware internal representation.
- Impacts:
  - Affects schema design, provenance model, and how we merge facts across extractors.

### ITD-14 — Job queue and worker framework: Arq (Redis-backed async jobs)
- Status: Completed
- Business problem:
  - Indexing must be resilient and asynchronous (initial ingest + incremental updates + retries).
- Options considered:
  - Arq (Redis-backed async jobs) (chosen)
  - Celery
  - Dramatiq
  - Redis+RQ
- Chosen option:
  - Arq (Redis-backed async jobs)
- Primary reason:
  - Best fit for an async-first Python stack (BlackSheep) with minimal operational overhead for on-prem deployments.
- Impacts:
  - Impacts reliability, retry behavior, and operational complexity.

### ITD-15 — Deployment runtime: Kubernetes
- Status: Completed
- Business problem:
  - CodeKnowl must be deployable on-prem with repeatable installs, scaling, and isolation across components (graph DB, vector DB, inference, workers).
- Options considered:
  - Kubernetes (chosen)
  - Single-node Docker Compose / systemd services
  - Nomad
- Chosen option:
  - Kubernetes
- Primary reason:
  - Lowest operational risk for on-prem multi-service deployments given existing industry tooling around packaging, upgrades, and observability.
- Impacts:
  - Drives decisions for packaging (Helm), secrets management, storage provisioning (Ceph), and observability stack.

### ITD-16 — Persistent storage substrate: Ceph
- Status: Completed
- Business problem:
  - CodeKnowl needs durable, scalable storage for graph/vector data and indexing artifacts in an on-prem environment.
- Options considered:
  - Ceph (chosen)
  - Local node disks only
  - NFS
- Chosen option:
  - Ceph
- Primary reason:
  - Minimizes data-loss risk and simplifies capacity management by providing a shared storage substrate suitable for Kubernetes.
- Impacts:
  - Influences PVC/storage-class assumptions for NebulaGraph and Qdrant, and artifact/object storage layout decisions.

### ITD-17 — Baseline hardware platform: AMD HX 370 mini PCs
- Status: Completed
- Business problem:
  - CodeKnowl must be viable as an on-prem, MIT-licensed solution with a clear “recommended hardware” story that minimizes total cost while delivering acceptable performance.
- Options considered:
  - AMD HX 370 mini PCs (chosen)
  - Rack servers (higher cost, more power/space)
  - Cloud GPUs (not on-prem-first)
- Chosen option:
  - AMD HX 370 mini PCs
- Primary reason:
  - Best cost/performance fit for a small on-prem cluster that can host Kubernetes + local GGUF inference without requiring data to leave the environment.
- Impacts:
  - Drives sizing assumptions (e.g., 3-node cluster, per-node RAM constraints), model selection/quantization strategy, and performance expectations for indexing + inference.

### ITD-18 — Observability: Loki + Prometheus/Grafana
- Status: Completed
- Business problem:
  - On-prem customers need visibility into indexing health, latency, and failures.
- Options considered:
  - Loki + Prometheus/Grafana (chosen)
  - TBD alternatives
- Chosen option:
  - Loki + Prometheus/Grafana
- Primary reason:
  - Strong on-prem operational fit with Kubernetes and a clear path to dashboards/alerts.
- Impacts:
  - Requires consistent structured logging, metrics instrumentation, and audit event design.

### ITD-19 — Code analysis integrations: SonarQube Community Build and Semgrep
- Status: Completed
- Business problem:
  - The PRD calls for analysis signals and reporting (quality/risk/security oriented) that should be machine-ingestible.
- Options considered:
  - SonarQube Community Build (chosen)
  - Semgrep (chosen)
  - Additional scanners (pending research)
- Chosen option:
  - SonarQube Community Build and Semgrep
- Primary reason:
  - Provides high-value analysis signals using widely adopted tools without requiring a proprietary SaaS dependency.
- Impacts:
  - Requires license-due-diligence on analyzers/rules; requires SARIF/JSON ingestion pipeline and data model.

### ITD-20 — CPG references: Joern and Fraunhofer AISEC CPG
- Status: Completed
- Business problem:
  - We need credible reference implementations for CPG extraction/semantics to avoid reinventing core concepts.
- Options considered:
  - Joern (chosen)
  - Fraunhofer AISEC CPG (chosen)
  - ShiftLeft CodePropertyGraph spec (pending decision for schema baseline)
- Chosen option:
  - Joern and Fraunhofer AISEC CPG as references
- Primary reason:
  - Reduces technical risk by grounding CodeKnowl’s CPG approach in established models and tooling.
- Impacts:
  - Influences schema design and extraction strategy; may influence language coverage priorities.

### ITD-21 — Frontend technology (non-extension surfaces): React
- Status: Completed
- Business problem:
  - We need an admin/observability UI surface for repository onboarding, indexing status, and health.
- Options considered:
  - React (chosen)
  - TBD other web stacks
- Chosen option:
  - React
- Primary reason:
  - Broad ecosystem and low hiring/maintenance risk for building internal/admin UI features.
- Impacts:
  - Requires API contracts for admin workflows; influences auth/UI integration approach.

### ITD-22 — Future embeddings upgrade path: add CodeT5+ (or similar) only if Nomic is insufficient
- Status: Completed
- Business problem:
  - If general embeddings underperform on identifier-heavy code retrieval, we need a planned upgrade path.
- Options considered:
  - Keep Nomic and add code-specific embeddings later (chosen)
  - Switch to code-specific embeddings immediately
- Chosen option:
  - Keep Nomic and add code-specific embeddings later
- Primary reason:
  - Lowest TCO path that preserves on-prem delivery while keeping a clear escape hatch if retrieval quality becomes a blocker.
- Impacts:
  - Changes embedding generation pipeline and vector DB storage requirements.
