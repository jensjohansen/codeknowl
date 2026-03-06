# Deploying CodeKnowl Models on a 3-Node Mini-PC Kubernetes Cluster (knowl1/knowl2/knowl3)

This document is a shareable, “no-real-hostnames” guide for deploying the three model services used by CodeKnowl onto a small on-prem Kubernetes cluster.

It is based on the practical lessons captured in `docs/lemonade-server-hx370-linux-runbook.md`, but rewritten to assume a clean 3-node setup with **generic node names**.

## Scope

You will deploy:

- `Qwen3-Coder-30B-A3B-Instruct-GGUF` on `knowl1` via **Lemonade Server**
- `gpt-oss-20b-mxfp4-GGUF` on `knowl2` via **Lemonade Server**
- `nomic-embed-text-v2-moe-GGUF` on `knowl3` via **Lemonade Server** (CPU-only or CPU+iGPU)
- `CodeT5+` on `knowl3` (CPU-only or CPU+iGPU)
- `bge-reranker-v2-m3-GGUF` on `knowl3` via **Lemonade Server** (CPU-only or CPU+iGPU)

Note on node count vs model count:

- In a strict three-node build, `Qwen3-Coder-30B-A3B-Instruct-GGUF` and `gpt-oss-20b-mxfp4-GGUF` are large enough that they typically need dedicated nodes.
- That leaves one node to host both embeddings and reranking, which can be done a few ways.

Operational options (do not implement both right now; this is for planning):

- **Option A (simplest scheduling)**: dedicate `knowl3` to embeddings (nomic) and run `bge-reranker-v2-m3-GGUF` CPU-only as a separate Kubernetes workload.
- **Option B (single host service)**: run both `nomic-embed-text-v2-moe-GGUF` (embeddings) and `bge-reranker-v2-m3-GGUF` (reranking) on the same Lemonade Server instance and validate that resource sharing/unload behavior is acceptable.

For the MVP implementation, we used a fourth node for the reranker to avoid resource contention while we validated the end-to-end system.

This guide focuses on:

- Node preparation (Ubuntu + ROCm + Lemonade)
- A clean node naming convention (`knowl1`, `knowl2`, `knowl3`)
- Kubernetes scheduling so each model lands on the intended node
- Verification gates and common gotchas (proxy, UMA/TTM)

## Reference hardware (examples)

This guide assumes a three-node cluster:

- `knowl1` (LLM node): **Ryzen AI 9 HX 370** mini PC
  - Example: Minisforum Aiberzy XG1-370 (64GB)
  - https://store.minisforum.com/products/minisforum-xg1-370-mini-pc?_pos=1&_psq=aiberzy&_ss=e&_v=1.0&variant=47212341100789

- `knowl2` (LLM node): **Ryzen AI 9 HX 370** mini PC
  - Example: Minisforum Aiberzy XG1-370 (64GB)
  - https://store.minisforum.com/products/minisforum-xg1-370-mini-pc?_pos=1&_psq=aiberzy&_ss=e&_v=1.0&variant=47212341100789

- `knowl3` (embeddings node): **Ryzen 9 8945HS** mini PC
  - Example: Minisforum UM890 Pro
  - https://store.minisforum.com/products/minisforum-um890pro-mini-pc

## Assumptions

- OS: Ubuntu 25.x (this guide was validated on Ubuntu 25.04/25.10 in the original runbook)
- RAM: 64GB per node
- Kubernetes is installed and the nodes are joined into a single cluster
- You have admin access:
  - `sudo` on each node
  - `kubectl` admin on the cluster

## 0) Choose and apply node names

Make sure Kubernetes sees the nodes as:

- `knowl1`
- `knowl2`
- `knowl3`

Verification:

```bash
kubectl get nodes -o wide
```

If your nodes currently have different names, rename them at the OS layer and/or adjust your kubelet/k3s configuration so the Kubernetes node names are stable.

## 1) Label nodes so scheduling is deterministic

Add labels to your nodes so workloads can select the correct placement.

Recommended labels:

- `codeknowl.role=llm`
- `codeknowl.role=embeddings`
- `codeknowl.model=qwen3-coder-30b`
- `codeknowl.model=gpt-oss-20b`
- `codeknowl.model=nomic-embed-text-v2-moe`
- `codeknowl.model=codet5`
- `codeknowl.model=bge-reranker-v2-m3`

Example:

