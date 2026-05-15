"""
The multi-agent pipeline. Each agent uses one model for one focused task:

  1. Fetcher       Gemini 2.5 Flash (grounded)   live news, multi-source
  2. Classifier    Gemini 2.5 Flash Lite          domain + urgency + severity
  3. Analyst       Gemini 2.5 Flash (grounded)    causes, connect-the-dots, narratives
  4. Impact Mapper Gemini 2.5 Flash Lite          winners/losers + impact matrix
  5. Historian     Groq Llama 4 Scout             history, blind spots, contrarian view
  6. Synthesis     Groq Llama 4 Scout             debate: agreement vs tension
  7. Rewriter      Groq Llama 4 Scout             final plain-English rewrite

The exported orchestrators wire these agents together; the API routes and the
scheduled scripts call the orchestrators. Independent agents run in parallel.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from app import prompts as P
from app.gemini import MODEL_FLASH, MODEL_LITE, extract_json, run_gemini
from app.groq_client import run_groq

SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}


def _clamp_urgency(value) -> int:
    try:
        v = round(float(value))
    except (TypeError, ValueError):
        return 5
    return max(1, min(10, v))


def _normalize_severity(value) -> str:
    v = str(value or "").upper()
    return v if v in SEVERITIES else "MEDIUM"


# --- AGENT 1: News Fetcher — Gemini 2.5 Flash + Google Search grounding ---
def _agent_fetch(query: str | None) -> dict:
    today = date.today().isoformat()
    prompt = (
        P.search_fetch_prompt(query.strip(), today)
        if query and query.strip()
        else P.news_fetch_prompt(today)
    )
    result = run_gemini(P.FETCH_SYSTEM, prompt, model=MODEL_FLASH, grounding=True)
    parsed = extract_json(result["text"])
    raw = [
        {
            "headline": str(s.get("headline", "Untitled")),
            "summary": str(s.get("summary", "")),
            "why": str(s.get("why", "")),
        }
        for s in (parsed.get("stories") or [])[:5]
    ]
    if not raw:
        raise RuntimeError("The fetcher agent returned no stories. Try again.")
    return {"raw": raw, "sources": result["sources"]}


# --- AGENT 2: Classifier — Gemini 2.5 Flash Lite ---
def _agent_classify(raw: list[dict]) -> list[dict]:
    result = run_gemini(P.CLASSIFY_SYSTEM, P.classify_prompt(raw), model=MODEL_LITE)
    parsed = extract_json(result["text"])
    return [
        {
            "domain": str(it.get("domain") or "Society"),
            "urgency": _clamp_urgency(it.get("urgency")),
            "severity": _normalize_severity(it.get("severity")),
        }
        for it in (parsed.get("items") or [])
    ]


# --- AGENT 3: Analyst — Gemini 2.5 Flash + grounding ---
def _agent_analyze(story: dict) -> dict:
    result = run_gemini(
        P.ANALYZE_SYSTEM, P.analyze_prompt(story), model=MODEL_FLASH, grounding=True
    )
    return {"part": extract_json(result["text"]), "sources": result["sources"]}


# --- AGENT 4: Impact Mapper — Gemini 2.5 Flash Lite ---
def _agent_impact(story: dict) -> dict:
    result = run_gemini(P.ANALYZE_SYSTEM, P.impact_prompt(story), model=MODEL_LITE)
    return extract_json(result["text"])


# --- AGENT 5: Historian + contrarian — Groq Llama 4 Scout ---
def _agent_history(story: dict) -> dict:
    return extract_json(run_groq(P.HISTORY_SYSTEM, P.history_prompt(story)))


# --- Multi-Agent View: 5 analyst perspectives — Gemini 2.5 Flash + grounding ---
def _agent_perspectives(story: dict) -> dict:
    result = run_gemini(
        P.PERSPECTIVES_SYSTEM,
        P.perspectives_prompt(story),
        model=MODEL_FLASH,
        grounding=True,
    )
    parsed = extract_json(result["text"])
    return {"agents": parsed.get("agents") or [], "sources": result["sources"]}


# --- AGENT 6: Debate synthesis — Groq Llama 4 Scout ---
def _agent_synthesis(agents: list[dict]) -> dict:
    return extract_json(run_groq(P.SYNTHESIS_SYSTEM, P.synthesis_prompt({"agents": agents})))


# --- AGENT 7: Rewriter — Groq Llama 4 Scout ---
def _agent_rewrite(label: str, data):
    """Rewrite text values into plain English; return the original on failure."""
    import json

    try:
        return extract_json(run_groq(P.REWRITE_SYSTEM, P.rewrite_prompt(label, json.dumps(data))))
    except Exception:
        return data


# ===================== ORCHESTRATORS =====================


def fetch_stories(query: str | None = None) -> dict:
    """Today's important news, or the top angles on a topic when `query` is given."""
    fetched = _agent_fetch(query)
    raw = fetched["raw"]

    with ThreadPoolExecutor(max_workers=2) as pool:
        classes_future = pool.submit(_agent_classify, raw)
        rewrite_future = pool.submit(
            _agent_rewrite, "set of news stories", {"stories": raw}
        )
        classes = classes_future.result()
        rewritten = rewrite_future.result()

    stamp = int(time.time() * 1000)
    rewritten_stories = rewritten.get("stories") or []
    stories: list[dict] = []
    for i, r in enumerate(raw):
        rw = rewritten_stories[i] if i < len(rewritten_stories) else {}
        cls = classes[i] if i < len(classes) else {}
        stories.append(
            {
                "id": f"s{stamp}-{i}",
                "headline": rw.get("headline") or r["headline"],
                "summary": rw.get("summary") or r["summary"],
                "why": rw.get("why") or r["why"],
                "domain": cls.get("domain") or "Society",
                "urgency": cls.get("urgency", 5),
                "severity": cls.get("severity") or "MEDIUM",
            }
        )

    stories.sort(key=lambda s: s["urgency"], reverse=True)
    return {"stories": stories, "sources": fetched["sources"]}


