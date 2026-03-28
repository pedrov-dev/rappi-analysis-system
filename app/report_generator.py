"""
report_generator.py — Layer 5: Automated Executive Report Generator

Performs five categories of deterministic Pandas analysis:
  1. Anomalies       — WoW changes ≥ 10 %
  2. Concerning Trends — metrics declining 3+ consecutive weeks
  3. Benchmarking    — zones diverging from same-country/type peers
  4. Correlations    — notable pairwise metric relationships
  5. Opportunities   — growth levers (supply gaps, cross-vertical, Pro)

After the analytics pass, a single GPT-4o call enriches the findings
with executive narrative and prioritised recommendations, then renders
a self-contained HTML report.

Usage (from main.py):
    from app.report_generator import generate_report
    html: str = generate_report()
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.data_loader import get_dataframes

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnomalyFinding:
    zone: str
    country: str
    city: str
    metric: str
    change_pct: float          # signed — negative = deterioration
    direction: str             # "deterioration" | "improvement"
    current_value: float
    previous_value: float


@dataclass
class TrendFinding:
    zone: str
    country: str
    city: str
    metric: str
    weeks: int                 # consecutive declining weeks
    delta_pct: float           # total % change over the streak


@dataclass
class BenchmarkFinding:
    zone: str
    country: str
    zone_type: str
    metric: str
    value: float
    peer_median: float
    gap_pct: float             # (value − median) / |median| × 100
    direction: str             # "above" | "below"


@dataclass
class CorrelationFinding:
    metric_a: str
    metric_b: str
    correlation: float
    strength: str              # "strong" | "moderate"
    direction: str             # "positive" | "negative"


@dataclass
class OpportunityFinding:
    zone: str
    country: str
    city: str
    opportunity_type: str
    description: str
    supporting_metrics: dict


@dataclass
class ReportFindings:
    anomalies:      list[AnomalyFinding]         = field(default_factory=list)
    trends:         list[TrendFinding]            = field(default_factory=list)
    benchmarks:     list[BenchmarkFinding]        = field(default_factory=list)
    correlations:   list[CorrelationFinding]      = field(default_factory=list)
    opportunities:  list[OpportunityFinding]      = field(default_factory=list)
    data_summary:   dict                          = field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# Utility helpers
# ─────────────────────────────────────────────────────────────────────────────

def _week_cols(df: pd.DataFrame) -> list[str]:
    """Return LxW columns sorted L0W (newest) → L8W (oldest)."""
    cols = [c for c in df.columns if re.match(r"^L\d+W", c, re.IGNORECASE)]
    return sorted(cols, key=lambda c: int(re.search(r"\d+", c).group()))  # type: ignore[union-attr]


def _safe_pct(new_val: float, old_val: float) -> float | None:
    if old_val == 0 or pd.isna(old_val) or pd.isna(new_val):
        return None
    return round((new_val - old_val) / abs(old_val) * 100, 2)


# ─────────────────────────────────────────────────────────────────────────────
# Analysis module 1 — Anomalies
# ─────────────────────────────────────────────────────────────────────────────

def _find_anomalies(df: pd.DataFrame, threshold: float = 10.0) -> list[AnomalyFinding]:
    """WoW change (L0W vs L1W) with |Δ%| ≥ threshold."""
    wcols = _week_cols(df)
    if len(wcols) < 2:
        return []
    c0, c1 = wcols[0], wcols[1]

    results: list[AnomalyFinding] = []
    for _, row in df.iterrows():
        pct = _safe_pct(row.get(c0), row.get(c1))
        if pct is None or abs(pct) < threshold:
            continue
        results.append(AnomalyFinding(
            zone=str(row.get("ZONE", "")),
            country=str(row.get("COUNTRY", "")),
            city=str(row.get("CITY", "")),
            metric=str(row.get("METRIC", "")),
            change_pct=pct,
            direction="improvement" if pct > 0 else "deterioration",
            current_value=float(row[c0]),
            previous_value=float(row[c1]),
        ))

    results.sort(key=lambda x: abs(x.change_pct), reverse=True)
    return results[:25]


# ─────────────────────────────────────────────────────────────────────────────
# Analysis module 2 — Concerning Trends
# ─────────────────────────────────────────────────────────────────────────────

def _find_trends(df: pd.DataFrame, min_weeks: int = 3) -> list[TrendFinding]:
    """Zones/metrics with ≥ min_weeks consecutive declining values."""
    wcols = _week_cols(df)
    if len(wcols) < min_weeks + 1:
        return []

    results: list[TrendFinding] = []
    for _, row in df.iterrows():
        vals = [row.get(c) for c in wcols]
        vals = [v for v in vals if not pd.isna(v)]
        if len(vals) < min_weeks:
            continue

        # Count consecutive decline: vals[0]=L0W (most recent), vals[1]=L1W, etc.
        # "declining" means current < prior, i.e. vals[i] < vals[i+1]
        streak = 0
        for i in range(len(vals) - 1):
            if vals[i] < vals[i + 1]:
                streak += 1
            else:
                break

        if streak >= min_weeks:
            delta = _safe_pct(vals[0], vals[streak]) or 0.0
            results.append(TrendFinding(
                zone=str(row.get("ZONE", "")),
                country=str(row.get("COUNTRY", "")),
                city=str(row.get("CITY", "")),
                metric=str(row.get("METRIC", "")),
                weeks=streak,
                delta_pct=delta,
            ))

    results.sort(key=lambda x: (x.weeks, abs(x.delta_pct)), reverse=True)
    return results[:20]


# ─────────────────────────────────────────────────────────────────────────────
# Analysis module 3 — Benchmarking
# ─────────────────────────────────────────────────────────────────────────────

def _find_benchmarks(df: pd.DataFrame, z_threshold: float = 1.5) -> list[BenchmarkFinding]:
    """Zones > z_threshold std-devs from their COUNTRY × ZONE_TYPE × METRIC peer group."""
    wcols = _week_cols(df)
    if not wcols:
        return []
    c0 = wcols[0]

    group_cols = [c for c in ["COUNTRY", "ZONE_TYPE"] if c in df.columns]
    if not group_cols:
        return []

    results: list[BenchmarkFinding] = []
    for _, grp in df.groupby(group_cols + ["METRIC"], observed=True):
        vals = grp[c0].dropna()
        if len(vals) < 3:
            continue
        med = float(vals.median())
        std = float(vals.std())
        if std == 0:
            continue

        for _, row in grp.iterrows():
            v = row.get(c0)
            if pd.isna(v):
                continue
            v = float(v)
            if abs((v - med) / std) < z_threshold:
                continue
            gap = ((v - med) / abs(med) * 100) if med != 0 else 0.0
            results.append(BenchmarkFinding(
                zone=str(row.get("ZONE", "")),
                country=str(row.get("COUNTRY", "")),
                zone_type=str(row.get("ZONE_TYPE", "")) if "ZONE_TYPE" in row else "",
                metric=str(row.get("METRIC", "")),
                value=round(v, 5),
                peer_median=round(med, 5),
                gap_pct=round(gap, 2),
                direction="above" if v > med else "below",
            ))

    results.sort(key=lambda x: abs(x.gap_pct), reverse=True)
    return results[:20]


# ─────────────────────────────────────────────────────────────────────────────
# Analysis module 4 — Correlations
# ─────────────────────────────────────────────────────────────────────────────

def _find_correlations(df: pd.DataFrame, r_threshold: float = 0.5) -> list[CorrelationFinding]:
    """Notable pairwise metric correlations across all zones (|r| ≥ r_threshold)."""
    wcols = _week_cols(df)
    if not wcols:
        return []
    c0 = wcols[0]

    index_cols = [c for c in ["COUNTRY", "CITY", "ZONE"] if c in df.columns]
    if not index_cols:
        return []

    try:
        pivot = df.pivot_table(
            index=index_cols,
            columns="METRIC",
            values=c0,
            aggfunc="mean",
        )
    except Exception as exc:
        logger.warning("Correlation pivot failed: %s", exc)
        return []

    # Drop metrics with > 60 % nulls
    pivot = pivot.dropna(thresh=max(1, int(len(pivot) * 0.4)), axis=1)
    if pivot.shape[1] < 2:
        return []

    corr = pivot.corr()
    results: list[CorrelationFinding] = []
    seen: set[frozenset] = set()

    for ma in corr.columns:
        for mb in corr.columns:
            if ma == mb:
                continue
            key: frozenset = frozenset([ma, mb])
            if key in seen:
                continue
            seen.add(key)
            r = corr.loc[ma, mb]
            if pd.isna(r) or abs(r) < r_threshold:
                continue
            results.append(CorrelationFinding(
                metric_a=str(ma),
                metric_b=str(mb),
                correlation=round(float(r), 3),
                strength="strong" if abs(r) >= 0.7 else "moderate",
                direction="positive" if r > 0 else "negative",
            ))

    results.sort(key=lambda x: abs(x.correlation), reverse=True)
    return results[:12]


# ─────────────────────────────────────────────────────────────────────────────
# Analysis module 5 — Opportunities
# ─────────────────────────────────────────────────────────────────────────────

def _find_opportunities(
    metrics_df: pd.DataFrame,
    orders_df: pd.DataFrame | None = None,
) -> list[OpportunityFinding]:
    """Identify zones with concrete growth / improvement potential."""
    wcols = _week_cols(metrics_df)
    if not wcols:
        return []
    c0 = wcols[0]

    index_cols = [c for c in ["COUNTRY", "CITY", "ZONE"] if c in metrics_df.columns]
    if not index_cols:
        return []

    try:
        pivot = metrics_df.pivot_table(
            index=index_cols,
            columns="METRIC",
            values=c0,
            aggfunc="mean",
        )
    except Exception:
        return []

    results: list[OpportunityFinding] = []

    def _fuzzy_col(pattern: str) -> str | None:
        for c in pivot.columns:
            if re.search(pattern, c, re.IGNORECASE):
                return c
        return None

    def _zone_fields(idx: tuple | str) -> tuple[str, str, str]:
        if isinstance(idx, tuple):
            country = idx[0] if len(idx) > 0 else ""
            city    = idx[1] if len(idx) > 1 else ""
            zone    = idx[-1]
        else:
            country, city, zone = "", "", str(idx)
        return str(country), str(city), str(zone)

    # ── A: Supply gap — low Lead Penetration ──────────────────────────────
    lead_col = _fuzzy_col(r"lead.?penetration")
    if lead_col:
        median_lead = pivot[lead_col].median()
        low = pivot[pivot[lead_col] < median_lead * 0.8].dropna(subset=[lead_col])
        for idx in low.index[:8]:
            country, city, zone = _zone_fields(idx)
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Supply Gap",
                description="Lead Penetration below 80 % of country median — new-store onboarding can expand supply.",
                supporting_metrics={lead_col: round(float(low.loc[idx, lead_col]), 4)},
            ))

    # ── B: Cross-vertical growth — low MLTV Adoption ─────────────────────
    mltv_col = _fuzzy_col(r"mltv|multi.?vertical|verticals.adoption")
    if mltv_col:
        median_mltv = pivot[mltv_col].median()
        low = pivot[pivot[mltv_col] < median_mltv * 0.75].dropna(subset=[mltv_col])
        for idx in low.index[:8]:
            country, city, zone = _zone_fields(idx)
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Cross-Vertical Growth",
                description="MLTV Adoption well below median — users buying single-vertical, prime for cross-sell campaigns.",
                supporting_metrics={mltv_col: round(float(low.loc[idx, mltv_col]), 4)},
            ))

    # ── C: Pro subscription growth — low Pro Adoption ────────────────────
    pro_col = _fuzzy_col(r"pro.adoption|pro adoption")
    if pro_col:
        median_pro = pivot[pro_col].median()
        low = pivot[pivot[pro_col] < median_pro * 0.7].dropna(subset=[pro_col])
        for idx in low.index[:6]:
            country, city, zone = _zone_fields(idx)
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Pro Subscription Growth",
                description="Pro Adoption >30 % below median — targeted Pro acquisition campaign opportunity.",
                supporting_metrics={pro_col: round(float(low.loc[idx, pro_col]), 4)},
            ))

    # ── D: Quality improvement — low Perfect Orders ───────────────────────
    perf_col = _fuzzy_col(r"perfect.orders|perfect orders")
    if perf_col:
        median_perf = pivot[perf_col].median()
        low = pivot[pivot[perf_col] < median_perf * 0.85].dropna(subset=[perf_col])
        for idx in low.index[:6]:
            country, city, zone = _zone_fields(idx)
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Quality Improvement",
                description="Perfect Orders below 85 % of median — investigation of cancellations/delays can lift NPS.",
                supporting_metrics={perf_col: round(float(low.loc[idx, perf_col]), 4)},
            ))

    return results[:20]


# ─────────────────────────────────────────────────────────────────────────────
# LLM enrichment — narrative + recommendations
# ─────────────────────────────────────────────────────────────────────────────

_REPORT_SYSTEM = """\
You are a senior operations analyst at Rappi (food delivery).
Given structured analytical findings, produce an executive report narrative.
Return ONLY valid JSON — no markdown fences, no preamble.

