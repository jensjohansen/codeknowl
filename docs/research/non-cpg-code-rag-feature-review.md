# Non-CPG Code RAG Projects (>=100 stars) — Feature Review and CodeKnowl Takeaways

## Scope
This document briefly reviews code-oriented “RAG” projects that **do not implement a full Code Property Graph** (i.e., they do not clearly provide AST+CFG+PDG/dataflow as a unified property graph), but that may contain product features worth borrowing for CodeKnowl.

Projects covered here:
- `vitali87/code-graph-rag` (code knowledge graph + agent features)
- `microsoft/graphrag` (general GraphRAG pipeline)
- `sankalp1999/code_qa` (tree-sitter structure extraction + vector index)

## 1) vitali87/code-graph-rag — “Graph-Based RAG System for Any Codebases”
### What it is
A codebase tool that:
- Parses code with Tree-sitter
- Stores a code structure knowledge graph in Memgraph
- Exposes natural-language querying and an MCP server integration

**Primary source:** https://github.com/vitali87/code-graph-rag

### Notable features to consider for CodeKnowl
- **MCP server integration** to make the system usable by IDE/agent clients
  - Source: README mentions MCP server integration
- **Natural language → graph query (Cypher) generation** and multi-provider model support (cloud + local)
  - Source: README “AI-Powered Cypher Generation”
- **Advanced file editing workflow** with AST-based targeting and diff previews
  - Source: README “Advanced File Editing”
- **Operational niceties**: real-time updates (optional), CLI, Makefile workflow

### Why it is not “full CPG”
The README emphasizes a unified schema of code structure (symbols, files, relationships) and retrieval/editing workflows; it does not claim CFG/PDG semantics in the Joern sense.

## 2) microsoft/graphrag — general GraphRAG pipeline
### What it is
A general “data pipeline and transformation suite” that uses LLMs to extract structured data from unstructured text, and uses “knowledge graph memory structures” to enhance LLM outputs.

**Primary source:** https://github.com/microsoft/graphrag

### Notable features to consider for CodeKnowl
- **Pipeline discipline** (init/migrations/versioning) and explicit caution about expensive indexing
- **Prompt tuning** emphasis (treat prompts/config as first-class artifacts)
- **Responsible AI + documentation quality** as a model for how to ship a serious OSS pipeline

### Why it is not code-CPG
It targets unstructured text corpora broadly; it is not a code semantics graph.

## 3) sankalp1999/code_qa — tree-sitter + LanceDB code RAG
### What it is
A codebase Q&A tool that:
- Uses tree-sitter for code structure extraction
- Generates embeddings and stores them in LanceDB
- Provides a simple UI for codebase querying

**Primary source:** https://github.com/sankalp1999/code_qa

### Notable features to consider for CodeKnowl
- **Hybrid approach**: structure extraction + embeddings + reranking
- Minimal UI and developer workflow for “@codebase” queries

### Why it is not full CPG
No indication of CFG/PDG/dataflow overlays; the graph aspect is not the core system of record.

## Cross-cutting “product must-haves” inferred from non-CPG code RAG tools
Even without full CPG semantics, these projects set user expectations for:
- **IDE integration surface** (MCP server is emerging as a practical standard)
- **Natural language query UX** (including query translation and guardrails)
- **Citable answers** (links back to files/lines/symbols)
- **Safe editing workflows** (diff previews, targeted edits, approval gates)
- **Incremental updates** (watch filesystem / reindex selectively)

## CodeKnowl “minimum bar” checklist (synthesized)
If CodeKnowl wants to meet the bar set by both full-CPG tools and code-RAG tools, a pragmatic minimum bar is:

### Graph/semantic core
- AST-level symbol graph for multi-language repos
- Call graph (at least resolvable to “best effort”)
- Some dataflow capability (taint-like or DFG-like) for deeper reasoning
- Schema versioning + extension mechanism

### Retrieval and UX
- Vector retrieval for text/semantic search
- Graph traversal retrieval for structural queries
- Citations (file path + line ranges) as a first-class output contract

### Agentic operations
- MCP server interface
- Safe edit pipeline: propose → diff → approve → apply
- Ability to run tests/commands in a controlled way

### Ops and scale
- Disk-backed storage (your current direction with NebulaGraph)
- Incremental reindexing
- Per-repo isolation / multi-tenant design

## References
- Code-Graph-RAG README/features: https://github.com/vitali87/code-graph-rag
- GraphRAG README/overview: https://github.com/microsoft/graphrag
- CodeQA README: https://github.com/sankalp1999/code_qa