```bash
kubectl label node knowl1 codeknowl.role=llm codeknowl.model=qwen3-coder-30b --overwrite
kubectl label node knowl2 codeknowl.role=llm codeknowl.model=gpt-oss-20b --overwrite
kubectl label node knowl3 codeknowl.role=embeddings codeknowl.model=nomic-embed-text-v2-moe codeknowl.model=codet5 codeknowl.model=bge-reranker-v2-m3 --overwrite
```

Verify:

```bash
kubectl get nodes --show-labels | sed -n '1p;/knowl[123]/p'
```

## 2) BIOS/firmware guidance (UMA)

Practical recommendation:

- During bring-up, keep UMA higher to reduce variables.
- After stable operation, reduce UMA (example: 1GB) and rely on dynamic allocation.

In the original runbook:

- One node worked well even at **1GB UMA** due to TTM dynamic allocations.

## 3) Prepare the HX 370 nodes (`knowl1`, `knowl2`) for Lemonade Server

Repeat these steps on both `knowl1` and `knowl2`.

### 3.1 Install Lemonade Server (snap)

```bash
sudo snap install lemonade-server
sudo snap restart lemonade-server
```

Logs:

```bash
sudo journalctl -u snap.lemonade-server.daemon.service -f
```

### 3.2 Verify ROCm is installed and wired correctly

Use the same validation gates as the runbook:

```bash
uname -r
. /etc/os-release && echo "$PRETTY_NAME"
dpkg -l | egrep '^(ii)\s+rocm\b|^(ii)\s+rocm-core\b|^(ii)\s+hip-runtime-amd\b|^(ii)\s+rocm-smi-lib\b'

ls -la /opt | egrep 'rocm' || true
readlink -f /opt/rocm

/opt/rocm/bin/rocminfo | head -30
/opt/rocm/bin/rocm-smi --version
```

If you’re installing ROCm fresh, follow AMD’s Ubuntu package-manager installation flow and validate with the commands above.

### 3.3 Add ROCm tools to PATH (optional but recommended)

```bash
printf '\nexport PATH="%s"\n' '$HOME/.local/bin:/opt/rocm/bin:$PATH' >> ~/.profile
source ~/.profile
which rocminfo
which rocm-smi
```

### 3.4 Install `amd-ttm` (optional but useful)

```bash
sudo apt update
sudo apt install -y pipx
pipx ensurepath

# open a new shell or re-login
pipx install amd-debug-tools
which amd-ttm
amd-ttm
```

### 3.5 Proxy gotcha (important)

If your environment uses an HTTP proxy and your shell exports `http_proxy`/`https_proxy`, even local calls like `curl http://127.0.0.1:8000/...` can be sent to the proxy and fail.

For all localhost checks, use:

```bash
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/health
```

If the node needs a proxy for outbound internet, configure `/etc/environment` with a correct `no_proxy` so snap daemons bypass proxy for localhost and LAN traffic.

## 3.6 Forced-vulkan Lemonade workaround (host OS, runs as `root`)

This section is a durable workaround for nodes where the snap daemon crash-loops with:

- `--llamacpp: rocm not in {vulkan,cpu}`

Symptom:

- `snap.lemonade-server.daemon.service` repeatedly restarts and ports `8000`/`8001` are never bound.

Resolution (validated): disable the snap daemon and run Lemonade via a custom `systemd` unit forcing `vulkan`. This keeps all caches under `/var/snap/lemonade-server/common/cache` and does not rely on any user home directory.

1) Disable the snap daemon:

```bash
sudo snap stop --disable lemonade-server.daemon
sudo snap services lemonade-server
```

2) Create a custom `systemd` service at `/etc/systemd/system/lemonade-server.service`:

```ini
[Unit]
Description=Lemonade Server (snap, forced vulkan)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=-/etc/environment
WorkingDirectory=/var/snap/lemonade-server/common
Environment=HF_HOME=/var/snap/lemonade-server/common/cache
Environment=HUGGINGFACE_HUB_CACHE=/var/snap/lemonade-server/common/cache/huggingface/hub
ExecStart=/snap/bin/lemonade-server serve --host 0.0.0.0 --port 8000 --llamacpp vulkan --log-level debug
Restart=on-failure
RestartSec=3
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
```

3) Ensure cache directories exist:

```bash
sudo mkdir -p /var/snap/lemonade-server/common/cache/huggingface/hub
sudo chown -R root:root /var/snap/lemonade-server/common
```

4) Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lemonade-server.service
sudo systemctl status lemonade-server.service --no-pager -l
```

5) Verify:

```bash
sudo ss -ltnp | egrep ':8000|:8001|lemonade|llama' || true
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/health
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/models
```

If `vulkan` is not available/working for a node, switch the unit to `--llamacpp cpu` as a CPU-only fallback.

## 4) Deploy Qwen3-Coder on `knowl1`

### 4.1 Configure model selection

Lemonade exposes an OpenAI-compatible API and typically manages model downloads into the snap cache directory under:

- `/var/snap/lemonade-server/common/cache/`

After you’ve configured Lemonade to use `Qwen3-Coder-30B-A3B-Instruct-GGUF`, verify that the GGUF exists and is intact.

Example pattern (adjust to the actual cached path for your model):

```bash
sudo ls -lh /var/snap/lemonade-server/common/cache/huggingface/hub/ | head
```

### 4.2 Verify Lemonade health

```bash
sudo ss -ltnp | egrep ':8000|:8001' || true

curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/health
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/models
```

### 4.3 Quick chat test (local)

```bash
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"Qwen3-Coder-30B-A3B-Instruct-GGUF","messages":[{"role":"user","content":"Say hello"}],"stream":false}'
```

### 4.4 Confirm GPU offload via logs

Look for signatures like:

- `offloaded ... layers to GPU`
- `ROCm0 model buffer size = ...`

```bash
sudo journalctl -u snap.lemonade-server.daemon.service -n 200 --no-pager | egrep 'offloaded|ROCm0 model buffer|ngl|llama-server' || true
```

If the model download fails validation (incomplete/missing files), stop Lemonade, delete the corresponding HuggingFace cache entry under `/var/snap/lemonade-server/common/cache/huggingface/hub/models--*`, and retry the same request to trigger a clean re-download.

## 5) Deploy gpt-oss on `knowl2`

Repeat the same Lemonade + ROCm + proxy checks on `knowl2`.

### 5.1 Quick chat test (local)

```bash
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-oss-20b-mxfp4-GGUF","messages":[{"role":"user","content":"Say hello"}],"stream":false}'
```

### 5.2 Confirm GPU offload

```bash
sudo journalctl -u snap.lemonade-server.daemon.service -n 200 --no-pager | egrep 'offloaded|ROCm0 model buffer|ngl|llama-server' || true
```

## 6) Deploy CodeT5+ on `knowl3`

`knowl3` is intended to run CodeT5+ (CPU-only or CPU+iGPU), plus CPU-bound platform services.

This guide intentionally keeps CodeT5+ deployment high-level because the exact serving method can vary (Python service, container, or integration into your indexing pipeline). The key operational guidance is:

- CodeT5+ is typically stable and useful even without GPU offload.
- The 8945HS node should be sized for sustained CPU throughput.

Verification gate (baseline):

- Ensure the node has sufficient RAM headroom.
- Ensure your chosen serving process can run reliably under `systemd` or Kubernetes.

If you are serving embeddings over HTTP/gRPC, apply the same proxy guidance as above (`no_proxy` for localhost and cluster CIDRs).

## 6.0) Deploy nomic-embed-text-v2-moe-GGUF on `knowl3` via Lemonade Server

Lemonade exposes an OpenAI-compatible embeddings endpoint:

- `POST /api/v1/embeddings`

Verify Lemonade is healthy (same checks as above), then test embeddings locally:

```bash
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/embeddings \
  -H 'Content-Type: application/json' \
  -d '{"model":"nomic-embed-text-v2-moe-GGUF","input":["hello world","goodbye world"]}'
```

Expected:

- HTTP 200
- A JSON response containing `data: [{ embedding: [...] }, ...]`

If you see `Download validation failed` when first loading the model, delete the model cache entry under `/var/snap/lemonade-server/common/cache/huggingface/hub/models--*nomic*` and retry the `POST /api/v1/embeddings` request.

## 6.1) Deploy bge-reranker-v2-m3-GGUF on `knowl3` via Lemonade Server

This section is the reference deployment path for the reranking model used by CodeKnowl.

Lemonade provides a reranking endpoint:

- `POST /api/v1/reranking`

Notes:

- This endpoint is only available for models using the `llamacpp` recipe.
- Results are returned in the original input order; clients sort by `relevance_score` descending.

### 6.1.1 Install / verify Lemonade Server

If Lemonade is not already installed on `knowl3`:

```bash
sudo snap install lemonade-server
sudo snap restart lemonade-server

