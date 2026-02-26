# Suggested Hardware Configuration for CodeKnowl (On-Prem, Local-Model-First)

CodeKnowl is designed to be deployed on-premises, using locally hosted models and local data stores. The goal is straightforward:

- Keep source code and derived code intelligence inside your network boundary.
- Minimize external dependencies.
- Deliver an AI “codebase analyst” experience that’s fast enough for daily engineering work.

This write-up is intentionally opinionated and optimized for pragmatic deployments. You should validate:

- OS and driver compatibility for your chosen node hardware.
- Your organization’s security requirements for remote access (VPN/tunnels).
- Capacity needs based on repo size, indexing frequency, and number of concurrent engineers.

This article documents the hardware and deployment assumptions I recommend for a practical, security-conscious CodeKnowl installation.

## Why on-prem (and why a dedicated LAN)

If you’re building developer-facing AI that needs broad access to internal repositories, build tooling, and documentation, the security blast radius can expand quickly.

My recommendation is to run CodeKnowl on a **stand-alone LAN** (physically or logically isolated) and treat it like an internal platform service:

- The cluster has **no direct inbound exposure** from the Internet.
- The cluster has **minimal outbound** network access (primarily to reach Git hosts and optionally OS/package mirrors).
- Access from engineers is gated through a small number of carefully controlled entry points.

This reduces the number of touch points between:

- The Internet
- Your corporate network
- Your code and build systems

In practice, this makes the “local-model-first” story real: the cluster becomes a contained environment that you can audit, monitor, and reason about.

## Exposing services safely: VPN and tunnels

Engineers still need access to CodeKnowl’s services (VS Code extension backends, web UIs, APIs, metrics). The recommended pattern is:

- **VPN** access into the dedicated LAN, or
- **Tunneling** access via a service like Cloudflare Tunnel

The key is that the tunnel/VPN endpoint becomes the control plane for access:

- Central authentication
- Device posture checks (if you use them)
- Logging and auditing
- Easy revocation

Even if the cluster remains isolated, you can still provide a clean and convenient developer experience.

## The reference cluster: 3-node Kubernetes

A simple and effective starting point is a **three-node Kubernetes cluster**, with each node optimized for a specific role.

### Node roles

- **Node A (LLM inference)**
  - Runs one “large” model via `lemonade-server`.
  - Example: `Qwen3-Coder-30B-A3B-Instruct-GGUF`.

- **Node B (LLM inference)**
  - Runs a second “large” model via `lemonade-server`.
  - Example: `gpt-oss-20b-mxfp4-GGUF`.

- **Node C (embeddings and CPU-heavy services)**
  - Runs CodeT5+ for embeddings / code representation.
  - Runs CPU-bound platform services (ingestion/indexing orchestration, schedulers, etc.).

This separation gives you predictable performance and avoids resource contention.

## Why AMD Ryzen AI 300 series for LLM nodes

For the LLM inference nodes, I recommend **AMD Ryzen AI 300 series** systems.

### The practical reason: the 890M iGPU is “enough”

In this design, the 890M iGPU in the stronger Ryzen AI 300 SoCs is adequate to serve:

- `Qwen3-Coder-30B-A3B-Instruct-GGUF`
- `gpt-oss-20b-mxfp4-GGUF`

…at useful speeds when deployed with **AMD’s `lemonade-server` on Linux**.

The result is a compelling cost/performance profile:

- No discrete GPU required for the initial deployment
- Lower power and thermal overhead
- Hardware that’s easier to source than high-end GPU servers

### One model per node

A simple operational rule that keeps things stable:

- Run **one large model per node**.

This minimizes noisy-neighbor effects and makes it clear how to scale:

- If you need more throughput, add another node.
- If you need a different model, dedicate a node.

## Why AMD Ryzen AI 8945HS for CodeT5+

For the CodeT5+ node, I recommend an **AMD Ryzen AI 8945HS**.

CodeT5+ runs well:

- In **CPU-only** mode, and
- In **CPU + iGPU** mode

This makes the embeddings node less sensitive to GPU constraints. It also means you can allocate the “best” iGPU capacity to the LLM inference nodes, where it tends to matter most.

## OS choice: Ubuntu 25

I recommend **Ubuntu 25** for the node operating system.

The primary rationale is operational simplicity:

- `apt` makes it easier to install and update dependencies.
- You can keep local builds to a minimum.

For an on-prem system, maintainability is a feature. If you can patch hosts reliably and rebuild images predictably, you’ll spend more time improving CodeKnowl—and less time debugging machine drift.

## Memory sizing: 64GB RAM per node (and why it matters)

I recommend **64GB of RAM per node**.

In practice:

- The two large models will often consume **~20–30GB RAM** each (depending on quantization, runtime settings, and concurrency).

### iGPU memory allocation via AMD TTM

A key detail for AMD iGPU deployments is memory allocation.

Recommended approach:

- Set the **UMA buffer** to the **smallest** value in firmware/BIOS.
- Allow **TTM** to dynamically allocate what is actually needed.

This avoids permanently reserving large chunks of RAM for the iGPU and leaves more memory available for:

- Indexing tasks
- Vector DB and graph DB caches
- General cluster overhead

On the CodeT5+ node (8945HS), 64GB is typically sufficient to run CPU-bound services comfortably while still having headroom for embeddings workloads.

## AMD vs Intel (and why I chose AMD)

It’s possible to use **Intel Ultra 9** processors to a similar current effect.

I chose AMD Ryzen primarily because:

- The **NPU** roadmap is promising.
- Once high-quality Linux support is available, the NPU should materially improve model performance and efficiency for certain workloads.

Even without immediate NPU acceleration, the iGPU-focused approach already provides a strong baseline for local inference.

## A concrete reference configuration (summary)

If you want a single “starting point” to copy/paste into a planning doc, here it is:

- **Cluster topology**: 3-node Kubernetes cluster on an isolated LAN
- **Remote access**: VPN or Cloudflare Tunnel (treat as the only ingress)
- **Node A**: AMD Ryzen AI 300 series + 64GB RAM (LLM via lemonade-server)
- **Node B**: AMD Ryzen AI 300 series + 64GB RAM (LLM via lemonade-server)
- **Node C**: AMD Ryzen AI 8945HS + 64GB RAM (CodeT5+ + CPU services)
- **OS**: Ubuntu 25
- **Firmware**: UMA buffer minimal; rely on AMD TTM for dynamic allocation

## A practical bill of materials (what to buy)

At a minimum:

- **3x compute nodes**
  - 2x AMD Ryzen AI 300 series nodes (LLM inference)
  - 1x AMD Ryzen AI 8945HS node (CodeT5+ + CPU services)
- **RAM**
  - 64GB per node
- **Storage**
  - Sufficient local SSD/NVMe for:
    - cloned repositories
    - indexing artifacts
    - Memgraph and Qdrant persistent storage
- **Networking**
  - A dedicated switch/VLAN or otherwise isolated LAN segment
  - A controlled ingress point for VPN/tunnel termination
- **Operational essentials**
  - Reliable backups for persistent volumes
  - Basic metrics/log collection for cluster health and indexing jobs

## Closing notes

This is a pragmatic configuration aimed at:

- Small-to-medium teams
- On-prem deployments with security constraints
- “Local first” AI workflows that must stay close to the code

As CodeKnowl evolves, the right answer may shift (especially as Linux NPU support matures). But this baseline is a strong starting point that balances cost, capability, and operational simplicity.