def build_deep_dive(story: dict) -> dict:
    """Full deep-dive analysis of one story. (Analyst ‖ Impact ‖ Historian) → Rewriter."""
    with ThreadPoolExecutor(max_workers=3) as pool:
        analyze_future = pool.submit(_agent_analyze, story)
        impact_future = pool.submit(_agent_impact, story)
        history_future = pool.submit(_agent_history, story)
        analysis = analyze_future.result()
        impact = impact_future.result()
        history = history_future.result()

    part = analysis["part"]
    merged = {
        "rootCauses": part.get("rootCauses"),
        "butterflyChain": part.get("butterflyChain") or [],
        "connectDots": part.get("connectDots"),
        "narratives": part.get("narratives") or [],
        "impacts": impact.get("impacts") or [],
        "winners": impact.get("winners") or [],
        "losers": impact.get("losers") or [],
        "historicalPattern": history.get("historicalPattern"),
        "blindSpots": history.get("blindSpots") or [],
        "predictions": history.get("predictions") or [],
        "contrarianView": history.get("contrarianView"),
    }
    final = _agent_rewrite("deep-dive analysis", merged)
    return {"analysis": final, "sources": analysis["sources"]}


def build_agent_takes(story: dict) -> dict:
    """Five specialist analysts weigh in, then a synthesis agent finds the debate."""
    perspectives = _agent_perspectives(story)
    agents = perspectives["agents"]
    synthesis = _agent_synthesis(agents)
    final = _agent_rewrite(
        "panel of analyst views and their debate",
        {"agents": agents, "synthesis": synthesis},
    )
    return {
        "agents": final.get("agents") or agents,
        "synthesis": final.get("synthesis") or synthesis,
        "sources": perspectives["sources"],
    }


def build_verdict(topic: str, story: dict) -> dict:
    """Deep Signal's own opinion on a topic — analysis, stance, solution, outcomes."""
    v = extract_json(run_groq(P.VERDICT_SYSTEM, P.verdict_prompt(topic, story)))
    outcomes = [
        {"horizon": str(o.get("horizon", "")), "outcome": str(o.get("outcome", ""))}
        for o in (v.get("outcomes") or [])[:4]
        if o.get("outcome")
    ]
    return {
        "analysis": str(v.get("analysis", "")),
        "opinion": str(v.get("opinion", "")),
        "solution": str(v.get("solution", "")),
        "outcomes": outcomes,
    }


def quick_scan() -> dict:
    """Lightweight breaking-news scan for the monitor — one grounded Gemini call."""
    today = date.today().isoformat()
    result = run_gemini(
        P.MONITOR_SYSTEM, P.monitor_prompt(today), model=MODEL_FLASH, grounding=True
    )
    parsed = extract_json(result["text"])
    items = [
        {
            "headline": str(it.get("headline", "")),
            "summary": str(it.get("summary", "")),
            "why": str(it.get("why", "")),
        }
        for it in (parsed.get("items") or [])[:5]
        if it.get("headline")
    ]
    return {"critical": bool(parsed.get("critical")), "items": items}