sudo journalctl -u snap.lemonade-server.daemon.service -f
```

### 6.1.2 Verify Lemonade health

```bash
sudo ss -ltnp | egrep ':8000|:8001' || true

curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/health
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/models
```

### 6.1.3 Verify reranking works (local)

```bash
curl --noproxy localhost,127.0.0.1 -sS http://127.0.0.1:8000/api/v1/reranking \
  -H "Content-Type: application/json" \
  -d '{
    "model": "bge-reranker-v2-m3-GGUF",
    "query": "What is the capital of France?",
    "documents": [
      "Paris is the capital of France.",
      "Berlin is the capital of Germany.",
      "Madrid is the capital of Spain."
    ]
  }'
```

Expected:

- HTTP 200 with a JSON response containing `results: [{ index, relevance_score }, ...]`
- The document about Paris should have the highest score.

### 6.1.4 iGPU acceleration vs CPU-only fallback

On Ryzen-class mini PCs, iGPU offload is preferred when it is stable. If iGPU offload is not available or not stable, CPU-only is acceptable for initial validation.

Verification:

```bash
sudo journalctl -u snap.lemonade-server.daemon.service -n 200 --no-pager | egrep 'offloaded|ROCm0 model buffer|ngl|llama-server' || true
```

If you do not see GPU/offload signatures and the reranking endpoint still works correctly, treat the node as CPU-only for this model.

### 6.1.5 Model download validation / corruption recovery

If Lemonade returns errors like:

- `Download validation failed. Some files are incomplete or missing. Run the command again to resume.`
- `Download succeeded but failed to rename file: No such file or directory`

The most reliable recovery is to stop Lemonade, delete the corrupted model cache entry, and retry.

Example (bge reranker):

```bash
sudo systemctl stop lemonade-server.service || true
sudo rm -rf /var/snap/lemonade-server/common/cache/huggingface/hub/models--pqnet--bge-reranker-v2-m3-Q8_0-GGUF
sudo systemctl start lemonade-server.service || true
```

Then re-run the same `POST /api/v1/reranking` request to trigger a clean re-download.

## 7) Kubernetes scheduling patterns

### 7.1 Use node selectors (simple and effective)

For a workload that must run on `knowl1`, set:

- `nodeSelector: { codeknowl.model: qwen3-coder-30b }`

For `knowl2`:

- `nodeSelector: { codeknowl.model: gpt-oss-20b }`

For `knowl3`:

- `nodeSelector: { codeknowl.model: codet5 }`

### 7.2 Use taints/tolerations (optional)

If you want to prevent “random” workloads from landing on your model nodes, consider:

- Tainting the LLM nodes
- Adding tolerations only to the model-serving pods

This is optional but useful as the cluster grows.

## 8) Common failure modes and fixes (short list)

- **Local curl goes through proxy and fails (often 403)**
  - Use `curl --noproxy localhost,127.0.0.1 ...`
  - Ensure `/etc/environment` has correct `no_proxy` for snap/systemd services

- **Requests appear to fail like networking issues but are context limits**
  - Large payloads can exceed model context window
  - Reduce request size or adjust context size (tradeoff: memory)

- **Lemonade snap daemon crash-looping due to backend auto-detection**
  - In the original runbook, the durable fix was:
    - disable the snap daemon
    - run Lemonade under a custom `systemd` unit forcing a stable backend

- **Snap daemon logs show `--llamacpp: rocm not in {vulkan,cpu}`**
  - Apply the forced-vulkan workaround (`3.6`).
  - Verify `ss` shows `:8000` listening and `/api/v1/health` returns JSON.

## 9) Quick “it works” checklist

On `knowl1` and `knowl2`:

- `ss` shows ports 8000 and 8001 listening
- `/api/v1/health` returns JSON `{"status":"ok"...}`
- `/api/v1/models` lists the expected model
- Logs indicate GPU offload (`offloaded ... layers to GPU`)

On `knowl3`:

- CodeT5+ service/process starts reliably (Kubernetes or systemd)
- Embedding generation works for a small test input
- Lemonade `/api/v1/reranking` returns relevance scores for a small test query/doc set

---

If you want, I can extend this document with:

- A concrete Kubernetes manifest pattern for exposing `knowl1`/`knowl2` Lemonade endpoints behind ClusterIP Services.
- A “model router” pattern (one internal endpoint that routes to the correct node/model).
- A more specific CodeT5+ serving approach once you confirm how you want to host it (Python service vs integrated into the indexing pipeline).
