# Deploying NebulaGraph for CodeKnowl (Kubernetes + Rook-Ceph)

## Why we are doing this

CodeKnowl needs a graph database to store and query a code graph (symbols, references, call relationships, module boundaries, and other relationships extracted from source repositories). The goals are:

- Handle large and "megalithic" repositories without requiring the entire graph to fit in RAM.
- Prefer disk-backed persistence and predictable operations over peak in-memory speed.
- Run fully on-prem in Kubernetes, using existing storage infrastructure.

## Why we are considering NebulaGraph

NebulaGraph is a distributed graph database that separates compute/query from storage:

- The Graph Service (`nebula-graphd`) handles querying.
- The Storage Service (`nebula-storaged`) handles persistent storage.
- The Meta Service (`nebula-metad`) manages metadata (schema, cluster management, and privileges).

Primary sources:

- NebulaGraph architecture overview describes the separation of storage and computing and the `nebula-graphd` vs `nebula-storaged` process split:
  - https://docs.nebula-graph.io/3.8.0/1.introduction/3.nebula-graph-architecture/1.architecture-overview/
- NebulaGraph storage service documentation states NebulaGraph uses a built-in KVStore with RocksDB as the local storage engine:
  - https://docs.nebula-graph.io/3.2.0/1.introduction/3.nebula-graph-architecture/4.storage-service/

This aligns with the operational constraint that CodeKnowl’s code graph must remain durable, disk-backed, and scalable.

## A critical clarification (what NebulaGraph is and is not)

NebulaGraph does **not** use PostgreSQL as its storage backend.

- NebulaGraph persistence is implemented in its own storage layer (`nebula-storaged`) backed by RocksDB (see the storage service documentation link above).

If you also deploy PostgreSQL (CNPG) in the cluster, it should be treated as a separate database for CodeKnowl application metadata (ingestion jobs, run history, configuration, etc.), not as NebulaGraph storage.

## Cluster assumptions

This guide assumes:

- Kubernetes cluster with three nodes.
- Rook-Ceph is installed.
- Each node contributes an unformatted dedicated NVMe drive to Ceph.
- You have Ceph-backed storage classes:
  - `rook-ceph-block` (RBD / block PVCs)
  - `rook-ceph-bucket` (S3-compatible object storage via RGW)

## Namespace strategy

Create a dedicated application namespace:

- `codeknowl`

Rationale:

- The graph’s size and workload is highly application-specific.
- Graph databases are sensitive to dataset size; deploying a dedicated graph cluster per application avoids cross-project contention.
- It reduces cross-namespace secret propagation (a frequent operational footgun on Kubernetes).

## Storage strategy (Rook-Ceph)

### Block vs SharedFS

Use **Ceph block** (`rook-ceph-block`) for NebulaGraph persistence:

- `nebula-storaged`: requires persistent storage (graph data).
- `nebula-metad`: requires persistent storage (cluster metadata).
- `nebula-graphd`: can be stateless.

Do not use shared filesystems (CephFS / SharedFS) for NebulaGraph’s core storage.

### Starting PVC sizes (reasonable defaults)

For a three-node cluster intended to successfully ingest and query real repos without immediately resizing storage:

- `metad`: `10Gi` per pod
- `storaged`: `200Gi` per pod

PVC expansion for Ceph RBD is typically straightforward (assuming the storage class allows expansion), so these can be increased later as you observe actual growth.

## Topology recommendation (3-node cluster)

Recommended initial topology:

- `metad`: 3 replicas (quorum)
- `storaged`: 3 replicas (spread across the three nodes)
- `graphd`: 2 replicas (redundant query tier without over-consuming CPU/RAM)

You can scale `graphd` horizontally later if query throughput becomes the bottleneck.

## Installation overview (how NebulaGraph is normally deployed on Kubernetes)

NebulaGraph is commonly deployed on Kubernetes using the Nebula Operator (installed via Helm), which manages the NebulaGraph cluster resources.

NebulaGraph Studio (the browser UI) is deployed separately.

Official Operator docs (Helm-based install path):

- https://docs.nebula-graph.io/3.5.0/nebula-operator/3.deploy-nebula-graph-cluster/3.2create-cluster-with-helm/
- Operator guide (repo documentation): https://raw.githubusercontent.com/vesoft-inc/nebula-operator/master/doc/user/operator_guide.md

## Step-by-step installation

### 0) Prerequisites

- `kubectl` access to the cluster.
- `helm` installed locally.
- Rook-Ceph is healthy and `rook-ceph-block` exists.

### 1) Create the namespace

```bash
kubectl create namespace codeknowl
```

### 2) Install Nebula Operator (separate namespace)

Nebula Operator is installed first (as a prerequisite) and then used to manage one or more NebulaGraph clusters.

```bash
helm repo add nebula-operator https://vesoft-inc.github.io/nebula-operator/charts
helm repo update

kubectl create namespace nebula-operator-system

helm upgrade --install nebula-operator nebula-operator/nebula-operator \
  --namespace=nebula-operator-system
```

### 3) Install a NebulaGraph cluster into `codeknowl`

This follows the upstream “create cluster with Helm” flow, but uses `helm upgrade --install` so it is safe to re-run.

Note: Some older NebulaGraph documentation examples use `--set nebula.metad.dataStorage=...` and `--set nebula.storaged.dataStorage=...`. For `nebula-operator/nebula-cluster` chart `1.8.6`, those keys do not apply. Use the key names from `helm show values nebula-operator/nebula-cluster`.

```bash
export NEBULA_CLUSTER_NAME=nebulagraph
export NEBULA_CLUSTER_NAMESPACE=codeknowl
export STORAGE_CLASS_NAME=rook-ceph-block

helm upgrade --install "${NEBULA_CLUSTER_NAME}" nebula-operator/nebula-cluster \
  --namespace="${NEBULA_CLUSTER_NAMESPACE}" \
  --set nameOverride="${NEBULA_CLUSTER_NAME}" \
  --set nebula.storageClassName="${STORAGE_CLASS_NAME}" \
  --set nebula.metad.dataVolume.storage=10Gi \
  --set nebula.storaged.dataVolumes[0].storage=200Gi
```

If you want to explicitly set replica counts (instead of relying on chart defaults), inspect the chart values and add the appropriate `--set` keys:

```bash
helm show values nebula-operator/nebula-cluster | less
```

### 4) Deploy NebulaGraph Studio (UI)

Deploy NebulaGraph Studio in the `codeknowl` namespace.

### 5) Verify the cluster

- Verify pods:

```bash
kubectl -n codeknowl get pods
```

- Verify PVCs:

```bash
kubectl -n codeknowl get pvc
```

- Connect with `nebula-console` and run a basic command (for example `SHOW HOSTS;`).

### 6) Operational checks (how to know you sized storage correctly)

After ingesting the first real repository:

- Observe `storaged` PVC usage growth.
- Capture:
  - total vertices/edges
  - space/partition counts
- Use those measurements to forecast how many repos of similar scale fit before PVC expansion.

## What about PostgreSQL / CNPG?

If you deploy PostgreSQL via CloudNativePG (CNPG), treat it as a separate concern:

- Use it for CodeKnowl application metadata (jobs, run history, configuration, etc.).
- Back it up to Ceph RGW (S3) using the CNPG ObjectStore pattern.

Do not describe it as a "NebulaGraph backend".
