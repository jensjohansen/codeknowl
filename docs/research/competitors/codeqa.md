# Competitor Survey (Research Paper): CodeQA.ai (On-Prem AI Code Search)

## Executive summary
CodeQA.ai positions itself as an **on-prem AI code search** and multi-repository code intelligence product. Of the commercial tools we’ve seen so far, CodeQA’s positioning is among the closest to CodeKnowl’s “AI codebase analyst” goal.

Public material emphasizes:
- Cross-repository indexing
- Blending semantic search with deterministic symbol search
- On-prem vs cloud tradeoffs and enterprise security controls (RBAC, audit logging, encryption)

## 1. Purpose and target users
### 1.1 Purpose
“Ask and understand your codebase” with secure and flexible deployment, multi-repository intelligence, and legacy code understanding.

**Primary source:** https://www.codeqa.ai/

### 1.2 Target users
- Enterprise engineering orgs with many repos
- Teams with compliance and data residency needs
- Developers needing faster discovery/reuse across codebases

## 2. Claimed core capabilities (publicly described)
### 2.1 Cross-repository indexing
The CodeQA blog describes cross-repository indexing as crucial for microservice architectures and organizations managing many projects.

**Primary source:** https://www.codeqa.ai/blog-post/ai-powered-code-search-enterprise-teams

### 2.2 Hybrid search: semantic + symbol/regex
The blog explicitly frames AI search as complementary to symbol search and regex.

**Primary source:** https://www.codeqa.ai/blog-post/ai-powered-code-search-enterprise-teams

## 3. Deployment and security posture (publicly described)
The blog discusses enterprise “security and deployment considerations”, including:
- On-prem vs cloud hosting tradeoffs
- Role-based access control and audit/compliance expectations

**Primary source:** https://www.codeqa.ai/blog-post/ai-powered-code-search-enterprise-teams

The product page states “cloud, on-premise, or hybrid” deployment options.

**Primary source:** https://www.codeqa.ai/

## 4. Likely architecture shape (inferred cautiously)
Based on public claims (without over-speculating):
- Requires a multi-repo indexing pipeline
- Requires a retrieval system supporting:
  - semantic embeddings
  - deterministic symbol index
  - authorization-aware results (repo-level permissions)
- Requires some form of “contextual indexing” / code understanding layer

## 5. Differentiators vs CodeKnowl
### 5.1 Differentiators
- Very direct positioning as on-prem AI code search
- Strong emphasis on enterprise concerns: RBAC, audit logging, encryption at rest

### 5.2 CodeKnowl opportunities
- If CodeKnowl leans into CPG + multi-store retrieval (graph + vector) and produces analyst-grade reports with citations and deterministic provenance, it may differentiate from a search-first product.
- CodeKnowl can also explicitly integrate SAST/DAST signals into the knowledge graph and reports (SonarQube/Semgrep/ZAP), beyond search.

## 6. Implications for CodeKnowl “minimum bar”
If CodeQA is the competitor to beat, CodeKnowl should treat these as baseline expectations:
- Cross-repository indexing
- Semantic + deterministic symbol search
- Enterprise permission model alignment (repo-level access control)
- Audit logging and security posture suitable for on-prem deployments

## References
- Product page: https://www.codeqa.ai/
- Blog: “AI-powered code search for enterprise teams”: https://www.codeqa.ai/blog-post/ai-powered-code-search-enterprise-teams
