"""File: backend/tests/test_reranker.py
Purpose: Verify deterministic reranker behavior used to reorder semantic retrieval hits.
Product/business importance: Ensures reranking improves evidence selection deterministically when configured.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
sys.path.insert(0, str(_SRC))

from codeknowl.reranker import OverlapReranker  # noqa: E402


class TestOverlapReranker(unittest.TestCase):
    def test_overlap_scores_prioritize_more_matching_identifiers(self) -> None:
        reranker = OverlapReranker()
        query = "Where is function build_file_inventory defined?"
        documents = [
            "This document mentions nothing relevant.",
            "The function build_file_inventory collects files.",
            "The function build_file_inventory is defined here.",
        ]

        scores = reranker.rerank(query=query, documents=documents)

        self.assertEqual(len(scores), len(documents))
        self.assertGreater(scores[2], scores[1])
        self.assertGreater(scores[1], scores[0])


if __name__ == "__main__":
    unittest.main()
