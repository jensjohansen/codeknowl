# Graph DB Comparison for CodeKnowl: Memgraph vs Neo4j vs NebulaGraph

## Purpose
Validate CodeKnowl’s graph database choice (currently **NebulaGraph**) against two common alternatives (**Memgraph**, **Neo4j**) for an on-prem, large-repo “code understanding” system.

Focus areas:
- On-prem operability and scale
- HA/clustering
- Licensing/commercial constraints
- Query language and ecosystem

## 1. High-level conclusion (current recommendation)
- **NebulaGraph** is the best default fit for CodeKnowl’s stated direction: disk-backed, distributed scaling, on-prem control, and permissive OSS licensing (Apache 2.0).
- **Neo4j** is extremely mature and feature-rich, but the practical “enterprise-grade” requirements for HA/horizontal scale/security tend to push teams toward **Enterprise Edition** (commercial) while Community Edition is **GPLv3**.
- **Memgraph** is attractive for Cypher compatibility and developer experience, but has licensing constraints for the community edition (BSL) and (based on Memgraph’s own documentation) positions HA as an enterprise feature area.

This is a product decision, not just a technical decision: CodeKnowl wants to be MIT-licensed and on-prem friendly, so licensing + distributability matters.

## 2. Licensing / commercial constraints
### 2.1 NebulaGraph
NebulaGraph documentation states it is open under the **Apache 2.0 License**.

**Primary source:** https://docs.nebula-graph.io/3.8.0/1.introduction/1.what-is-nebula-graph/

### 2.2 Neo4j
Neo4j states Community Edition is **GPLv3**.

**Primary source:** https://neo4j.com/open-core-and-neo4j/

Neo4j pricing describes Community Edition as “GPL3-licensed” and explicitly calls out that it is for projects that don’t need automatic HA/horizontal scalability/beyond-basic security.

**Primary source:** https://neo4j.com/pricing/

### 2.3 Memgraph
Memgraph’s legal page provides links indicating:
- Community Edition uses **Business Source License (BSL)**
- Enterprise Edition uses a Memgraph Enterprise License

**Primary source:** https://memgraph.com/legal

## 3. HA / clustering posture
### 3.1 NebulaGraph
NebulaGraph documents a separation of compute and storage services (graphd vs storaged) and describes this as enabling scalability, HA, and cost flexibility.

**Primary source:** https://docs.nebula-graph.io/3.5.0/1.introduction/3.nebula-graph-architecture/1.architecture-overview/

NebulaGraph also documents role-based access control and LDAP integration.

**Primary source:** https://docs.nebula-graph.io/3.8.0/1.introduction/1.what-is-nebula-graph/

### 3.2 Neo4j
Neo4j pricing positions Enterprise Edition as including:
- unlimited horizontal read scaling with replication
- fine-grained access controls
- high availability

**Primary source:** https://neo4j.com/pricing/

### 3.3 Memgraph
Memgraph’s clustering docs frame “High availability with Memgraph Enterprise” as a topic area and link to operational guides for replication and HA.

**Primary source:** https://memgraph.com/docs/clustering/high-availability

## 4. Query language and developer ecosystem
### 4.1 NebulaGraph
NebulaGraph states nGQL is “openCypher-compatible”.

**Primary source:** https://docs.nebula-graph.io/3.8.0/1.introduction/1.what-is-nebula-graph/

### 4.2 Neo4j
Neo4j is the originator of Cypher and positions openCypher under Apache 2.0.

**Primary source:** https://neo4j.com/open-core-and-neo4j/

### 4.3 Memgraph
Memgraph positions itself as compatible for Neo4j developers and uses Cypher-like querying; licensing and HA differences may affect production posture.

**Primary source:** https://memgraph.com/legal

## 4.4 Clarification: NebulaGraph is not Spark (but has Spark-based graph computing tooling)
NebulaGraph’s core database runtime is implemented as its own services (e.g., meta service + graph service + storage service) and does not require Spark.

However, NebulaGraph also publishes a separate “NebulaGraph Algorithm” component for graph computing that:
- Lists Spark (2.4 or 3.x) and Scala as prerequisites.
- Reads graph data from NebulaGraph into DataFrames via the NebulaGraph Spark Connector.
- Transforms DataFrames into a GraphX graph and runs GraphX/self-implemented algorithms.

This is an **optional analytics/graph-computing library**, not the database query engine.

**Primary source:** https://docs.nebula-graph.io/3.8.0/graph-computing/nebula-algorithm/

## 5. CodeKnowl-specific evaluation criteria (what matters for us)
### 5.1 Must-haves for CodeKnowl
- Distributed scaling / partitioning strategy suitable for “megalithic” repos
- Disk-backed persistence
- A query language compatible with typical graph traversal and pattern match workflows
- OSS license compatibility with an MIT-licensed project and on-prem deployments

### 5.2 How the options map
- NebulaGraph:
  - Strong fit for distributed scaling and permissive OSS licensing
  - nGQL is openCypher-compatible, reducing migration friction
- Neo4j:
  - Strong maturity, but OSS Community Edition is GPLv3 and enterprise-grade needs tend to point to paid Enterprise
- Memgraph:
  - Strong developer ergonomics for Cypher users
  - Licensing model (BSL) plus enterprise feature segmentation may be misaligned with CodeKnowl’s OSS posture

## 6. Recommended next validation steps
- Run a small-scale benchmark with a representative CodeKnowl schema and query set:
  - symbol lookup
  - callers/callees traversal
  - cross-repo dependency traversal
  - impact analysis path queries
- Confirm operational requirements:
  - backup/restore
  - cluster upgrades
  - failure recovery
- Confirm licensing plan for redistribution:
  - “integrate vs redistribute” policy for graph DB and associated tooling

## References
- Memgraph legal: https://memgraph.com/legal
- Memgraph HA docs: https://memgraph.com/docs/clustering/high-availability
- Neo4j open-core licensing FAQ: https://neo4j.com/open-core-and-neo4j/
- Neo4j pricing (community vs enterprise positioning): https://neo4j.com/pricing/
- NebulaGraph “What is” (Apache 2.0, nGQL openCypher-compatible, RBAC/LDAP): https://docs.nebula-graph.io/3.8.0/1.introduction/1.what-is-nebula-graph/
- NebulaGraph architecture overview (meta/graph/storage separation): https://docs.nebula-graph.io/3.5.0/1.introduction/3.nebula-graph-architecture/1.architecture-overview/
