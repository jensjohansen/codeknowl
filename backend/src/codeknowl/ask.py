"""File: backend/src/codeknowl/ask.py
Purpose: Build best-effort evidence bundles from snapshot artifacts and (optionally) generate LLM-backed answers.
Product/business importance: Enables Milestone 1 'ask' flows that return semi-intelligent answers grounded in citations.

Copyright (c) 2026 John K Johansen
License: MIT (see LICENSE)
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from typing import Any

from codeknowl.llm import OpenAiCompatibleClient
from codeknowl.query import explain_file_stub, find_callers_best_effort, where_is_symbol_defined


@dataclass(frozen=True)
class AskResult:
    answer: str
    citations: list[dict[str, Any]]
    evidence: dict[str, Any]


def _limit_text(text: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    if len(text) <= max_chars:
        return text
    if max_chars <= 3:
        return text[:max_chars]
    return text[: max_chars - 3] + "..."


def constrain_semantic_hits(
    semantic_hits: list[dict[str, Any]] | None,
    *,
    max_hits: int,
    max_hit_text_chars: int,
    max_total_text_chars: int,
) -> list[dict[str, Any]]:
    if not semantic_hits:
        return []

    hits = [h for h in semantic_hits if isinstance(h, dict)]
    hits = hits[: max(0, int(max_hits))]

    remaining = max(0, int(max_total_text_chars))
    out: list[dict[str, Any]] = []
    for h in hits:
        text = str(h.get("text") or "")
        cap = min(max(0, int(max_hit_text_chars)), remaining) if remaining else 0
        item = dict(h)
        item["text"] = _limit_text(text, max_chars=cap)
        remaining = max(0, remaining - len(item["text"]))
        out.append(item)
        if remaining <= 0:
            break

    return out


def _qa_limits_from_env() -> tuple[int, int, int, int]:
    max_hits = int(os.environ.get("CODEKNOWL_QA_SEMANTIC_HITS_K", "8"))
    max_hit_text_chars = int(os.environ.get("CODEKNOWL_QA_HIT_MAX_CHARS", "2000"))
    max_total_text_chars = int(os.environ.get("CODEKNOWL_QA_EVIDENCE_MAX_TEXT_CHARS", "16000"))
    max_evidence_json_chars = int(os.environ.get("CODEKNOWL_QA_EVIDENCE_MAX_JSON_CHARS", "40000"))
    return max_hits, max_hit_text_chars, max_total_text_chars, max_evidence_json_chars


def _evidence_json_with_cap(evidence: dict[str, Any], *, max_chars: int) -> str:
    raw = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)
    if max_chars <= 0 or len(raw) <= max_chars:
        return raw

    shrunk = dict(evidence)
    sem = shrunk.get("semantic_hits")
    if not isinstance(sem, list):
        return raw[: max_chars - 3] + "..." if max_chars > 3 else raw[:max_chars]

    max_hits, max_hit_text_chars, max_total_text_chars, _ = _qa_limits_from_env()
    hits: list[dict[str, Any]] = [h for h in sem if isinstance(h, dict)]
    while hits:
        capped = constrain_semantic_hits(
            hits,
            max_hits=min(len(hits), max_hits),
            max_hit_text_chars=max_hit_text_chars,
            max_total_text_chars=max_total_text_chars,
        )
        shrunk["semantic_hits"] = capped
        raw = json.dumps(shrunk, ensure_ascii=False, indent=2, sort_keys=True)
        if len(raw) <= max_chars:
            return raw
        hits = hits[:-1]

    shrunk.pop("semantic_hits", None)
    raw = json.dumps(shrunk, ensure_ascii=False, indent=2, sort_keys=True)
    if len(raw) <= max_chars:
        return raw
    return raw[: max_chars - 3] + "..." if max_chars > 3 else raw[:max_chars]


def _extract_repo_path_candidate(question: str) -> str | None:
    m = re.search(r"([\w\-./]+\.[a-zA-Z0-9]{1,6})", question)
    if not m:
        return None
    return m.group(1)


def _extract_identifier_candidate(question: str) -> str | None:
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", question)
    if not tokens:
        return None
    return tokens[-1]


def _dedupe_citations(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uniq: dict[tuple[str, int | None, int | None], dict[str, Any]] = {}
    for c in citations:
        key = (c.get("file_path"), c.get("start_line"), c.get("end_line"))
        uniq[key] = c
    return list(uniq.values())


def _maybe_add_semantic_hits(
    semantic_hits: list[dict[str, Any]] | None, evidence: dict[str, Any], citations: list[dict[str, Any]]
) -> None:
    if not semantic_hits:
        return

    evidence["semantic_hits"] = semantic_hits
    for h in semantic_hits:
        if not isinstance(h, dict):
            continue
        citations.append(
            {
                "file_path": h.get("file_path"),
                "start_line": h.get("start_line"),
                "end_line": h.get("end_line"),
                "note": "semantic",
            }
        )


def _maybe_add_file_stub(
    artifacts: dict[str, Any], question: str, evidence: dict[str, Any], citations: list[dict[str, Any]]
) -> None:
    file_path = _extract_repo_path_candidate(question)
    if not file_path:
        return

    if not any(f.get("path") == file_path for f in artifacts.get("files", [])):
        return

    try:
        stub = explain_file_stub(artifacts, file_path)
    except KeyError:
        return

    evidence["file"] = {"path": file_path}
    evidence["file_stub"] = stub
    citations.extend(stub.get("citations", []))


def _maybe_add_where_defined(
    artifacts: dict[str, Any], question: str, evidence: dict[str, Any], citations: list[dict[str, Any]]
) -> None:
    q = question.lower()
    if "where" not in q or ("defined" not in q and "definition" not in q):
        return

    name = _extract_identifier_candidate(question)
    if not name:
        return

    defs = where_is_symbol_defined(artifacts, name)
    evidence["where_defined"] = defs
    for d in defs:
        c = d.get("citation")
        if c:
            citations.append(c)


def _maybe_add_call_sites(
    artifacts: dict[str, Any], question: str, evidence: dict[str, Any], citations: list[dict[str, Any]]
) -> None:
    q = question.lower()
    if "call" not in q:
        return

    name = _extract_identifier_candidate(question)
    if not name:
        return

    callsites = find_callers_best_effort(artifacts, name)
    evidence["call_sites"] = callsites[:50]
    for cs in callsites[:50]:
        c = cs.get("citation")
        if c:
            citations.append(c)


def build_evidence_bundle(
    artifacts: dict[str, Any],
    question: str,
    *,
    semantic_hits: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Build a best-effort evidence bundle from snapshot artifacts.

    This is used both for deterministic Q&A commands and as grounding for LLM-backed answers.
    """

    evidence: dict[str, Any] = {"question": question, "best_effort": True}
    citations: list[dict[str, Any]] = []

    max_hits, max_hit_text_chars, max_total_text_chars, _ = _qa_limits_from_env()
    capped_hits = constrain_semantic_hits(
        semantic_hits,
        max_hits=max_hits,
        max_hit_text_chars=max_hit_text_chars,
        max_total_text_chars=max_total_text_chars,
    )

    _maybe_add_semantic_hits(capped_hits, evidence, citations)
    _maybe_add_file_stub(artifacts, question, evidence, citations)
    _maybe_add_where_defined(artifacts, question, evidence, citations)
    _maybe_add_call_sites(artifacts, question, evidence, citations)

    if "file_stub" not in evidence and "where_defined" not in evidence and "call_sites" not in evidence:
        evidence["hint"] = "No specific evidence matched the question; try including a symbol name or file path."

    return evidence, _dedupe_citations(citations)


