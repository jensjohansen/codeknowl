from __future__ import annotations

import json
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


def build_evidence_bundle(artifacts: dict[str, Any], question: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    q = question.lower()

    evidence: dict[str, Any] = {"question": question, "best_effort": True}
    citations: list[dict[str, Any]] = []

    file_path = _extract_repo_path_candidate(question)
    if file_path and any(f.get("path") == file_path for f in artifacts.get("files", [])):
        try:
            stub = explain_file_stub(artifacts, file_path)
            evidence["file"] = {"path": file_path}
            evidence["file_stub"] = stub
            citations.extend(stub.get("citations", []))
        except KeyError:
            pass

    if "where" in q and ("defined" in q or "definition" in q):
        name = _extract_identifier_candidate(question)
        if name:
            defs = where_is_symbol_defined(artifacts, name)
            evidence["where_defined"] = defs
            for d in defs:
                c = d.get("citation")
                if c:
                    citations.append(c)

    if "call" in q:
        name = _extract_identifier_candidate(question)
        if name:
            callsites = find_callers_best_effort(artifacts, name)
            evidence["call_sites"] = callsites[:50]
            for cs in callsites[:50]:
                c = cs.get("citation")
                if c:
                    citations.append(c)

    if "file_stub" not in evidence and "where_defined" not in evidence and "call_sites" not in evidence:
        evidence["hint"] = "No specific evidence matched the question; try including a symbol name or file path."

    uniq: dict[tuple[str, int | None, int | None], dict[str, Any]] = {}
    for c in citations:
        key = (c.get("file_path"), c.get("start_line"), c.get("end_line"))
        uniq[key] = c

    return evidence, list(uniq.values())


def answer_with_llm(
    *,
    llm: OpenAiCompatibleClient,
    artifacts: dict[str, Any],
    question: str,
) -> AskResult:
    evidence, citations = build_evidence_bundle(artifacts, question)

    evidence_json = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True)

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
