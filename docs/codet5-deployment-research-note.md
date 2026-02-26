# Research Note: Deploying CodeT5+ on `knowl3` (8945HS) for CodeKnowl

This note answers three practical questions about a future (post-MVP) deployment of **CodeT5+** on the embeddings / CPU-services node (`knowl3`, e.g. an 8945HS mini PC).

CodeKnowl MVP is planned to use **Nomic embeddings via Lemonade Server**. CodeT5+ is kept as an optional upgrade path if we later measure a meaningful lift for code-to-code retrieval.

## 1) Is Lemonade Server locked down to only the models at `models.html`?

No. Lemonade Server is **not** locked down to only the curated model registry.

Key points from Lemonade docs:

- Lemonade Server can discover **arbitrary `.gguf` files** from an extra models directory when launched with `--extra-models-dir`. Any `.gguf` found there “will automatically appear in Lemonade's model list in the custom category.”
  - Source: Lemonade FAQ (Models → model storage; extra models directory + `.gguf` discovery)

- If a model isn’t listed in the Model Manager, Lemonade explicitly suggests:
  - Add a custom model manually via the app or via the CLI `pull` command.
  - Optionally disable model filtering via `LEMONADE_DISABLE_MODEL_FILTERING`.
  - Source: Lemonade FAQ (Models → “I'm looking for a model, but it's not listed…”) 

- The CLI docs show how to **register and install a custom GGUF model** using `lemonade-server pull` with `--checkpoint` and `--recipe llamacpp`.
  - Source: Lemonade Server CLI docs (“Options for pull”)

What this means for CodeT5+:

- If CodeT5+ (or a CodeT5-derived model) is available as a GGUF compatible with llama.cpp, Lemonade Server can likely *list and serve it* as a “custom” GGUF model.

Important nuance:

- CodeT5+ is **not inherently a GGUF/llama.cpp-native architecture** in the same way common decoder-only LLMs are. In practice, “can Lemonade serve it?” depends less on Lemonade policy and more on whether you have a compatible model artifact and runtime backend.

## 2) If we can’t use Lemonade Server for CodeT5+, what should we use instead?

If CodeT5+ can’t be run via Lemonade’s supported backends (or if you don’t have a compatible artifact), the most straightforward alternatives are:

### Option A: Run CodeT5+ as a dedicated embeddings microservice (recommended)

A small service that exposes an HTTP API like:

- `POST /embeddings` with `{ "inputs": [...] }`

Implementation choices:

- **Python + Hugging Face Transformers** for the model runtime
- Use a simple web framework:
  - `FastAPI` (common)
  - `aiohttp` (fine)

Deployment choices:

- **Kubernetes pod** on `knowl3`
  - Pros:
    - consistent with the rest of CodeKnowl deployment
    - easy rollout/rollback
    - easy resource limits/requests
    - easy node pinning (`nodeSelector` to `knowl3`)
  - Cons:
    - you must manage Python deps/container image

- **Ubuntu service (systemd)** on `knowl3`
  - Pros:
    - simplest runtime surface area
    - fewer Kubernetes moving parts
  - Cons:
    - less portable
    - harder to integrate with cluster-native service discovery/ingress patterns

For CodeKnowl, Kubernetes is typically the cleaner choice because you can:

- pin the deployment to `knowl3`
- expose it as a ClusterIP Service
- have the indexer call it uniformly

### Option B: Offline batch embeddings (no service)

If embeddings are computed only during indexing (not online), you can run CodeT5+ as a batch job:

- a Kubernetes Job/CronJob
- or a pipeline step in your indexing worker

This can be a good approach if:

- you don’t need low-latency embedding generation on demand
- you primarily embed code during ingestion/update

## 3) Will using the GPU on `knowl3` improve CodeT5+ performance?

It depends on:

- the runtime (PyTorch vs ONNX Runtime vs something else)
- the model size and how much time is spent in matrix ops vs overhead
- whether your embedding workload is throughput-oriented (batching) or low-latency (single snippet)

### Practical expectations

- **Yes, GPU can help** if you are embedding a lot of content and can batch requests.
- For smaller batches / short snippets, gains may be modest due to overhead.

### How to measure (recommended)

If/when you pick a specific CodeT5+ artifact and runtime, run a simple benchmark on `knowl3`:

- Dataset:
  - a few hundred code chunks representative of your ingestion chunking strategy
- Compare:
  - CPU-only
  - CPU+iGPU
- Measure:
  - embeddings/sec (throughput)
  - p50/p95 latency for batch sizes of 1, 8, 32, 128

### Why this is worth benchmarking

For CodeKnowl, embeddings are typically a major cost center in indexing. If CodeT5+ is materially better for code retrieval but materially slower, you may decide to:

- keep Nomic for broad coverage
- use CodeT5+ only for code chunks
- or use CodeT5+ only for “similar code” workflows

## Recommended conclusion (for the PRD + roadmap)

- Lemonade Server is **not limited** to only the pre-listed models; it supports custom GGUF discovery and custom GGUF pulls.
- CodeT5+ should be treated as a **post-MVP** option because the main uncertainty is not “policy support,” but whether the desired CodeT5+ variant is available in a backend-compatible format.
- If CodeT5+ can’t be served via Lemonade, deploy it as a **Kubernetes embeddings microservice** pinned to `knowl3`.
- GPU acceleration on 8945HS may help, but should be validated with a small benchmark aligned to your actual chunking and batching strategy.

## Citations

- Lemonade FAQ (Models): extra models directory and `.gguf` discovery; model not listed guidance; environment variables like `LEMONADE_DISABLE_MODEL_FILTERING`.
  - https://lemonade-server.ai/docs/faq/
- Lemonade Server CLI docs (custom GGUF registration via `pull --checkpoint ... --recipe llamacpp`)
  - https://lemonade-server.ai/docs/server/lemonade-server-cli/
- Lemonade Server spec (GGUF support; installing arbitrary GGUF via the web app)
  - https://lemonade-server.ai/docs/server/server_spec/
