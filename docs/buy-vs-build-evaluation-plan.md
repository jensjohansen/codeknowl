# CodeKnowl — Buy vs Build Evaluation Plan

## Purpose
Define how CodeKnowl will evaluate whether to continue building the platform as designed vs adopting/extending an existing product or framework.

This is an execution plan (not an ITD). Any resulting decisions should be recorded in the ITD register.

## Scope of evaluation
The evaluation focuses on whether an existing solution can satisfy the revised PRD goals:

- On-prem / local-first operation
- Deterministic, traversable code relationships (CPG-style) plus semantic retrieval
- IDE-first experience with citations
- Incremental indexing
- Enterprise-aligned auth and repo-level access control
- MIT-friendly OSS viability

## Options to evaluate
Shortlist candidates and compare them against the criteria below. Candidates may include:

- Existing code intelligence platforms
- Code graph frameworks / parsers / CPG toolchains
- “RAG-only” code search systems

## Evaluation criteria

### Functional fit
- Repo ingestion and indexing
- Relationship navigation (symbols, calls, dependencies)
- Hybrid retrieval (graph traversal + semantic)
- Citations and traceability
- Incremental updates
- Multi-repo scoping

### Non-functional fit
- On-prem deployment viability
- Performance at target repo sizes
- Operational complexity
- Observability and failure handling

### Security and compliance
- AuthN/AuthZ integration
- Audit logging
- Air-gapped viability (where required)

### Licensing / OSS viability
- Can CodeKnowl remain MIT-licensed and publishable on GitHub?
- Are required dependencies redistributable / permissively licensed?
- Do any components impose source-available or restrictive terms?

### Extensibility
- Ability to add new languages and extractors
- Ability to add new storage backends or swap components via ITDs

### Total cost
- Licensing cost (if any)
- Hardware cost
- Maintenance burden

## Method
1. Pick 2–4 candidates for a short technical spike.
2. For each candidate:
   - run an indexing POC on representative repos
   - validate relationship queries and citation quality
   - measure indexing time and incremental update feasibility
   - record deployment assumptions
   - record licensing findings with primary sources
3. Summarize results in a short comparison document.
4. Make a recommendation and record any technical decision as an ITD.

## Deliverables
- Candidate shortlist and selection rationale
- Comparison summary document
- Recommendation: continue building vs adopt/extend

## Owners
- Decision owner:
- Technical evaluator(s):
- Licensing reviewer:

## Timeline
- Start:
- Target completion:
