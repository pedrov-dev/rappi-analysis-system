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
from typing import Any

import pandas as pd
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.data_loader import get_dataframes
from app.report_renderer import _render_html

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


def _as_float(value: Any) -> float | None:
    """Convert inexact pandas values to float safely for mypy and runtime."""
    if value is None:
        return None

    if isinstance(value, complex):
        return None

    # Supports numpy and pandas numeric scalars, plus primitive numbers.
    if pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        try:
            coerced = pd.to_numeric(value, errors="coerce")
            if pd.isna(coerced):
                return None
            return float(coerced)
        except Exception:
            return None


def _safe_pct(new_val: float | int | None, old_val: float | int | None) -> float | None:
    if old_val == 0 or pd.isna(old_val) or pd.isna(new_val):
        return None
    new_val_f = _as_float(new_val)
    old_val_f = _as_float(old_val)
    if new_val_f is None or old_val_f is None or old_val_f == 0:
        return None
    return round((new_val_f - old_val_f) / abs(old_val_f) * 100, 2)


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
        current_value = _as_float(row.get(c0))
        previous_value = _as_float(row.get(c1))
        if current_value is None or previous_value is None:
            continue

        results.append(AnomalyFinding(
            zone=str(row.get("ZONE", "")),
            country=str(row.get("COUNTRY", "")),
            city=str(row.get("CITY", "")),
            metric=str(row.get("METRIC", "")),
            change_pct=pct,
            direction="improvement" if pct > 0 else "deterioration",
            current_value=current_value,
            previous_value=previous_value,
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
        med = _as_float(vals.median())
        std = _as_float(vals.std())
        if med is None or std is None or std == 0:
            continue

        for _, row in grp.iterrows():
            v = row.get(c0)
            if pd.isna(v):
                continue
            v = _as_float(v)
            if v is None:
                continue
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
            if pd.isna(r):
                continue
            r_float = _as_float(r)
            if r_float is None or abs(r_float) < r_threshold:
                continue
            results.append(CorrelationFinding(
                metric_a=str(ma),
                metric_b=str(mb),
                correlation=round(r_float, 3),
                strength="strong" if abs(r_float) >= 0.7 else "moderate",
                direction="positive" if r_float > 0 else "negative",
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
            zone    = idx[-1] if len(idx) > 0 else ""
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
            lead_val = _as_float(low.loc[idx, lead_col])
            if lead_val is None:
                continue
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Supply Gap",
                description="Lead Penetration below 80 % of country median — new-store onboarding can expand supply.",
                supporting_metrics={lead_col: round(lead_val, 4)},
            ))

    # ── B: Cross-vertical growth — low MLTV Adoption ─────────────────────
    mltv_col = _fuzzy_col(r"mltv|multi.?vertical|verticals.adoption")
    if mltv_col:
        median_mltv = pivot[mltv_col].median()
        low = pivot[pivot[mltv_col] < median_mltv * 0.75].dropna(subset=[mltv_col])
        for idx in low.index[:8]:
            country, city, zone = _zone_fields(idx)
            mltv_val = _as_float(low.loc[idx, mltv_col])
            if mltv_val is None:
                continue
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Cross-Vertical Growth",
                description="MLTV Adoption well below median — users buying single-vertical, prime for cross-sell campaigns.",
                supporting_metrics={mltv_col: round(mltv_val, 4)},
            ))

    # ── C: Pro subscription growth — low Pro Adoption ────────────────────
    pro_col = _fuzzy_col(r"pro.adoption|pro adoption")
    if pro_col:
        median_pro = pivot[pro_col].median()
        low = pivot[pivot[pro_col] < median_pro * 0.7].dropna(subset=[pro_col])
        for idx in low.index[:6]:
            country, city, zone = _zone_fields(idx)
            pro_val = _as_float(low.loc[idx, pro_col])
            if pro_val is None:
                continue
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Pro Subscription Growth",
                description="Pro Adoption >30 % below median — targeted Pro acquisition campaign opportunity.",
                supporting_metrics={pro_col: round(pro_val, 4)},
            ))

    # ── D: Quality improvement — low Perfect Orders ───────────────────────
    perf_col = _fuzzy_col(r"perfect.orders|perfect orders")
    if perf_col:
        median_perf = pivot[perf_col].median()
        low = pivot[pivot[perf_col] < median_perf * 0.85].dropna(subset=[perf_col])
        for idx in low.index[:6]:
            country, city, zone = _zone_fields(idx)
            perf_val = _as_float(low.loc[idx, perf_col])
            if perf_val is None:
                continue
            results.append(OpportunityFinding(
                zone=zone, country=country, city=city,
                opportunity_type="Quality Improvement",
                description="Perfect Orders below 85 % of median — investigation of cancellations/delays can lift NPS.",
                supporting_metrics={perf_col: round(perf_val, 4)},
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