# Deploying CodeKnowl Models on a 3-Node Mini-PC Kubernetes Cluster (knowl1/knowl2/knowl3)

This document is a shareable, “no-real-hostnames” guide for deploying the three model services used by CodeKnowl onto a small on-prem Kubernetes cluster.

It is based on the practical lessons captured in `docs/lemonade-server-hx370-linux-runbook.md`, but rewritten to assume a clean 3-node setup with **generic node names**.

## Scope

You will deploy:

- `Qwen3-Coder-30B-A3B-Instruct-GGUF` on `knowl1` via **Lemonade Server**
- `gpt-oss-20b-mxfp4-GGUF` on `knowl2` via **Lemonade Server**
- `CodeT5+` on `knowl3` (CPU-only or CPU+iGPU)

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
- `codeknowl.model=codet5`

Example:

```bash
kubectl label node knowl1 codeknowl.role=llm codeknowl.model=qwen3-coder-30b --overwrite
kubectl label node knowl2 codeknowl.role=llm codeknowl.model=gpt-oss-20b --overwrite
kubectl label node knowl3 codeknowl.role=embeddings codeknowl.model=codet5 --overwrite
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

## 4) Deploy Qwen3-Coder on `knowl1`

### 4.1 Configure model selection

Lemonade exposes an OpenAI-compatible API and typically manages model downloads into the snap cache directory under:

- `/var/snap/lemonade-server/common/.cache/`

After you’ve configured Lemonade to use `Qwen3-Coder-30B-A3B-Instruct-GGUF`, verify that the GGUF exists and is intact.

Example pattern (adjust to the actual cached path for your model):

```bash
sudo ls -lh /var/snap/lemonade-server/common/.cache/huggingface/hub/ | head
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

## 9) Quick “it works” checklist

On `knowl1` and `knowl2`:

- `ss` shows ports 8000 and 8001 listening
- `/api/v1/health` returns JSON `{"status":"ok"...}`
- `/api/v1/models` lists the expected model
- Logs indicate GPU offload (`offloaded ... layers to GPU`)

On `knowl3`:

- CodeT5+ service/process starts reliably (Kubernetes or systemd)
- Embedding generation works for a small test input

---

If you want, I can extend this document with:

- A concrete Kubernetes manifest pattern for exposing `knowl1`/`knowl2` Lemonade endpoints behind ClusterIP Services.
- A “model router” pattern (one internal endpoint that routes to the correct node/model).
- A more specific CodeT5+ serving approach once you confirm how you want to host it (Python service vs integrated into the indexing pipeline).
