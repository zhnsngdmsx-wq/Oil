"""
Global Oil Production Monitor
Fetches and displays real-time oil production data by country using the EIA API.
Falls back to latest known data if the API is unavailable.
Generates a self-contained HTML report and opens it in the default browser.
"""

import urllib.request
import json
import datetime
import os
import webbrowser
import tempfile

# ── Fallback data (barrels per day, approximate 2024 figures) ──────────────────

FALLBACK_DATA = [
    {"country": "United States",    "region": "North America", "bpd": 20_000_000},
    {"country": "Saudi Arabia",     "region": "Middle East",   "bpd": 11_000_000},
    {"country": "Russia",           "region": "Europe/Asia",   "bpd": 10_500_000},
    {"country": "Canada",           "region": "North America", "bpd":  5_576_000},
    {"country": "Iraq",             "region": "Middle East",   "bpd":  4_520_000},
    {"country": "China",            "region": "Asia",          "bpd":  4_111_000},
    {"country": "UAE",              "region": "Middle East",   "bpd":  3_000_000},
    {"country": "Brazil",           "region": "South America", "bpd":  2_900_000},
    {"country": "Kuwait",           "region": "Middle East",   "bpd":  2_600_000},
    {"country": "Iran",             "region": "Middle East",   "bpd":  2_500_000},
    # Africa
    {"country": "Nigeria",          "region": "Africa",        "bpd":  1_700_000},
    {"country": "Angola",           "region": "Africa",        "bpd":  1_100_000},
    {"country": "Algeria",          "region": "Africa",        "bpd":    900_000},
    {"country": "Libya",            "region": "Africa",        "bpd":    700_000},
    {"country": "Egypt",            "region": "Africa",        "bpd":    600_000},
    {"country": "South Sudan",      "region": "Africa",        "bpd":    150_000},
    {"country": "Gabon",            "region": "Africa",        "bpd":    200_000},
    {"country": "Congo",            "region": "Africa",        "bpd":    250_000},
    {"country": "Equatorial Guinea","region": "Africa",        "bpd":    100_000},
]

REGION_COLORS = {
    "North America": "#3b82f6",   # blue
    "Middle East":   "#f59e0b",   # amber
    "Europe/Asia":   "#8b5cf6",   # violet
    "Asia":          "#ec4899",   # pink
    "South America": "#10b981",   # emerald
    "Africa":        "#f97316",   # orange
}

REGION_EMOJIS = {
    "North America": "🌎",
    "Middle East":   "🌍",
    "Europe/Asia":   "🌏",
    "Asia":          "🌏",
    "South America": "🌎",
    "Africa":        "🌍",
}


def format_bpd(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.2f}M bpd"
    elif n >= 1_000:
        return f"{n/1_000:.0f}K bpd"
    return f"{n:,} bpd"