JSON schema:
{
  "executive_summary": "2-3 sentence overall assessment",
  "key_findings": ["finding 1", "finding 2", "finding 3", "finding 4", "finding 5"],
  "anomalies_narrative": "2-3 sentences about the anomaly findings",
  "trends_narrative": "2-3 sentences about the concerning trends",
  "benchmarking_narrative": "2-3 sentences about peer divergence",
  "correlations_narrative": "2-3 sentences about metric correlations",
  "opportunities_narrative": "2-3 sentences about growth opportunities",
  "recommendations": [
    {
      "priority": "high|medium|low",
      "finding": "brief description of the issue",
      "action": "specific, actionable recommendation",
      "metric": "primary metric involved"
    }
  ]
}

Rules:
- key_findings: 3-5 most impactful findings, cite specific zones/metrics
- recommendations: 5-8 items, sorted high → low priority
- Be specific; reference zones, countries and metric names from the data
- Keep all text concise and action-oriented
"""


def _llm_enrich(findings: ReportFindings) -> dict:
    payload = json.dumps({
        "data_summary":       findings.data_summary,
        "anomalies":          [asdict(f) for f in findings.anomalies[:10]],
        "concerning_trends":  [asdict(f) for f in findings.trends[:10]],
        "benchmarking":       [asdict(f) for f in findings.benchmarks[:10]],
        "correlations":       [asdict(f) for f in findings.correlations[:8]],
        "opportunities":      [asdict(f) for f in findings.opportunities[:10]],
    }, indent=2)

    llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
    response = llm.invoke([
        SystemMessage(content=_REPORT_SYSTEM),
        HumanMessage(content=f"Generate executive report narrative from:\n{payload}"),
    ])

    raw = str(response.content).strip()
    raw = (raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    try:
        return json.loads(raw)
    except Exception:
        logger.error("LLM report JSON parse failed — using fallback narrative")
        return _fallback_narrative(findings)


def _fallback_narrative(findings: ReportFindings) -> dict:
    return {
        "executive_summary": (
            f"Automated analysis identified {len(findings.anomalies)} anomalies, "
            f"{len(findings.trends)} concerning trends, and {len(findings.opportunities)} "
            "growth opportunities across the operational dataset."
        ),
        "key_findings": [
            f"{len(findings.anomalies)} zones show significant week-over-week changes (≥10%).",
            f"{len(findings.trends)} metric-zone combinations have been declining 3+ consecutive weeks.",
            f"{len(findings.benchmarks)} zones diverge notably from their peer-group benchmark.",
            f"{len(findings.correlations)} notable metric correlations detected.",
            f"{len(findings.opportunities)} actionable growth opportunities identified.",
        ],
        "anomalies_narrative": "",
        "trends_narrative": "",
        "benchmarking_narrative": "",
        "correlations_narrative": "",
        "opportunities_narrative": "",
        "recommendations": [],
    }


# ─────────────────────────────────────────────────────────────────────────────
# HTML renderer
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --bg: #f5f6fa;
  --card: #ffffff;
  --border: #e4e7f0;
  --accent: #ff7a2f;
  --accent2: #ff4f00;
  --text: #18192a;
  --muted: #6b7280;
  --red: #ef4444;
  --green: #10b981;
  --orange: #f59e0b;
  --blue: #3b82f6;
  --purple: #8b5cf6;
  --radius: 10px;
  --shadow: 0 1px 6px rgba(0,0,0,0.07);
}

@media print {
  .no-print { display: none !important; }
  body { background: white; }
  .header { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
}

body {
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
  line-height: 1.6;
}

/* ── Print / Export button ── */
.print-btn {
  position: fixed; top: 16px; right: 16px; z-index: 100;
  background: var(--accent); color: white; border: none;
  padding: 8px 18px; border-radius: 8px; font-size: 13px; font-weight: 600;
  cursor: pointer; box-shadow: 0 2px 10px rgba(255,122,47,0.35);
  transition: background .15s;
}
.print-btn:hover { background: var(--accent2); }

/* ── Header ── */
.header {
  background: linear-gradient(140deg, #0f1120 0%, #1e2038 55%, #2a1a2e 100%);
  color: white; padding: 40px 52px;
}
.header-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 28px; }
.logo-area { display: flex; align-items: center; gap: 14px; }
.logo-icon {
  width: 46px; height: 46px; background: var(--accent);
  border-radius: 13px; display: flex; align-items: center; justify-content: center; font-size: 22px;
}
.logo-label { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; opacity: .7; }
.report-meta { text-align: right; font-size: 11px; opacity: .5; line-height: 1.7; }
.report-title { font-size: 30px; font-weight: 800; letter-spacing: -.6px; margin-bottom: 6px; }
.report-subtitle { font-size: 14px; opacity: .6; }
.header-stats {
  display: flex; gap: 36px; margin-top: 32px; padding-top: 24px;
  border-top: 1px solid rgba(255,255,255,.1); flex-wrap: wrap;
}
.stat { display: flex; flex-direction: column; gap: 3px; }
.stat-val { font-size: 26px; font-weight: 800; color: var(--accent); line-height: 1; }
.stat-lbl { font-size: 10px; letter-spacing: 1px; text-transform: uppercase; opacity: .45; margin-top: 2px; }

/* ── Layout ── */
.container { max-width: 1120px; margin: 0 auto; padding: 36px 24px; }

/* ── Executive summary ── */
.exec-card {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 28px 32px;
  margin-bottom: 28px; box-shadow: var(--shadow);
}
.section-label {
  font-size: 10px; font-weight: 700; letter-spacing: 1.8px;
  text-transform: uppercase; color: var(--muted); margin-bottom: 10px;
}
.exec-text { font-size: 15px; line-height: 1.75; margin-bottom: 20px; }
.key-findings { list-style: none; display: flex; flex-direction: column; gap: 9px; }
.key-findings li {
  display: flex; align-items: flex-start; gap: 10px;
  font-size: 13px; line-height: 1.55;
}
.key-findings li::before {
  content: "◆"; color: var(--accent); flex-shrink: 0; margin-top: 3px; font-size: 9px;
}

/* ── Section card ── */
.section {
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); margin-bottom: 24px;
  overflow: hidden; box-shadow: var(--shadow);
}
.section-hdr {
  padding: 16px 24px; border-bottom: 1px solid var(--border);
  display: flex; align-items: center; gap: 12px;
  background: linear-gradient(to right, var(--card), var(--bg));
}
.sec-icon {
  width: 38px; height: 38px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center; font-size: 18px; flex-shrink: 0;
}
.ic-red    { background: rgba(239,68,68,.1); }
.ic-orange { background: rgba(245,158,11,.1); }
.ic-blue   { background: rgba(59,130,246,.1); }
.ic-purple { background: rgba(139,92,246,.1); }
.ic-green  { background: rgba(16,185,129,.1); }
.sec-title { font-size: 15px; font-weight: 600; }
.sec-count {
  margin-left: auto; font-size: 11px; color: var(--muted);
  background: var(--bg); padding: 3px 11px; border-radius: 20px; border: 1px solid var(--border);
}
.sec-narrative {
  padding: 13px 24px; font-size: 13px; color: var(--muted);
  border-bottom: 1px solid var(--border); font-style: italic; line-height: 1.6;
  background: rgba(245,246,250,.6);
}

/* ── Tables ── */
table { width: 100%; border-collapse: collapse; }
thead tr { background: var(--bg); border-bottom: 2px solid var(--border); }
th {
  padding: 10px 16px; text-align: left;
  font-size: 10px; font-weight: 700; letter-spacing: .7px;
  text-transform: uppercase; color: var(--muted);
}
td {
  padding: 9px 16px; font-size: 13px;
  border-bottom: 1px solid var(--border); vertical-align: middle;
}
tr:last-child td { border-bottom: none; }
tr:hover { background: rgba(255,122,47,.025); }
td.mono, .mono { font-family: 'Cascadia Code', 'SF Mono', Consolas, monospace; font-size: 12px; }
td.center { text-align: center; }
td.small { font-size: 11px; }

.pct { font-weight: 700; font-family: 'SF Mono', monospace; font-size: 12px; }
.pct.red   { color: var(--red); }
.pct.green { color: var(--green); }

/* ── Badges ── */
.badge {
  font-size: 10px; font-weight: 700; letter-spacing: .5px;
  text-transform: uppercase; padding: 2px 8px;
  border-radius: 4px; display: inline-block;
}
.badge.red    { background: rgba(239,68,68,.12);  color: var(--red); }
.badge.green  { background: rgba(16,185,129,.12); color: var(--green); }
.badge.orange { background: rgba(245,158,11,.12); color: var(--orange); }
.badge.blue   { background: rgba(59,130,246,.12); color: var(--blue); }
.badge.strong   { background: rgba(59,130,246,.12);  color: var(--blue); }
.badge.moderate { background: rgba(139,92,246,.12); color: var(--purple); }

.zone-tag {
  font-size: 10px; font-weight: 700;
  background: rgba(255,122,47,.1); color: var(--accent2);
  padding: 1px 6px; border-radius: 3px; margin-right: 4px;
}

/* ── Correlation grid ── */
.corr-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px; padding: 20px;
}
.corr-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px;
}
.corr-metrics {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 10px; flex-wrap: wrap;
}
.metric-pill {
  font-size: 11px; font-weight: 500;
  background: var(--card); border: 1px solid var(--border);
  padding: 3px 10px; border-radius: 20px;
}
.corr-arrow { color: var(--muted); font-size: 16px; }
.corr-bar-wrap {
  height: 6px; background: var(--border);
  border-radius: 3px; overflow: hidden; margin-bottom: 8px;
}
.corr-bar { height: 100%; border-radius: 3px; }
.corr-bar.pos { background: var(--green); }
.corr-bar.neg { background: var(--red); }
.corr-meta { display: flex; justify-content: space-between; align-items: center; }
.corr-r { font-family: 'SF Mono', monospace; font-size: 12px; font-weight: 700; }

/* ── Opportunity grid ── */
.opp-grid {
  display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 14px; padding: 20px;
}
.opp-card {
  background: var(--bg); border: 1px solid var(--border);
  border-radius: 8px; padding: 14px; border-left: 3px solid var(--green);
}
.opp-header { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
.opp-type {
  font-size: 10px; font-weight: 700; color: var(--green);
  text-transform: uppercase; letter-spacing: .6px;
}
.opp-zone { font-size: 13px; font-weight: 600; margin-bottom: 5px; }
.opp-desc { font-size: 12px; color: var(--muted); line-height: 1.5; margin-bottom: 8px; }
.opp-metrics { display: flex; gap: 6px; flex-wrap: wrap; }
.metric-tag {
  font-size: 10px; background: rgba(16,185,129,.1); color: var(--green);
  padding: 2px 8px; border-radius: 4px; font-family: monospace;
}

/* ── Chart ── */
.chart-wrap { padding: 20px; height: 280px; position: relative; }

/* ── Recommendations block ── */
.rec-section {
  background: linear-gradient(140deg, #0f1120, #1e2038);
  color: white; border-radius: var(--radius);
  overflow: hidden; margin-bottom: 28px; box-shadow: var(--shadow);
}
.rec-hdr { padding: 20px 28px; border-bottom: 1px solid rgba(255,255,255,.08); font-size: 15px; font-weight: 700; }
.rec-section table { color: white; }
.rec-section th { color: rgba(255,255,255,.4); }
.rec-section td { border-color: rgba(255,255,255,.07); }
.rec-section tr:hover { background: rgba(255,255,255,.03); }

/* ── Empty state ── */
.empty { padding: 32px; text-align: center; color: var(--muted); font-size: 13px; }

/* ── Footer ── */
.footer {
  text-align: center; padding: 24px;
  font-size: 11px; color: var(--muted);
  border-top: 1px solid var(--border); margin-top: 16px;
}

@media (max-width: 700px) {
  .header { padding: 24px 20px; }
  .container { padding: 16px; }
  .corr-grid, .opp-grid { grid-template-columns: 1fr; }
  .header-stats { gap: 18px; }
}
"""


