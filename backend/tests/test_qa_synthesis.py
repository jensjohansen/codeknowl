import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
sys.path.insert(0, str(_SRC))

from codeknowl.ask import answer_with_llm_synthesis  # noqa: E402


class _StubLlm:
    def __init__(self, name: str, reply: str):
        self._name = name
        self._reply = reply
        self.calls: list[dict[str, str]] = []

    def chat(self, *, system: str, user: str) -> str:  # noqa: ANN001
        self.calls.append({"system": system, "user": user})
        return self._reply


class TestQaSynthesis(unittest.TestCase):
    def test_synthesis_calls_responders_and_synth(self) -> None:
        coding = _StubLlm("coding", "CODING_ANSWER")
        general = _StubLlm("general", "GENERAL_ANSWER")
        synth = _StubLlm("synth", "FINAL_ANSWER")

        result = answer_with_llm_synthesis(
            coding_llm=coding,
            general_llm=general,
            synth_llm=synth,
            artifacts={"files": [], "symbols": [], "calls": []},
            question="What does foo do?",
            semantic_hits=[
                {
                    "chunk_id": "c1",
                    "score": 0.9,
                    "file_path": "a.py",
                    "start_line": 1,
                    "end_line": 2,
                    "text": "x" * 5000,
                }
            ],
        )

        self.assertEqual(result.answer, "FINAL_ANSWER")
        self.assertEqual(len(coding.calls), 1)
        self.assertEqual(len(general.calls), 1)
        self.assertEqual(len(synth.calls), 1)

        synth_user = synth.calls[0]["user"]
        self.assertIn("CODING_ANSWER", synth_user)
        self.assertIn("GENERAL_ANSWER", synth_user)

    def test_evidence_caps_reduce_semantic_hit_text(self) -> None:
        coding = _StubLlm("coding", "A")
        general = _StubLlm("general", "B")
        synth = _StubLlm("synth", "C")

        env = {
            "CODEKNOWL_QA_SEMANTIC_HITS_K": "1",
            "CODEKNOWL_QA_HIT_MAX_CHARS": "10",
            "CODEKNOWL_QA_EVIDENCE_MAX_TEXT_CHARS": "10",
            "CODEKNOWL_QA_EVIDENCE_MAX_JSON_CHARS": "200",
        }

        with patch.dict(os.environ, env, clear=False):
            _ = answer_with_llm_synthesis(
                coding_llm=coding,
                general_llm=general,
                synth_llm=synth,
                artifacts={"files": [], "symbols": [], "calls": []},
                question="What is foo?",
                semantic_hits=[
                    {
                        "chunk_id": "c1",
                        "score": 0.9,
                        "file_path": "a.py",
                        "start_line": 1,
                        "end_line": 2,
                        "text": "0123456789" * 20,
                    }
                ],
            )

        responder_user = coding.calls[0]["user"]
        self.assertIn("Evidence bundle (JSON):", responder_user)

        # Ensure the full long text is not included in prompt.
        self.assertNotIn("0123456789" * 20, responder_user)

        # Evidence JSON should be bounded in size in the prompt.
        evidence_json = responder_user.split("Evidence bundle (JSON):\n", 1)[1].split("\n\nReturn", 1)[0]
        self.assertLessEqual(len(evidence_json), 200)


if __name__ == "__main__":
    unittest.main()
