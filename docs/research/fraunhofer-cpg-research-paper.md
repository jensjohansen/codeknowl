# Fraunhofer AISEC CPG (Fraunhofer-AISEC/cpg) — Code Property Graph Research Paper

## Abstract
Fraunhofer AISEC’s `cpg` project is an open-source library for extracting **Code Property Graphs** across multiple languages, with explicit formal specifications for core semantic overlays including a **Data Flow Graph (DFG)** and an **Evaluation Order Graph (EOG)**. Unlike Joern (an end-to-end analysis platform), this project is primarily a **CPG construction + schema/spec + library** that can be integrated into other systems and stored in external graph databases (e.g., Neo4j is referenced in the project’s “graph model” specification).

## 1. Purpose, target users, and positioning
### 1.1 Purpose
The README defines a CPG as a labeled, directed multigraph with properties, suitable for storage in graph databases and querying with graph query languages.

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg (What is this?)

### 1.2 Target users
- Researchers and engineers building static analysis tooling on top of a CPG
- Teams that want to **embed** CPG generation into their own products/pipelines

### 1.3 Positioning / differentiation
Key differentiators in the project’s own docs:
- Explicit specs for semantic overlays (DFG, EOG)
- Language frontends including forgiving parsers for some languages
- Integration path as a library

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg

## 2. CPG definition and conceptual model
The README states that a code property graph is:
- A labeled directed multi-graph
- Nodes/edges have key-value properties
- Intended for use with graph databases and query languages (Cypher, Gremlin, etc.)

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg

## 3. Semantic overlays / “full CPG” characteristics
The project maintains explicit specifications for:
- **DFG (Data Flow Graph):** defined as edges between nodes with `prevDFG`/`nextDFG`.
- **EOG (Evaluation Order Graph):** a fine-grained execution-order overlay across AST nodes (`prevEOG`/`nextEOG`).

These overlays go beyond a pure AST graph and represent “full CPG”-style semantics needed for deeper program reasoning.

**Primary sources:**
- DFG spec: https://fraunhofer-aisec.github.io/cpg/CPG/specs/dfg/
- EOG spec: https://fraunhofer-aisec.github.io/cpg/CPG/specs/eog/

## 4. Graph schema and persistence model
The “Graph Schema” documentation explicitly mentions persistence of the in-memory CPG into **Neo4j** and that the spec is generated automatically.

**Primary source:** https://fraunhofer-aisec.github.io/cpg/CPG/specs/graph/ (CPG Schema)

## 5. Parsing strategy and robustness
The README notes the use of “forgiving parsers” for some languages:
- Eclipse CDT for C/C++
- JavaParser for Java
and contrasts these with compiler AST generators, describing tolerance for incomplete/incorrect code and missing dependencies.

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg

## 6. Language support
The documentation describes a language maturity model (maintained / incubating / experimental / discontinued), and notes that many languages can be analyzed via LLVM IR through `cpg-language-llvm`.

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg (Language Support)

## 7. Query model
The project is positioned as compatible with standard graph DB query languages (e.g., Cypher, Gremlin) because its representation is a labeled directed multigraph with properties.

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg

## 8. Licensing and governance
The repository is Apache-2.0 licensed (visible on GitHub).

**Primary source:** https://github.com/Fraunhofer-AISEC/cpg

## 9. Strengths and weaknesses (for CodeKnowl adoption)
### 9.1 Strengths
- Clear formal specs for semantics like DFG and EOG (good for “complete understanding” beyond structure)
- Library-first design: can be embedded into CodeKnowl ingestion pipelines
- Explicit Neo4j-oriented schema documentation suggests practical persistence patterns

### 9.2 Weaknesses / risks
- It is not a complete “product”: you would need to build the surrounding ingestion/orchestration, storage, UI, and RAG integration
- Language support maturity varies (explicitly acknowledged in docs)

## 10. “Minimum bar” requirements inferred for CodeKnowl
If you want to be competitive with full-CPG systems, this project suggests your minimum bar should include:
- A formal (or at least stable) schema and versioning strategy
- A dataflow overlay (DFG-like) and an execution-order/control overlay (EOG/CFG-like)
- A way to persist and query the graph in an external DB (Neo4j is an existence proof; CodeKnowl would map to NebulaGraph or Postgres/AGE)

## References
- Repository README (CPG definition, parsers, storage/query compatibility): https://github.com/Fraunhofer-AISEC/cpg
- DFG spec (`prevDFG`/`nextDFG`): https://fraunhofer-aisec.github.io/cpg/CPG/specs/dfg/
- EOG spec (`prevEOG`/`nextEOG`): https://fraunhofer-aisec.github.io/cpg/CPG/specs/eog/
- Graph schema / Neo4j persistence note: https://fraunhofer-aisec.github.io/cpg/CPG/specs/graph/
