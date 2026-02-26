<!--
File: docs/README.md
Purpose: Describe the documentation set and the discipline for keeping it current.
Product/business importance: Keeps product intent, architecture, and delivery tracking aligned as the code evolves.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
-->

# CodeKnowl Documentation

This folder contains the authoritative product and engineering documentation for CodeKnowl.

## Key documents

- `prd-revised.md`
  - Product requirements and milestone acceptance criteria.
- `architecture-and-design.md`
  - Tactical architecture mapped to PRD milestones.
- `CODING_STANDARDS_AND_DOD.md`
  - Coding standards and Definition of Done (DoD).
- `implementation-plan-tracker.md`
  - Execution checklist with milestone work item statuses.

## Contribution discipline

- Update `implementation-plan-tracker.md` whenever milestone work lands.
- Keep PRD and architecture aligned; if they drift, update PRD first.
- Treat this folder as an engineering deliverable: docs must be accurate, current, and referenced by code/CI.
