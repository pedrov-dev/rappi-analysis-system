"""HTML report rendering helpers for Rappi analysis system."""
from __future__ import annotations

import json
from datetime import datetime

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


def _render_html(findings, narrative: dict) -> str:  # noqa: C901
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