def try_fetch_eia():
    url = (
        "https://api.eia.gov/v2/international/data/"
        "?frequency=annual&data[0]=value"
        "&facets[productId][]=53"
        "&facets[unit][]=TBPD"
        "&sort[0][column]=period&sort[0][direction]=desc"
        "&length=20"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "OilMonitor/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read())
        rows = payload.get("response", {}).get("data", [])
        if rows:
            return rows
    except Exception:
        pass
    return None


def build_html(data, use_live):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    source = "Live EIA API" if use_live else "Latest verified data (2024)"

    max_bpd = max(d["bpd"] for d in data)
    total_world = sum(d["bpd"] for d in data)

    # Group by region, sorted by region total descending
    regions = {}
    for row in data:
        regions.setdefault(row["region"], []).append(row)
    region_order = sorted(regions, key=lambda r: sum(d["bpd"] for d in regions[r]), reverse=True)

    # Africa summary stats
    africa = [d for d in data if d["region"] == "Africa"]
    africa_total = sum(d["bpd"] for d in africa)
    africa_share = africa_total / total_world * 100
    top_africa = sorted(africa, key=lambda x: x["bpd"], reverse=True)[0]["country"] if africa else "—"

    # ── Build region sections ─────────────────────────────────────────────────
    region_html = ""
    rank = 1
    for region in region_order:
        rows = sorted(regions[region], key=lambda x: x["bpd"], reverse=True)
        color = REGION_COLORS.get(region, "#6b7280")
        emoji = REGION_EMOJIS.get(region, "🌐")
        region_total = sum(d["bpd"] for d in rows)
        region_share = region_total / total_world * 100

        rows_html = ""
        for row in rows:
            pct = row["bpd"] / total_world * 100
            bar_pct = row["bpd"] / max_bpd * 100
            rows_html += f"""
            <tr>
              <td class="rank">#{rank}</td>
              <td class="country">{row['country']}</td>
              <td class="bpd">{format_bpd(row['bpd'])}</td>
              <td class="share">{pct:.1f}%</td>
              <td class="bar-cell">
                <div class="bar-track">
                  <div class="bar-fill" style="width:{bar_pct:.1f}%;background:{color}"></div>
                </div>
              </td>
            </tr>"""
            rank += 1

        region_html += f"""
        <div class="region-card">
          <div class="region-header" style="border-left:4px solid {color}">
            <span class="region-emoji">{emoji}</span>
            <span class="region-name">{region}</span>
            <span class="region-stats">{format_bpd(region_total)} &nbsp;·&nbsp; {region_share:.1f}% of total</span>
          </div>
          <table class="data-table">
            <thead>
              <tr>
                <th>Rank</th><th>Country</th><th>Production</th>
                <th>World Share</th><th>Relative Output</th>
              </tr>
            </thead>
            <tbody>{rows_html}</tbody>
          </table>
        </div>"""

    # ── Africa summary cards ──────────────────────────────────────────────────
    africa_html = ""
    if africa:
        africa_html = f"""
      <section class="africa-section">
        <h2 class="section-title">🌍 Africa Summary</h2>
        <div class="stat-grid">
          <div class="stat-card">
            <div class="stat-label">Total Production</div>
            <div class="stat-value">{format_bpd(africa_total)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">World Share</div>
            <div class="stat-value">{africa_share:.1f}%</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Countries Tracked</div>
            <div class="stat-value">{len(africa)}</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Largest Producer</div>
            <div class="stat-value">{top_africa}</div>
          </div>
        </div>
      </section>"""

    badge_color = "#10b981" if use_live else "#f59e0b"
    badge_text  = "● Live" if use_live else "● Cached"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Global Oil Production Monitor</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      min-height: 100vh;
      padding: 2rem 1rem;
    }}

    .container {{ max-width: 1000px; margin: 0 auto; }}

    /* ── Header ── */
    .header {{
      text-align: center;
      margin-bottom: 2.5rem;
    }}
    .header h1 {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.5px;
      color: #f1f5f9;
    }}
    .header .subtitle {{
      margin-top: 0.4rem;
      font-size: 0.9rem;
      color: #94a3b8;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }}
    .badge {{
      padding: 0.2rem 0.7rem;
      border-radius: 999px;
      font-size: 0.78rem;
      font-weight: 600;
      background: {badge_color}22;
      color: {badge_color};
      border: 1px solid {badge_color}55;
    }}

    /* ── World total banner ── */
    .world-banner {{
      background: linear-gradient(135deg, #1e3a5f 0%, #1e293b 100%);
      border: 1px solid #334155;
      border-radius: 12px;
      padding: 1.25rem 1.75rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2rem;
      flex-wrap: wrap;
      gap: 0.75rem;
    }}
    .world-banner .label {{ font-size: 0.85rem; color: #94a3b8; }}
    .world-banner .value {{ font-size: 1.6rem; font-weight: 700; color: #38bdf8; }}
    .world-banner .countries {{ font-size: 0.85rem; color: #94a3b8; text-align: right; }}

    /* ── Region cards ── */
    .region-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 12px;
      margin-bottom: 1.5rem;
      overflow: hidden;
    }}
    .region-header {{
      display: flex;
      align-items: center;
      gap: 0.75rem;
      padding: 0.9rem 1.25rem;
      background: #0f172a;
      border-bottom: 1px solid #334155;
    }}
    .region-emoji {{ font-size: 1.2rem; }}
    .region-name {{
      font-weight: 600;
      font-size: 1rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #f1f5f9;
      flex: 1;
    }}
    .region-stats {{ font-size: 0.82rem; color: #64748b; }}

    /* ── Data table ── */
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.88rem;
    }}
    .data-table thead th {{
      padding: 0.6rem 1rem;
      text-align: left;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      border-bottom: 1px solid #334155;
      background: #1a2744;
    }}
    .data-table tbody tr {{
      border-bottom: 1px solid #1e293b;
      transition: background 0.15s;
    }}
    .data-table tbody tr:last-child {{ border-bottom: none; }}
    .data-table tbody tr:hover {{ background: #263352; }}
    .data-table td {{
      padding: 0.65rem 1rem;
      vertical-align: middle;
    }}
    td.rank    {{ color: #64748b; font-size: 0.8rem; width: 50px; }}
    td.country {{ font-weight: 500; color: #f1f5f9; }}
    td.bpd     {{ font-variant-numeric: tabular-nums; color: #38bdf8; white-space: nowrap; }}
    td.share   {{ color: #94a3b8; white-space: nowrap; }}
    td.bar-cell {{ width: 35%; min-width: 140px; }}

    .bar-track {{
      height: 8px;
      background: #0f172a;
      border-radius: 4px;
      overflow: hidden;
    }}
    .bar-fill {{
      height: 100%;
      border-radius: 4px;
      transition: width 0.6s ease;
    }}

    /* ── Africa summary ── */
    .africa-section {{
      margin-top: 2rem;
    }}
    .section-title {{
      font-size: 1.1rem;
      font-weight: 600;
      color: #f1f5f9;
      margin-bottom: 1rem;
    }}
    .stat-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 1rem;
    }}
    .stat-card {{
      background: #1e293b;
      border: 1px solid #334155;
      border-radius: 10px;
      padding: 1.1rem 1.25rem;
    }}
    .stat-label {{ font-size: 0.78rem; color: #64748b; margin-bottom: 0.4rem; text-transform: uppercase; letter-spacing: 0.05em; }}
    .stat-value {{ font-size: 1.35rem; font-weight: 700; color: #f97316; }}

    /* ── Footer ── */
    .footer {{
      margin-top: 2.5rem;
      text-align: center;
      font-size: 0.78rem;
      color: #475569;
    }}

    @media (max-width: 600px) {{
      td.bar-cell {{ display: none; }}
      .data-table thead th:last-child {{ display: none; }}
    }}
  </style>
</head>
<body>
  <div class="container">

    <header class="header">
      <h1>🛢️ Global Oil Production Monitor</h1>
      <div class="subtitle">
        <span>Updated: {now}</span>
        <span class="badge">{badge_text} · {source}</span>
      </div>
    </header>

    <div class="world-banner">
      <div>
        <div class="label">World Total (shown countries)</div>
        <div class="value">{format_bpd(total_world)}</div>
      </div>
      <div class="countries">{len(data)} countries tracked</div>
    </div>

    <section>{region_html}</section>

    {africa_html}

    <footer class="footer">
      Data source: U.S. Energy Information Administration (EIA) · Figures in barrels per day
    </footer>

  </div>
</body>
</html>"""


def main():
    print("\n  Attempting to fetch live data from EIA…")
    live = try_fetch_eia()

    if live:
        parsed = []
        for row in live:
            parsed.append({
                "country": row.get("countryName", "Unknown"),
                "region":  row.get("countryRegionName", "Other"),
                "bpd":     int(float(row.get("value", 0)) * 1000),
            })
        html = build_html(parsed, use_live=True)
    else:
        print("  Live API unavailable — using latest verified data.\n")
        html = build_html(FALLBACK_DATA, use_live=False)

    # Write to a temp file and open in browser
    out_path = os.path.join(tempfile.gettempdir(), "oil_monitor.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"  Report saved to: {out_path}")
    webbrowser.open(f"file://{out_path}")
    print("  Opened in your default browser.\n")


if __name__ == "__main__":
    main()
