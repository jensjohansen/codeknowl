# CodeKnowl Coding Standards

This directory contains coding standards and quality gates for the CodeKnowl project.

## Docstring/JSDoc Requirement

All publicly accessible symbols must have explanatory docstrings (Python) or JSDoc (TypeScript) that explain the rationale (“why”) behind the code, not just what it does.

### Enforcement

- CI runs `scripts/check-docstrings.py` on every push/PR to prevent regressions.
- The script checks:
  - Python: All public functions, classes, and methods (names not starting with `_`) have docstrings.
  - TypeScript: All exported functions have JSDoc comment blocks (`/** ... */`).

### How to Run Locally

```bash
python3 scripts/check-docstrings.py
```

If the script reports missing docstrings, add them before committing.