def _esc(s: object) -> str:
    return (str(s)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


def _render_html(findings: ReportFindings, narrative: dict) -> str:  # noqa: C901
    ts  = datetime.utcnow().strftime("%B %d, %Y · %H:%M UTC")
    ds  = findings.data_summary

    # ── Anomaly rows ────────────────────────────────────────────────────────
    anomaly_rows = ""
    for a in findings.anomalies[:15]:
        arrow = "▼" if a.direction == "deterioration" else "▲"
        cls   = "red" if a.direction == "deterioration" else "green"
        anomaly_rows += (
            f"<tr><td><span class='zone-tag'>{_esc(a.country)}</span>{_esc(a.zone)}</td>"
            f"<td>{_esc(a.city)}</td>"
            f"<td class='mono'>{_esc(a.metric)}</td>"
            f"<td class='mono'>{a.previous_value:.4f}</td>"
            f"<td class='mono'>{a.current_value:.4f}</td>"
            f"<td class='pct {cls}'>{arrow} {abs(a.change_pct):.1f}%</td></tr>"
        )

    # ── Trend rows ──────────────────────────────────────────────────────────
    trend_rows = ""
    for t in findings.trends[:15]:
        trend_rows += (
            f"<tr><td><span class='zone-tag'>{_esc(t.country)}</span>{_esc(t.zone)}</td>"
            f"<td>{_esc(t.city)}</td>"
            f"<td class='mono'>{_esc(t.metric)}</td>"
            f"<td class='center'>{t.weeks} wks</td>"
            f"<td class='pct red'>▼ {abs(t.delta_pct):.1f}%</td></tr>"
        )

    # ── Benchmark rows ──────────────────────────────────────────────────────
    bench_rows = ""
    for b in findings.benchmarks[:15]:
        arrow = "▲" if b.direction == "above" else "▼"
        cls   = "green" if b.direction == "above" else "red"
        bench_rows += (
            f"<tr><td><span class='zone-tag'>{_esc(b.country)}</span>{_esc(b.zone)}</td>"
            f"<td>{_esc(b.zone_type)}</td>"
            f"<td class='mono'>{_esc(b.metric)}</td>"
            f"<td class='mono'>{b.value:.4f}</td>"
            f"<td class='mono'>{b.peer_median:.4f}</td>"
            f"<td class='pct {cls}'>{arrow} {abs(b.gap_pct):.1f}%</td></tr>"
        )

    # ── Correlation cards ───────────────────────────────────────────────────
    corr_cards = ""
    for c in findings.correlations[:9]:
        bar_w   = int(abs(c.correlation) * 100)
        bar_cls = "pos" if c.direction == "positive" else "neg"
        corr_cards += (
            f"<div class='corr-card'>"
            f"<div class='corr-metrics'>"
            f"<span class='metric-pill'>{_esc(c.metric_a)}</span>"
            f"<span class='corr-arrow'>{'↔' if c.direction == 'positive' else '↕'}</span>"
            f"<span class='metric-pill'>{_esc(c.metric_b)}</span>"
            f"</div>"
            f"<div class='corr-bar-wrap'><div class='corr-bar {bar_cls}' style='width:{bar_w}%'></div></div>"
            f"<div class='corr-meta'>"
            f"<span class='badge {c.strength}'>{c.strength.capitalize()} {c.direction}</span>"
            f"<span class='corr-r'>r = {c.correlation:+.3f}</span>"
            f"</div></div>"
        )

    # ── Opportunity cards ───────────────────────────────────────────────────
    opp_cards = ""
    for o in findings.opportunities[:12]:
        metrics_html = " ".join(
            f"<span class='metric-tag'>{_esc(k)}: {v}</span>"
            for k, v in o.supporting_metrics.items()
        )
        opp_cards += (
            f"<div class='opp-card'>"
            f"<div class='opp-header'>"
            f"<span class='opp-type'>{_esc(o.opportunity_type)}</span>"
            f"<span class='zone-tag'>{_esc(o.country)}</span>"
            f"</div>"
            f"<div class='opp-zone'>{_esc(o.zone)} · {_esc(o.city)}</div>"
            f"<div class='opp-desc'>{_esc(o.description)}</div>"
            f"{'<div class=\"opp-metrics\">' + metrics_html + '</div>' if metrics_html else ''}"
            f"</div>"
        )

    # ── Key findings list ───────────────────────────────────────────────────
    kf_html = "".join(
        f"<li>{_esc(f)}</li>" for f in narrative.get("key_findings", [])
    )

    # ── Recommendation rows ─────────────────────────────────────────────────
    rec_rows = ""
    for r in narrative.get("recommendations", []):
        prio     = r.get("priority", "medium")
        prio_cls = {"high": "red", "medium": "orange", "low": "green"}.get(prio, "orange")
        rec_rows += (
            f"<tr>"
            f"<td><span class='badge {prio_cls}'>{prio.upper()}</span></td>"
            f"<td>{_esc(r.get('finding', ''))}</td>"
            f"<td>{_esc(r.get('action', ''))}</td>"
            f"<td class='mono small'>{_esc(r.get('metric', '—'))}</td>"
            f"</tr>"
        )

    # ── Chart.js data ───────────────────────────────────────────────────────
    chart_labels = json.dumps([f"{a.zone[:18]}" for a in findings.anomalies[:12]])
    chart_values = json.dumps([round(a.change_pct, 2) for a in findings.anomalies[:12]])
    chart_colors = json.dumps([
        "rgba(239,68,68,0.75)" if a.direction == "deterioration" else "rgba(16,185,129,0.75)"
        for a in findings.anomalies[:12]
    ])

    # ── Conditional section helpers ─────────────────────────────────────────
    def _narrative_div(key: str) -> str:
        txt = narrative.get(key, "")
        return f"<div class='sec-narrative'>{_esc(txt)}</div>" if txt else ""

    def _table_or_empty(rows: str, heads: str) -> str:
        if not rows:
            return "<div class='empty'>No findings detected for this category.</div>"
        return f"<table><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table>"

    th = lambda s: f"<th>{s}</th>"  # noqa: E731

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Rappi Executive Report · {ts}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>{_CSS}</style>
</head>
<body>

<button class="print-btn no-print" onclick="window.print()">🖨 Export PDF</button>

<!-- ── Header ──────────────────────────────────────────────────────────── -->
<div class="header">
  <div class="header-top">
    <div class="logo-area">
      <div class="logo-icon">📦</div>
      <div><div class="logo-label">Rappi Operations</div></div>
    </div>
    <div class="report-meta">Generated: {ts}<br/>Rappi Analytics Platform</div>
  </div>
  <div class="report-title">Executive Operations Report</div>
  <div class="report-subtitle">Automated insight analysis across zones, metrics &amp; weekly periods</div>
  <div class="header-stats">
    <div class="stat"><span class="stat-val">{len(findings.anomalies)}</span><span class="stat-lbl">Anomalies</span></div>
    <div class="stat"><span class="stat-val">{len(findings.trends)}</span><span class="stat-lbl">Declining Trends</span></div>
    <div class="stat"><span class="stat-val">{len(findings.benchmarks)}</span><span class="stat-lbl">Benchmark Gaps</span></div>
    <div class="stat"><span class="stat-val">{len(findings.correlations)}</span><span class="stat-lbl">Correlations</span></div>
    <div class="stat"><span class="stat-val">{len(findings.opportunities)}</span><span class="stat-lbl">Opportunities</span></div>
    <div class="stat"><span class="stat-val">{ds.get("total_zones", "—")}</span><span class="stat-lbl">Zones</span></div>
    <div class="stat"><span class="stat-val">{ds.get("total_metrics", "—")}</span><span class="stat-lbl">Metrics</span></div>
  </div>
</div>

<div class="container">

  <!-- Executive Summary -->
  <div class="exec-card">
    <div class="section-label">Executive Summary</div>
    <div class="exec-text">{_esc(narrative.get("executive_summary", ""))}</div>
    <div class="section-label">Key Findings</div>
    <ul class="key-findings">{kf_html}</ul>
  </div>

  <!-- 1 · Anomalies -->
  <div class="section">
    <div class="section-hdr">
      <div class="sec-icon ic-red">⚡</div>
      <div><div class="sec-title">Week-over-Week Anomalies</div></div>
      <span class="sec-count">{len(findings.anomalies)} findings</span>
    </div>
    {_narrative_div("anomalies_narrative")}
    {"<div class='chart-wrap'><canvas id='anomalyChart'></canvas></div>" if findings.anomalies else ""}
    {_table_or_empty(anomaly_rows,
        th("Zone") + th("City") + th("Metric") + th("Prev.") + th("Current") + th("Change"))}
  </div>

  <!-- 2 · Trends -->
  <div class="section">
    <div class="section-hdr">
      <div class="sec-icon ic-orange">📉</div>
      <div><div class="sec-title">Concerning Trends (3+ Consecutive Weeks)</div></div>
      <span class="sec-count">{len(findings.trends)} findings</span>
    </div>
    {_narrative_div("trends_narrative")}
    {_table_or_empty(trend_rows,
        th("Zone") + th("City") + th("Metric") + th("Streak") + th("Total Δ"))}
  </div>

  <!-- 3 · Benchmarking -->
  <div class="section">
    <div class="section-hdr">
      <div class="sec-icon ic-blue">🎯</div>
      <div><div class="sec-title">Peer Benchmarking — Zone Divergence</div></div>
      <span class="sec-count">{len(findings.benchmarks)} findings</span>
    </div>
    {_narrative_div("benchmarking_narrative")}
    {_table_or_empty(bench_rows,
        th("Zone") + th("Type") + th("Metric") + th("Value") + th("Peer Median") + th("Gap"))}
  </div>

  <!-- 4 · Correlations -->
  <div class="section">
    <div class="section-hdr">
      <div class="sec-icon ic-purple">🔗</div>
      <div><div class="sec-title">Metric Correlations</div></div>
      <span class="sec-count">{len(findings.correlations)} findings</span>
    </div>
    {_narrative_div("correlations_narrative")}
    {"<div class='corr-grid'>" + corr_cards + "</div>" if corr_cards else "<div class='empty'>No notable correlations detected.</div>"}
  </div>

  <!-- 5 · Opportunities -->
  <div class="section">
    <div class="section-hdr">
      <div class="sec-icon ic-green">🌱</div>
      <div><div class="sec-title">Growth Opportunities</div></div>
      <span class="sec-count">{len(findings.opportunities)} findings</span>
    </div>
    {_narrative_div("opportunities_narrative")}
    {"<div class='opp-grid'>" + opp_cards + "</div>" if opp_cards else "<div class='empty'>No specific opportunities identified.</div>"}
  </div>

  <!-- Prioritised Action Plan -->
  <div class="rec-section">
    <div class="rec-hdr">🎬 Prioritised Action Plan</div>
    {"<table><thead><tr>" + th("Priority") + th("Finding") + th("Recommended Action") + th("Metric") + "</tr></thead><tbody>" + rec_rows + "</tbody></table>"
      if rec_rows else "<div class='empty' style='color:rgba(255,255,255,.4)'>No recommendations generated.</div>"}
  </div>

</div>

<div class="footer">
  Rappi Analytics Platform &nbsp;·&nbsp; Auto-generated Executive Report &nbsp;·&nbsp; {ts}
  &nbsp;·&nbsp; <em>For internal use only</em>
</div>

<script>
(function() {{
  var ctx = document.getElementById('anomalyChart');
  if (!ctx) return;
  new Chart(ctx, {{
    type: 'bar',
    data: {{
      labels: {chart_labels},
      datasets: [{{
        label: 'WoW Change %',
        data: {chart_values},
        backgroundColor: {chart_colors},
        borderRadius: 4,
      }}]
    }},
    options: {{
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {{
        legend: {{ display: false }},
        tooltip: {{ callbacks: {{ label: function(c) {{ return ' ' + (c.raw > 0 ? '+' : '') + c.raw.toFixed(1) + '%'; }} }} }}
      }},
      scales: {{
        x: {{
          grid: {{ color: 'rgba(0,0,0,0.05)' }},
          ticks: {{ callback: function(v) {{ return v + '%'; }}, font: {{ size: 11 }} }}
        }},
        y: {{ ticks: {{ font: {{ size: 11 }} }} }}
      }}
    }}
  }});
}})();
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

def generate_report() -> str:
    """
    Run all five analytical modules, enrich with GPT-4o narrative,
    and return a self-contained HTML report string.

    Raises ValueError if the METRICS DataFrame is not loaded.
    """
    dfs        = get_dataframes()
    metrics_df = dfs.get("METRICS")
    orders_df  = dfs.get("ORDERS")

    if metrics_df is None:
        raise ValueError("METRICS DataFrame not available — ensure data_loader was initialised.")

    data_summary = {
        "total_zones":    int(metrics_df["ZONE"].nunique())   if "ZONE"   in metrics_df.columns else 0,
        "total_metrics":  int(metrics_df["METRIC"].nunique()) if "METRIC" in metrics_df.columns else 0,
        "countries":      list(metrics_df["COUNTRY"].unique()) if "COUNTRY" in metrics_df.columns else [],
        "weeks_available": len(_week_cols(metrics_df)),
    }

    logger.info(
        "report_generator | start | zones=%d metrics=%d countries=%s",
        data_summary["total_zones"],
        data_summary["total_metrics"],
        data_summary["countries"],
    )

    findings = ReportFindings(
        anomalies     = _find_anomalies(metrics_df),
        trends        = _find_trends(metrics_df),
        benchmarks    = _find_benchmarks(metrics_df),
        correlations  = _find_correlations(metrics_df),
        opportunities = _find_opportunities(metrics_df, orders_df),
        data_summary  = data_summary,
    )

    logger.info(
        "report_generator | analysis done | anomalies=%d trends=%d benchmarks=%d corr=%d opp=%d",
        len(findings.anomalies), len(findings.trends),
        len(findings.benchmarks), len(findings.correlations),
        len(findings.opportunities),
    )

    try:
        narrative = _llm_enrich(findings)
    except Exception as exc:
        logger.error("report_generator | LLM enrichment failed: %s", exc)
        narrative = _fallback_narrative(findings)

    return _render_html(findings, narrative)