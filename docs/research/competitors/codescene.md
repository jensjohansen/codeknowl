# Competitor Survey (Research Paper): CodeScene (On-Prem)

## Executive summary
CodeScene is a commercial “behavioral code analysis” product focused on prioritizing technical debt, delivery risk, and hotspots by analyzing the **evolution** of a codebase and overlaying organizational/people signals. It competes with CodeKnowl in the broader “codebase understanding and engineering decision support” space, but it is not a CPG engine and is not framed as an AI code analyst.

For CodeKnowl, CodeScene is important less as a replacement and more as a benchmark for:
- “Where should we look first?” (hotspots)
- Risk/priority ranking
- Integrations (issue trackers, PR feedback)
- Organization/knowledge-loss analytics

## 1. Purpose and target users
### 1.1 Purpose
CodeScene describes itself as:
- A “quality visualization tool for software”
- Used to prioritize technical debt and detect delivery risks
- Adds “people side” insights (coordination bottlenecks, knowledge loss, Conway’s Law alignment)

**Primary source:** https://codescene.com/resources/faq

### 1.2 Target users
- Engineering leadership prioritizing debt and delivery risk
- Teams planning refactors with minimal disruption
- Platform/DevEx teams who integrate analysis into PR and notifications

## 2. Key capabilities (publicly described)
From the FAQ:
- Hotspot analysis and X-Ray (evolution per function/method in a hotspot)
- PR integration for “real-time feedback” and soft quality gates
- Socio-technical and organizational analytics
- Integrations with Jira/Trello/Azure DevOps/GitHub Issues/GitLab PM/YouTrack

**Primary source:** https://codescene.com/resources/faq

## 3. Deployment and on-prem posture
CodeScene provides explicit “on-prem” installation guidance, including a “deploy using executable JAR” path.

The on-prem JAR deploy prerequisites include:
- Java JDK 17+
- Git client
- SSH client

**Primary source:** https://codescene.com/product/free-trial/on-prem/jar/deploy

The FAQ states that “On-Prem supports any git provider on a basic level (you can specify any git remote URL).”

**Primary source:** https://codescene.com/resources/faq

## 4. Differentiators vs CodeKnowl
### 4.1 Differentiators
- Temporal/evolution analysis (not just snapshot)
- Strong prioritization/risk heuristics for hotspots
- Socio-technical analytics beyond code semantics

### 4.2 Gaps/opportunities for CodeKnowl
- CodeScene is not positioned as:
  - a code property graph platform
  - an AI-first “analyst agent”
  - a semantic program analysis system (dataflow/taint/etc.)

CodeKnowl can add value by combining:
- Graph semantics (CPG-like structure)
- RAG + citations
- Risk/priority ranking inspired by CodeScene-style hotspot methodology

## 5. Implications for CodeKnowl “minimum bar”
If you want CodeKnowl reports to be taken seriously by engineering leaders, consider borrowing CodeScene-style outputs:
- Hotspot ranking and “why this area is risky” explanations
- Change-risk heuristics and refactoring sequencing
- Integrations for surfacing findings in PRs/issue trackers

## References
- Feature/positioning FAQ: https://codescene.com/resources/faq
- On-prem JAR deploy prerequisites: https://codescene.com/product/free-trial/on-prem/jar/deploy
