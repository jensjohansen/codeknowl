# Joern (joernio/joern) — Code Property Graph Research Paper

## Abstract
Joern is an open-source static analysis platform that builds **Code Property Graphs (CPGs)** from source code, bytecode, and binaries, and supports interactive and automated vulnerability research via a strongly-typed, Scala-based query DSL. Joern is best understood as an end-to-end CPG system: ingestion frontends + a multi-layer CPG representation + query/runtime + analysis passes (including taint analysis).

## 1. Purpose, target users, and positioning
### 1.1 Purpose
Joern’s stated purpose is static program analysis and vulnerability discovery by representing programs as CPGs and enabling mining via graph queries.

### 1.2 Target users
- Security researchers and appsec engineers doing vulnerability discovery
- Static analysis researchers building/experimenting with new analyses
- Power users comfortable with query-driven analysis (Scala-like DSL)

### 1.3 Positioning / differentiation
Joern emphasizes:
- Robust/fuzzy parsing (import even without full build environments)
- Multi-layer semantic graph representation (CPG)
- Query-first workflow (interactive and scripted)
- Extensibility via passes

**Primary sources:**
- Joern README overview: https://github.com/joernio/joern (see “Joern is a platform…”)
- Joern docs “Core features”: https://docs.joern.io/

## 2. System overview and architecture
### 2.1 CPG generation pipeline
At a high level, Joern:
- Parses code via language frontends
- Builds an intermediate representation as a **CPG**
- Runs additional enrichment passes (data-flow/taint/etc.)
- Supports interactive exploration and automated analyses

The Joern documentation describes core features including “Code Property Graphs”, a “Taint Analysis” engine, and an extensible query language.

**Primary source:** https://docs.joern.io/ (core features)

### 2.2 Multi-layer graph model
Joern’s CPG is explicitly described as multi-layered; the public spec site organizes the schema into layers such as:
- **AST**
- **CallGraph**
- **CFG**
- **Dominators**
- **PDG** (data dependence + control dependence)

**Primary source:** https://cpg.joern.io/ (e.g., AST / CFG / PDG sections)

### 2.3 Execution modes
Joern supports local usage and Docker execution; the README includes a Docker invocation and also mentions running in “server mode”.

**Primary source:** https://github.com/joernio/joern (Docker based execution, `--server`)

## 3. Storage model and scalability characteristics
### 3.1 Storage statement
The Joern README states that generated CPGs are stored in a “custom graph database”.

**Primary source:** https://github.com/joernio/joern

### 3.2 In-memory emphasis (docs)
The Joern documentation states that Joern stores semantic code property graphs “in an in-memory graph database.”

**Primary source:** https://docs.joern.io/ (core features)

### 3.3 Implication for large monorepos
For very large repos, the in-memory orientation implies:
- You need an ingestion strategy that bounds graph size per analysis job (partitioning, selective ingestion, or distributed workflow outside of Joern)
- You need an on-disk persistence/export strategy if your product requires long-lived graphs

Joern can still be used as a **CPG generator + analysis engine** even if CodeKnowl stores its durable graph in a separate DB (e.g., NebulaGraph).

## 4. Query model
Joern uses a Scala-based DSL for querying the code graph.
- README: “Scala-based domain-specific query language”
- Spec/tooling ecosystem includes query primitives and typed traversal steps.

**Primary sources:**
- https://github.com/joernio/joern

## 5. Static analysis capabilities
### 5.1 Taint analysis
Joern’s docs list a “Taint Analysis” engine as a core feature.

**Primary source:** https://docs.joern.io/

### 5.2 Extensible passes
Joern’s docs describe extensibility via “CPG passes” and multi-layered graphs.

**Primary source:** https://docs.joern.io/

## 6. Language support
The Joern docs site enumerates language frontends (e.g., Java, JavaScript, Python) and indicates a frontend architecture (“X2CPG”).

**Primary source:** https://docs.joern.io/ (Frontends)

## 7. Licensing and governance
Joern is Apache-2.0 licensed (visible on the GitHub repo).

**Primary source:** https://github.com/joernio/joern

## 8. Strengths and weaknesses (for CodeKnowl adoption)
### 8.1 Strengths
- **Full CPG semantics** aligned with the classic CPG definition (AST + CFG + PDG)
- Mature query ecosystem; designed for deep code reasoning and vulnerability research
- Extensibility via passes (a strong “minimum bar” capability)

### 8.2 Weaknesses / risks
- In-memory orientation is a mismatch for a durable, disk-backed “complete understanding of a monorepo” product unless you treat Joern as an analysis backend rather than the system of record
- Developer ergonomics: Scala DSL is powerful but a barrier for many teams; productizing requires building friendlier APIs/UIs

## 9. “Minimum bar” requirements inferred for CodeKnowl
If you want to compete with/meet expectations set by Joern-like CPG systems:
- Durable representation that can express at least AST + call graph + CFG + some dataflow/PDG-like edges
- Query surface that supports:
  - Symbol lookup
  - Cross-file call chains
  - Dataflow/taint-style reasoning
- Extensibility mechanism (passes/plugins) to enrich graph over time

## 10. Relevance to CodeKnowl build-vs-buy
### 10.1 When Joern can replace CodeKnowl
If your core product need is security/static analysis (taint, vulnerability patterns, code mining) and you’re willing to accept Joern’s operational model, Joern could serve as the primary engine.

### 10.2 When CodeKnowl still makes sense
If you need:
- Disk-backed, multi-tenant, long-lived graphs for very large repos
- Integration with on-prem RAG, vector DB, and your own agent workflow
- Non-security workflows (architecture understanding, impact analysis, refactoring assistance)

then Joern is more naturally a **CPG extraction/analysis backend** or reference implementation rather than a complete replacement.

## References
- Joern repository (overview, execution modes): https://github.com/joernio/joern
- Joern documentation (core features, frontends): https://docs.joern.io/
- Code Property Graph specification as implemented by Joern: https://cpg.joern.io/
