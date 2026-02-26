# ShiftLeft CodePropertyGraph (ShiftLeftSecurity/codepropertygraph) — Research Paper

## Abstract
`ShiftLeftSecurity/codepropertygraph` is the **base specification and tooling** for the “Code Property Graph” schema used by Joern and related tooling. It provides a minimal base schema that can be extended, and includes build tooling to generate data structure definitions and Protocol Buffer bindings for accessing a CPG in different languages. It is explicitly positioned as a **specification and exchange format**, not as a full end-to-end analysis product.

## 1. Purpose, target users, and positioning
### 1.1 Purpose
The repository describes itself as:
- “Code Property Graph - Specification and Tooling”
- A suggestion for an open standard for exchanging code intermediate representations and analysis results
- A minimal base schema augmented via extension schemas

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph

### 1.2 Target users
- Tool builders who want a common CPG schema
- Teams wanting a language-agnostic interchange format between CPG producers/consumers

### 1.3 Positioning note
The README explicitly recommends first-time users build Joern instead because it combines this repo with language frontends to form a complete platform.

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph

## 2. Technical components
### 2.1 Schema and versioning approach
The project emphasizes:
- A minimal base schema
- Extension schemas for application-specific data
- Generated artifacts for different languages

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph

### 2.2 Protocol Buffer / bindings
The README describes generating bindings from `cpg.proto` contained in the jar artifact.

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph

### 2.3 Loading and querying a CPG
The README includes:
- Example loading into “ShiftLeft Tinkergraph”
- A “Querying the cpg” section that references the `query-primitives` subproject
- Example traversals (`cpg.file.toList`, `cpg.method...` etc.)

**Primary sources:**
- Loading section: https://github.com/ShiftLeftSecurity/codepropertygraph
- Querying section: https://github.com/ShiftLeftSecurity/codepropertygraph

## 3. Query model
The “query-primitives” DSL is described as strongly typed in the sense that invalid steps result in compile errors.

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph (Querying the cpg)

## 4. Storage model
The README references loading into an in-memory reference database (Tinkergraph) for interactive usage.

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph

## 5. Licensing and governance
The project is Apache-2.0 licensed (visible on GitHub).

**Primary source:** https://github.com/ShiftLeftSecurity/codepropertygraph

## 6. Strengths and weaknesses (for CodeKnowl adoption)
### 6.1 Strengths
- Good “schema contract” for CPG producers/consumers
- Extension schema concept maps cleanly to CodeKnowl’s need to add product-specific metadata (LLM summaries, embeddings, provenance)
- Protobuf bindings support polyglot tooling and distributed pipelines

### 6.2 Weaknesses / risks
- Not a complete system: no language frontends and no complete analysis engine on its own
- Still implies a Scala ecosystem for many of the existing query primitives

## 7. “Minimum bar” requirements inferred for CodeKnowl
From a product perspective, this repo suggests CodeKnowl should have:
- A **versioned schema** and an extension mechanism
- A stable interchange format for analysis outputs (even if internal)
- A typed query API layer (or a constrained query surface) to avoid “invalid traversals”

## 8. Relevance to CodeKnowl
- If CodeKnowl wants long-lived, disk-backed graphs in NebulaGraph, the ShiftLeft spec is more useful as a conceptual guide / schema baseline than as a storage engine.
- If CodeKnowl ever needs interop with Joern ecosystems, aligning concepts/labels with this spec reduces translation friction.

## References
- Repository README: https://github.com/ShiftLeftSecurity/codepropertygraph
