"""
Signal Engine — the research layer of NewsAgent AI.

Most news apps report *what* happened. The Signal Engine quantifies *patterns in
the news stream itself* by combining the historical warehouse (Neon Postgres)
with today's live stories:

  • Signal Score   — a transparent 0–100 blend of severity, urgency and volume
                     per desk (domain).
  • Momentum       — is a desk escalating or cooling versus its OWN historical
                     baseline? (z-score of recent vs prior intensity).
  • Anomalies      — desks whose latest activity is a statistical outlier.
  • Co-occurrence  — which desks tend to spike on the same days (the soft
                     "what moves with what" — connect-the-dots).

Every number is computed with plain statistics — nothing is hallucinated, and
the whole thing is reproducible. The signals sharpen as the warehouse
accumulates more days of history; with little history the engine says so
instead of inventing confidence.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

from app.analytics import _connect

# Blend weights for a single story's "intensity" (0–1).
_W_SEVERITY = 0.6
_W_URGENCY = 0.4
# Blend weights for a desk's Signal Score.
_W_INTENSITY = 0.75
_W_VOLUME = 0.25
_RECENT_DAYS = 3  # the "live/recent" window; older rows form the baseline


def _story_intensity(severity_rank: int, urgency) -> float:
    sev = (severity_rank or 0) / 4.0
    urg = (float(urgency) / 10.0) if urgency is not None else sev  # fall back to severity
    return max(0.0, min(1.0, _W_SEVERITY * sev + _W_URGENCY * urg))


def _fetch():
    con = _connect()
    if con is None:
        return []
    with con:
        rows = con.execute(
            "SELECT date, domain, severity_rank, urgency "
            "FROM stories WHERE date IS NOT NULL ORDER BY date"
        ).fetchall()
    con.close()
    return rows


def signal_report() -> dict:
    rows = _fetch()
    if not rows:
        return {"available": False, "reason": "warehouse empty — run scripts/etl.py"}

    dates = sorted({r[0] for r in rows})
    n_days = len(dates)
    latest = dates[-1]
    recent_cut = dates[max(0, n_days - _RECENT_DAYS)]

    # --- aggregate per domain, and per (domain, date) for time-series work ---
    per_domain = defaultdict(list)          # domain -> [intensity, ...]
    by_domain_date = defaultdict(lambda: defaultdict(list))  # domain -> date -> [intensity]
    day_domains = defaultdict(set)          # date -> {domains present}
    total = 0
    for date, domain, sev, urg in rows:
        i = _story_intensity(sev, urg)
        per_domain[domain].append(i)
        by_domain_date[domain][date].append(i)
        day_domains[date].add(domain)
        total += 1

    # --- Signal Score per desk ---
    desks = []
    for domain, ints in per_domain.items():
        intensity = statistics.fmean(ints)
        volume_share = len(ints) / total
        score = round(100 * (_W_INTENSITY * intensity + _W_VOLUME * volume_share), 1)
        desks.append({
            "domain": domain,
            "signal_score": score,
            "stories": len(ints),
            "intensity": round(intensity, 3),
            "volume_share": round(volume_share, 3),
        })
    desks.sort(key=lambda d: d["signal_score"], reverse=True)

    # --- Momentum: recent window vs historical baseline (per desk) ---
    momentum = []
    for domain, by_date in by_domain_date.items():
        recent = [i for d, ii in by_date.items() if d >= recent_cut for i in ii]
        baseline = [i for d, ii in by_date.items() if d < recent_cut for i in ii]
        if len(baseline) >= 3 and recent:
            b_mean, r_mean = statistics.fmean(baseline), statistics.fmean(recent)
            # Floor the std so near-constant baselines can't blow the z-score up,
            # and clamp to a sane range.
            b_std = max(statistics.pstdev(baseline), 0.1)
            z = max(-8.0, min(8.0, (r_mean - b_mean) / b_std))
            label = "escalating" if z > 0.5 else "cooling" if z < -0.5 else "steady"
            momentum.append({
                "domain": domain, "z_score": round(z, 2), "trend": label,
                "recent_intensity": round(r_mean, 3), "baseline_intensity": round(b_mean, 3),
            })
    momentum.sort(key=lambda m: m["z_score"], reverse=True)

    # --- Anomaly flags: latest-day intensity vs a desk's own daily history ---
    anomalies = []
    for domain, by_date in by_domain_date.items():
        daily = [statistics.fmean(by_date[d]) for d in sorted(by_date) if by_date[d]]
        if len(daily) >= 4:
            hist, today = daily[:-1], daily[-1]
            mu, sd = statistics.fmean(hist), max(statistics.pstdev(hist), 0.1)
            z = max(-8.0, min(8.0, (today - mu) / sd))
            if abs(z) >= 2:
                anomalies.append({"domain": domain, "z_score": round(z, 2),
                                  "direction": "spike" if z > 0 else "drop"})

    # --- Cross-desk co-occurrence: desks that light up on the same days ---
    pair_days = defaultdict(int)
    for doms in day_domains.values():
        ds = sorted(doms)
        for a in range(len(ds)):
            for b in range(a + 1, len(ds)):
                pair_days[(ds[a], ds[b])] += 1
    co_occurrence = sorted(
        ({"pair": [a, b], "shared_days": n} for (a, b), n in pair_days.items() if n >= 1),
        key=lambda x: x["shared_days"], reverse=True,
    )[:8]

    # --- honest data-sufficiency note ---
    if n_days < 3:
        maturity = "building — momentum/anomaly need a few days of history; scores are current-snapshot only"
    elif n_days < 10:
        maturity = "warming up — trends are directional; anomaly detection improves past ~2 weeks"
    else:
        maturity = "mature — momentum, anomalies and co-occurrence are statistically meaningful"

    return {
        "available": True,
        "as_of": str(latest),
        "history_days": n_days,
        "total_stories": total,
        "maturity": maturity,
        "desks": desks,
        "momentum": momentum,
        "anomalies": anomalies,
        "co_occurrence": co_occurrence,
        "method": {
            "story_intensity": "0.6·(severity/4) + 0.4·(urgency/10)",
            "signal_score": "100·(0.75·mean_intensity + 0.25·volume_share)",
            "momentum": "z-score of recent-window vs baseline mean intensity",
        },
    }


def research_note(report: dict) -> str:
    """LLM 'analyst' layer: interpret the COMPUTED metrics in plain English.

    The model only ever sees the numbers the engine produced — it interprets,
    it does not invent facts or predict specific events.
    """
    if not report.get("available"):
        return "Not enough data yet to write a research note."

    from app.gemini import extract_json
    from app.groq_client import run_groq

    desks = ", ".join(f"{d['domain']}={d['signal_score']}" for d in report["desks"][:6])
    mom = "; ".join(
        f"{m['domain']} {m['trend']} (z={m['z_score']})" for m in report["momentum"][:5]
    ) or "no momentum yet — history still building"
    co = ", ".join(f"{c['pair'][0]}+{c['pair'][1]}" for c in report["co_occurrence"][:4])

    system = (
        "You are a quantitative news analyst. You are given ALREADY-COMPUTED "
        "signal metrics for news desks. Interpret ONLY the numbers given: never "
        "invent specific events, never predict exact outcomes, and when history "
        "is thin say the read is preliminary. Respond as JSON of the form "
        '{"note": "<a measured 3-4 sentence analyst note>"}.'
    )
    prompt = (
        f"Signal scores (0-100): {desks}. Momentum: {mom}. "
        f"Co-occurring desks: {co or 'n/a'}. "
        f"History: {report['history_days']} day(s), {report['total_stories']} stories "
        f"({report['maturity']}). Return JSON with the single key 'note'."
    )
    parsed = extract_json(run_groq(system, prompt))
    if isinstance(parsed, dict) and parsed.get("note"):
        return str(parsed["note"]).strip()
    return "Signal read is preliminary while history accumulates."
