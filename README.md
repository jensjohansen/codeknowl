# CodeKnowl

<p align="right">
  <img src="assets/knowl.png" alt="Knowl" width="128" />
</p>

CodeKnowl is an on-prem, local-first “codebase analyst” that ingests one or more Git repositories and provides:

- A structured relationship store for code entities and relationships.
- A knowledge base suitable for retrieval, summarization, and analyst workflows.
- An IDE-first experience (initially VS Code) for Q&A with citations, navigation, and impact analysis.

## Local development

### Backend

See `backend/README.md` for the authoritative instructions to run the Python backend.

### Environment variables

This repository includes a `local.env` template at the repo root. It captures the backend's supported `CODEKNOWL_*`
environment variables (LLM profiles for synthesis, embeddings, vector store, auth/audit, reranker, QA evidence caps).

- **[secrets]** Do not commit real API keys.
- **[loading]** Typical shell usage:

```bash
set -a
source local.env
set +a
```

By default, the backend stores state in `.codeknowl` (SQLite + artifacts). You can also choose local-only modes for
development and tests:

- `CODEKNOWL_VECTOR_MODE=file`
- `CODEKNOWL_EMBED_MODE=hash`

To enable LLM-backed `qa.ask` synthesis, configure either `CODEKNOWL_LLM_*` or the role-specific profiles:

- `CODEKNOWL_LLM_CODING_*`
- `CODEKNOWL_LLM_GENERAL_*`
- `CODEKNOWL_LLM_SYNTH_*` (defaults to `GENERAL` if not set)

## Project docs

### Product
- [PRD (revised)](docs/prd-revised.md)
- [Implementation plan / tracker](docs/implementation-plan-tracker.md)

### Architecture and design
- [Architecture & design (tactical/functional spec)](docs/architecture-and-design.md)

### Research and technology
- [ITD register](docs/research/technology/itd-register.md)
- [OSS components & licensing notes](docs/research/technology/oss-components-commercially-permissible.md)
- [Buy vs build evaluation plan](docs/buy-vs-build-evaluation-plan.md)

## License

MIT License. See `LICENSE`.

Third-party notices: see `THIRD_PARTY_NOTICES.md`.