def answer_with_llm(
    *,
    llm: OpenAiCompatibleClient,
    artifacts: dict[str, Any],
    question: str,
    semantic_hits: list[dict[str, Any]] | None = None,
) -> AskResult:
    """Generate a short, evidence-grounded answer from an OpenAI-compatible LLM."""
    evidence, citations = build_evidence_bundle(artifacts, question, semantic_hits=semantic_hits)

    *_, max_evidence_json_chars = _qa_limits_from_env()
    evidence_json = _evidence_json_with_cap(evidence, max_chars=max_evidence_json_chars)

    system = (
        "You are CodeKnowl, an on-prem codebase analyst. "
        "You must only use the provided evidence bundle. "
        "If the evidence is insufficient, say so and ask for a file path or symbol name. "
        "Do not invent file names or line numbers."
    )

    user = (
        "Question:\n"
        f"{question}\n\n"
        "Evidence bundle (JSON):\n"
        f"{evidence_json}\n\n"
        "Return a short answer. Where applicable, mention cited file paths and line ranges."
    )

    answer = llm.chat(system=system, user=user)
    return AskResult(answer=answer, citations=citations, evidence=evidence)


def answer_with_llm_synthesis(
    *,
    coding_llm: OpenAiCompatibleClient,
    general_llm: OpenAiCompatibleClient,
    synth_llm: OpenAiCompatibleClient,
    artifacts: dict[str, Any],
    question: str,
    semantic_hits: list[dict[str, Any]] | None = None,
) -> AskResult:
    evidence, citations = build_evidence_bundle(artifacts, question, semantic_hits=semantic_hits)
    *_, max_evidence_json_chars = _qa_limits_from_env()
    evidence_json = _evidence_json_with_cap(evidence, max_chars=max_evidence_json_chars)

    responder_system = (
        "You are CodeKnowl, an on-prem codebase analyst. "
        "You must only use the provided evidence bundle. "
        "If the evidence is insufficient, say so and ask for a file path or symbol name. "
        "Do not invent file names or line numbers. "
        "Return a short answer with citations (file paths + line ranges) where applicable."
    )

    responder_user = (
        "Question:\n"
        f"{question}\n\n"
        "Evidence bundle (JSON):\n"
        f"{evidence_json}\n\n"
        "Return an answer grounded only in the evidence bundle."
    )

    coding_answer = coding_llm.chat(system=responder_system, user=responder_user)
    general_answer = general_llm.chat(system=responder_system, user=responder_user)

    synth_system = (
        "You are CodeKnowl Synthesizer. "
        "You must only use the provided evidence bundle and the two candidate answers. "
        "Produce a single coherent final answer. "
        "If the candidates conflict, resolve the conflict explicitly and prefer claims supported by evidence. "
        "Do not invent file names or line numbers; preserve citations where applicable."
    )

    synth_user = (
        "Question:\n"
        f"{question}\n\n"
        "Evidence bundle (JSON):\n"
        f"{evidence_json}\n\n"
        "Candidate answer (coding model):\n"
        f"{coding_answer}\n\n"
        "Candidate answer (general model):\n"
        f"{general_answer}\n\n"
        "Return the final synthesized answer."
    )

    final_answer = synth_llm.chat(system=synth_system, user=synth_user)
    return AskResult(answer=final_answer, citations=citations, evidence=evidence)
