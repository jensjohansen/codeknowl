# Competitor Survey (Research Paper): Sourcegraph (Enterprise Self-Hosted)

## Executive summary
Sourcegraph is a commercial **code intelligence platform** centered around multi-repository code search, navigation, and organization-wide change workflows. It is a strong competitor/adjacent product to CodeKnowl on the “understand and operate on large codebases” axis, especially for enterprises that need self-hosting.

Sourcegraph is not marketed as a Code Property Graph (CPG) engine; its differentiator is operationalizing code search + codebase-wide change execution (and reporting) at scale.

## 1. Purpose and target users
### 1.1 Purpose
Enable teams to “search, write, and understand massive codebases” and execute large-scale refactors/migrations.

**Primary source:** https://sourcegraph.com/enterprise

### 1.2 Target users
- Large engineering orgs with many repos
- Platform engineering teams
- Security response teams (e.g., organization-wide vulnerability remediation)

**Primary source:** https://sourcegraph.com/enterprise

## 2. Core capabilities (publicly described)
From Sourcegraph’s Enterprise positioning:
- Multi-repo discovery and understanding
- Large-scale migrations/refactors via “Batch Changes”
- Tracking via dashboards (“Code Insights”)
- Vulnerability response workflows (find instances, replace across repos)

**Primary source:** https://sourcegraph.com/enterprise

## 3. Deployment and on-prem posture
Sourcegraph provides an “Enterprise Self-Hosted” deployment track and explicitly frames it as “running Sourcegraph on-prem.”

The self-hosted docs link to multiple deployment modes including:
- Docker Compose
- Kubernetes (Helm preferred)
- Machine images
- Single-node deployment
- Instance sizing and a resource estimator

**Primary sources:**
- https://sourcegraph.com/docs/self-hosted
- https://sourcegraph.com/docs/self-hosted/deploy

## 4. Architecture signals and operational implications
### 4.1 Self-hosted is a first-class path
The self-hosted documentation emphasizes robust, scalable deployment on Kubernetes, with Helm as the preferred deployment method.

**Primary source:** https://sourcegraph.com/docs/self-hosted/deploy

### 4.2 Built-in sizing/estimation mindset
The presence of a “resource estimator” and “instance sizing” docs is a notable product maturity signal and aligns with CodeKnowl’s need to be predictable on megalithic repos.

**Primary source:** https://sourcegraph.com/docs/self-hosted

## 5. Differentiators vs CodeKnowl
### 5.1 Differentiators
- Proven multi-repo scale focus, with operational workflows (batch changes + dashboards)
- Mature self-hosted ops surface (deploy/upgrade/sizing)

### 5.2 What Sourcegraph may not cover (CodeKnowl opportunities)
- Deep semantic program analysis in the “full CPG” sense (AST+CFG+PDG/dataflow overlays)
- A product-first “AI analyst report” experience grounded in explicit graph semantics (if CodeKnowl leans CPG/analysis)

## 6. Implications for CodeKnowl “minimum bar”
If Sourcegraph is a true competitor class, CodeKnowl should meet expectations around:
- Multi-repo indexing and search/navigation
- On-prem, self-hosted deployments with clear sizing guidance
- Codebase-wide change workflows (at least as a roadmap)

## References
- Product positioning: https://sourcegraph.com/enterprise
- Self-hosted docs: https://sourcegraph.com/docs/self-hosted
- Deployment overview: https://sourcegraph.com/docs/self-hosted/deploy
