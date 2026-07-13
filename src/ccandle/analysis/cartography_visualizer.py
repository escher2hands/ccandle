"""
cartographer.py
Takes a list of enriched page node dicts and renders a standalone HTML
visualization showing structural richness vs. page importance.

Usage:
    from cartographer import render
    render(nodes, output_path="cartographer.html", space_title="My Space")
    # -> writes cartographer.html and returns the output path

Node dict schema (all fields required):
    {
        "pid":             int | str,
        "title":           str,
        "depth":           int,
        "direct_children": int,
        "descendants":     int,
        "word_count":      int,
        "subtree_words":   int | float,
        "quality":         float,   # 0.0–1.0
        "subtree_quality": float,   # 0.0–1.0
        "incoming_links":  int,
        "outgoing_links":  int,
        "type":            str,
    }
"""

from __future__ import annotations

import json
import math
import os
import webbrowser
from typing import Any


# ---------------------------------------------------------------------------
# Score computation
# Adds `structural` and `importance` float scores (both 0–1) to each node.
# ---------------------------------------------------------------------------
def _compute_scores(nodes: list[dict]) -> list[dict]:
    if not nodes:
        return []

    max_subtree_words   = max(n["subtree_words"]   for n in nodes) or 1
    max_subtree_quality = 1 #max(n["subtree_quality"] for n in nodes) or 1
    max_quality         = 1 #max(n["quality"]         for n in nodes) or 1
    max_incoming        = max(n["incoming_links"]  for n in nodes) or 1
    max_outgoing        = max(n["outgoing_links"]  for n in nodes) or 1

    enriched = []
    for n in nodes:
        structural = (
            0.50 * (n["subtree_words"]   / max_subtree_words)
          + 0.30 * (n["subtree_quality"] / max_subtree_quality)
          + 0.20 * (n["quality"]         / max_quality)
        )

        raw_importance = (
            0.55 * (n["incoming_links"] / max_incoming)
          + 0.25 * (n["outgoing_links"] / max_outgoing)
          + 0.20 * (n["quality"]        / max_quality)
        )

        # Soft depth penalty — buried gems lose at most ~40% of their score.
        # Depth 0 → ×1.0, depth 5+ → ×0.60
        depth_factor = max(0.60, 1.0 - n["depth"] * 0.08)
        importance = raw_importance * depth_factor

        enriched.append({**n, "structural": structural, "importance": importance})

    # Gem detection: depth >= 4, both scores in top 40% of the set
    if len(enriched) >= 3:
        imp_sorted  = sorted(e["importance"]  for e in enriched)
        str_sorted  = sorted(e["structural"]  for e in enriched)
        imp_thresh  = imp_sorted[math.floor(len(enriched) * 0.60)]
        str_thresh  = str_sorted[math.floor(len(enriched) * 0.60)]
    else:
        imp_thresh = str_thresh = 0.0

    for e in enriched:
        e["is_gem"] = (
            e["depth"] >= 4
            and e["importance"] >= imp_thresh
            and e["structural"] >= str_thresh
        )

    return enriched


# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
def _html(nodes_json: str, space_title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cartographer — {space_title}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

  :root {{
    --bg:        #f8f7f5;
    --surface:   #ffffff;
    --border:    rgba(0,0,0,0.10);
    --text:      #0b0b0b;
    --text-sec:  #52514e;
    --text-muted:#898781;
    --grid:      #e1e0d9;
    --radius:    8px;
  }}

  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg:        #111110;
      --surface:   #1a1a19;
      --border:    rgba(255,255,255,0.10);
      --text:      #ffffff;
      --text-sec:  #c3c2b7;
      --text-muted:#898781;
      --grid:      #2c2c2a;
    }}
  }}

  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }}

  header {{
    padding: 1rem 1.5rem 0.75rem;
    border-bottom: 0.5px solid var(--border);
    display: flex;
    align-items: baseline;
    gap: 1rem;
    flex-wrap: wrap;
  }}

  header h1 {{
    font-size: 15px;
    font-weight: 500;
    color: var(--text);
  }}

  header span {{
    font-size: 13px;
    color: var(--text-muted);
  }}

  #controls {{
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 0.6rem 1.5rem;
    border-bottom: 0.5px solid var(--border);
    flex-wrap: wrap;
  }}

  .ctrl {{
    display: flex;
    align-items: center;
    gap: 7px;
    font-size: 13px;
    color: var(--text-sec);
  }}

  .ctrl select {{
    font-size: 13px;
    padding: 3px 8px;
    border-radius: var(--radius);
    border: 0.5px solid var(--border);
    background: var(--surface);
    color: var(--text);
    cursor: pointer;
  }}

  .ctrl-sep {{
    width: 0.5px;
    height: 16px;
    background: var(--border);
  }}

  #hint {{
    margin-left: auto;
    font-size: 12px;
    color: var(--text-muted);
  }}

  #main {{
    display: flex;
    flex: 1;
    overflow: hidden;
  }}

  #chart-wrap {{
    flex: 1;
    position: relative;
    min-height: 500px;
  }}

  canvas {{
    display: block;
    position: absolute;
    inset: 0;
  }}

  /* ---- Tooltip ---- */
  #tooltip {{
    position: fixed;
    display: none;
    pointer-events: none;
    background: var(--surface);
    border: 0.5px solid var(--border);
    border-radius: var(--radius);
    padding: 10px 14px;
    font-size: 13px;
    color: var(--text);
    min-width: 210px;
    max-width: 280px;
    z-index: 999;
    box-shadow: 0 2px 12px rgba(0,0,0,0.10);
  }}

  #tooltip .tt-title {{
    font-size: 14px;
    font-weight: 500;
    margin-bottom: 8px;
    line-height: 1.35;
    color: var(--text);
  }}

  #tooltip .tt-row {{
    display: flex;
    justify-content: space-between;
    gap: 12px;
    padding: 1.5px 0;
    color: var(--text-sec);
    font-size: 12px;
  }}

  #tooltip .tt-val {{
    font-weight: 500;
    color: var(--text);
    text-align: right;
  }}

  #tooltip .tt-divider {{
    border: none;
    border-top: 0.5px solid var(--border);
    margin: 6px 0;
  }}

  #tooltip .tt-gem {{
    display: inline-block;
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 20px;
    background: #eda10022;
    color: #eda100;
    margin-top: 6px;
    font-weight: 500;
  }}

  /* ---- Sidebar: gems panel ---- */
  #sidebar {{
    width: 240px;
    border-left: 0.5px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }}

  #sidebar h2 {{
    font-size: 12px;
    font-weight: 500;
    color: var(--text-muted);
    padding: 0.75rem 1rem 0.5rem;
    letter-spacing: 0.05em;
    text-transform: uppercase;
    border-bottom: 0.5px solid var(--border);
  }}

  #gem-list {{
    overflow-y: auto;
    flex: 1;
    padding: 0.5rem 0;
  }}

  .gem-item {{
    padding: 7px 1rem;
    cursor: default;
    border-left: 2px solid transparent;
    transition: border-color 0.1s;
  }}

  .gem-item:hover {{
    background: var(--bg);
    border-left-color: #eda100;
  }}

  .gem-title {{
    font-size: 13px;
    font-weight: 500;
    color: var(--text);
    line-height: 1.3;
    margin-bottom: 3px;
  }}

  .gem-meta {{
    font-size: 11px;
    color: var(--text-muted);
  }}

  /* ---- Legend ---- */
  #legend {{
    padding: 0.5rem 1.5rem;
    border-top: 0.5px solid var(--border);
    display: flex;
    gap: 16px;
    font-size: 12px;
    color: var(--text-muted);
    flex-wrap: wrap;
    align-items: center;
  }}

  .legend-item {{
    display: flex;
    align-items: center;
    gap: 5px;
  }}

  .legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }}

  .legend-grad {{
    width: 48px;
    height: 10px;
    border-radius: 3px;
    flex-shrink: 0;
  }}
</style>
</head>
<body>

<header>
  <h1>Cartographer &mdash; {space_title}</h1>
  <span id="node-count"></span>
</header>

<div id="controls">
  <div class="ctrl">
    <label for="size-by">Size by</label>
    <select id="size-by">
      <option value="descendants">Descendants</option>
      <option value="subtree_words">Subtree words</option>
      <option value="word_count">Word count</option>
    </select>
  </div>
  <div class="ctrl-sep"></div>
  <div class="ctrl">
    <label for="color-by">Color by</label>
    <select id="color-by">
      <option value="type">Page type</option>
      <option value="depth">Depth</option>
      <option value="total_links">Total links (in + out)</option>
      <option value="quality">Quality</option>
    </select>
  </div>
  <div class="ctrl-sep"></div>
  <div class="ctrl">
    <label for="hide-junk">
      <input type="checkbox" id="hide-junk"> Hide low-value branches
    </label>
  </div>
  <span id="hint">Hover to inspect &nbsp;&middot;&nbsp; top-right = start here</span>
</div>

<div id="main">
  <div id="chart-wrap">
    <canvas id="c"></canvas>
  </div>
  <div id="sidebar">
    <h2>Buried gems</h2>
    <div id="gem-list"></div>
  </div>
</div>

<div id="legend"></div>

<div id="tooltip">
  <div class="tt-title" id="tt-title"></div>
  <hr class="tt-divider">
  <div class="tt-row"><span>Depth</span><span class="tt-val" id="tt-depth"></span></div>
  <div class="tt-row"><span>Children / descendants</span><span class="tt-val" id="tt-cd"></span></div>
  <div class="tt-row"><span>Word count</span><span class="tt-val" id="tt-wc"></span></div>
  <div class="tt-row"><span>Subtree words</span><span class="tt-val" id="tt-sw"></span></div>
  <div class="tt-row"><span>Quality</span><span class="tt-val" id="tt-q"></span></div>
  <div class="tt-row"><span>Incoming / outgoing links</span><span class="tt-val" id="tt-links"></span></div>
  <hr class="tt-divider">
  <div class="tt-row"><span>Structural score</span><span class="tt-val" id="tt-struct"></span></div>
  <div class="tt-row"><span>Importance score</span><span class="tt-val" id="tt-imp"></span></div>
  <div class="tt-row"><span>Type</span><span class="tt-val" id="tt-type"></span></div>
  <div id="tt-gem-badge"></div>
</div>

<script>
const ALL_NODES = {nodes_json};

// ---- Color schemes ----

const TYPE_PALETTE = {{
  solution_docs:    "#2a78d6",
  landing_page:     "#1baf7a",
  meeting_minutes:  "#888780",
  workshop_minutes: "#eda100",
  uncategorized:    "#b4b2a9",
}};
const TYPE_FALLBACK = "#4a3aa7";

const DEPTH_COLORS = ["#2a78d6","#1baf7a","#eda100","#e34948","#4a3aa7","#e87ba4","#eb6834"];

function depthColor(d) {{
  return DEPTH_COLORS[Math.min(d, DEPTH_COLORS.length - 1)];
}}

function lerp(a, b, t) {{
  return Math.round(a + (b - a) * t);
}}

// blue → red for links / quality
function rampColor(t) {{
  const r = lerp(42, 227, t);
  const g = lerp(120, 30, t);
  const b = lerp(214, 27, t);
  return `rgb(${{r}},${{g}},${{b}})`;
}}

function nodeColor(node, mode, maxTotalLinks) {{
  if (mode === "type")        return TYPE_PALETTE[node.type] ?? TYPE_FALLBACK;
  if (mode === "depth")       return depthColor(node.depth);
  if (mode === "total_links") return rampColor((node.incoming_links + node.outgoing_links) / maxTotalLinks);
  if (mode === "quality")     return rampColor(node.quality);
  return "#888780";
}}

// is_gem is pre-computed by Python — no client-side gem detection needed.

// ---- Auto-ranging helpers ----
// Computes {min, max} of a score key across nodes with padding so bubbles
// never sit exactly on the axis edge.

function dataRange(nodes, key, padFrac=0.10) {{
  const vals = nodes.map(n => n[key]);
  let lo = Math.min(...vals);
  let hi = Math.max(...vals);
  if (lo === hi) {{ lo -= 0.05; hi += 0.05; }}
  const pad = (hi - lo) * padFrac;
  return {{ min: lo - pad, max: hi + pad }};
}}

// Map a raw score value into canvas [0,1] within the visible range.
function norm(v, range) {{
  return Math.max(0, Math.min(1, (v - range.min) / (range.max - range.min)));
}}

// Extract r,g,b components from an rgb(...) string so we can build rgba().
function rgbToRgba(rgbStr, alpha) {{
  const m = rgbStr.match(/rgb\\((\\d+),(\\d+),(\\d+)\\)/);
  if (m) return `rgba(${{m[1]}},${{m[2]}},${{m[3]}},${{alpha}})`;
  return rgbStr; // hex fallback — browsers handle hex fill fine
}}

// ---- Canvas renderer ----

const canvas = document.getElementById("c");
const ctx    = canvas.getContext("2d");
const PAD    = {{ top: 32, right: 28, bottom: 52, left: 60 }};
let positions = [];
let currentNodes = [];

function isDark() {{
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}}

function cssVar(name) {{
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}}

function resize() {{
  const wrap = document.getElementById("chart-wrap");
  canvas.width  = wrap.clientWidth;
  canvas.height = wrap.clientHeight;
  draw();
}}

function getRadius(node, sizeMode) {{
  const maxVal = Math.max(...currentNodes.map(n => n[sizeMode])) || 1;
  const t = node[sizeMode] / maxVal;
  return 10 + Math.sqrt(t) * 38;
}}

function draw() {{
  const W = canvas.width;
  const H = canvas.height;
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top  - PAD.bottom;

  ctx.clearRect(0, 0, W, H);

  const dark      = isDark();
  const textMuted = dark ? "#898781" : "#898781";
  const textSec   = dark ? "#c3c2b7" : "#52514e";
  const textPri   = dark ? "#ffffff" : "#0b0b0b";
  const gridCol   = dark ? "#2c2c2a" : "#e1e0d9";

  const sizeMode  = document.getElementById("size-by").value;
  const colorMode = document.getElementById("color-by").value;
  const maxTotalLinks = Math.max(...currentNodes.map(n => n.incoming_links + n.outgoing_links)) || 1;

  // Compute data ranges for auto-scaled axes
  const srRange  = dataRange(currentNodes, "structural");
  const impRange = dataRange(currentNodes, "importance");

  // Grid lines + axis tick labels (show actual data-range values)
  const ticks = [0, 0.25, 0.5, 0.75, 1.0];

  ctx.lineWidth = 0.5;
  ctx.font = "11px -apple-system, sans-serif";

  ticks.forEach(t => {{
    const y = PAD.top + plotH * (1 - t);
    ctx.strokeStyle = gridCol;
    ctx.beginPath(); ctx.moveTo(PAD.left, y); ctx.lineTo(PAD.left + plotW, y); ctx.stroke();
    const labelVal = impRange.min + t * (impRange.max - impRange.min);
    ctx.fillStyle = textMuted;
    ctx.textAlign = "right";
    ctx.fillText(labelVal.toFixed(2), PAD.left - 7, y + 4);
  }});

  ticks.forEach(t => {{
    const x = PAD.left + plotW * t;
    ctx.strokeStyle = gridCol;
    ctx.beginPath(); ctx.moveTo(x, PAD.top); ctx.lineTo(x, PAD.top + plotH); ctx.stroke();
    const labelVal = srRange.min + t * (srRange.max - srRange.min);
    ctx.fillStyle = textMuted;
    ctx.textAlign = "center";
    ctx.fillText(labelVal.toFixed(2), x, PAD.top + plotH + 18);
  }});

  // Axis labels
  ctx.fillStyle = textSec;
  ctx.font = "12px -apple-system, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("structural richness  →", PAD.left + plotW / 2, H - 8);

  ctx.save();
  ctx.translate(14, PAD.top + plotH / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText("importance  →", 0, 0);
  ctx.restore();

  // Quadrant label (faint) — always top-right corner = best pages
  ctx.fillStyle = dark ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)";
  ctx.font = "bold 11px -apple-system, sans-serif";
  ctx.textAlign = "right";
  ctx.fillText("start here", PAD.left + plotW - 8, PAD.top + 18);

  // Draw nodes — smaller ones first so large ones sit on top
  const sorted = [...currentNodes].sort((a, b) => getRadius(a, sizeMode) - getRadius(b, sizeMode));
  positions = [];

  sorted.forEach(node => {{
    // Map scores into canvas coords via data range
    const nx = norm(node.structural, srRange);
    const ny = norm(node.importance, impRange);
    const x  = PAD.left + nx * plotW;
    const y  = PAD.top  + (1 - ny) * plotH;
    const r  = getRadius(node, sizeMode);
    const color = nodeColor(node, colorMode, maxTotalLinks);

    positions.push({{ node, x, y, r }});

    // Fill — use rgba() to avoid the hex-append bug with rgb() strings
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = rgbToRgba(color, 0.13);
    ctx.fill();

    // Stroke
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = node.is_gem ? 2.5 : 1.5;
    ctx.setLineDash([]);
    ctx.stroke();

    // Gem ring
    if (node.is_gem) {{
      ctx.beginPath();
      ctx.arc(x, y, r + 4, 0, Math.PI * 2);
      ctx.strokeStyle = "#eda100";
      ctx.lineWidth = 1;
      ctx.setLineDash([3, 3]);
      ctx.stroke();
      ctx.setLineDash([]);
    }}

    // Label inside bubble (only if large enough)
    if (r > 20) {{
      ctx.fillStyle = textPri;
      ctx.textAlign = "center";
      const fontSize = Math.min(12, r * 0.36);
      ctx.font = `${{fontSize}}px -apple-system, sans-serif`;
      const maxW = r * 1.7;
      const words = node.title.split(" ");
      let line = "", lines = [];
      words.forEach(w => {{
        const test = line ? line + " " + w : w;
        if (ctx.measureText(test).width > maxW && line) {{ lines.push(line); line = w; }}
        else line = test;
      }});
      if (line) lines.push(line);
      lines = lines.slice(0, 3);
      const lineH = fontSize + 2;
      const startY = y - (lines.length - 1) * lineH / 2;
      lines.forEach((l, i) => ctx.fillText(l, x, startY + i * lineH + fontSize * 0.35));
    }}
  }});
}}

// ---- Tooltip ----

const tooltip = document.getElementById("tooltip");

function fmt(n) {{ return Number(n).toLocaleString(); }}

canvas.addEventListener("mousemove", e => {{
  const rect = canvas.getBoundingClientRect();
  const mx = e.clientX - rect.left;
  const my = e.clientY - rect.top;

  let hit = null;
  for (let i = positions.length - 1; i >= 0; i--) {{
    const {{ node, x, y, r }} = positions[i];
    if (Math.hypot(mx - x, my - y) <= r) {{ hit = node; break; }}
  }}

  if (hit) {{
    document.getElementById("tt-title").textContent  = hit.title;
    document.getElementById("tt-depth").textContent  = hit.depth;
    document.getElementById("tt-cd").textContent     = `${{hit.direct_children}} / ${{hit.descendants}}`;
    document.getElementById("tt-wc").textContent     = fmt(hit.word_count);
    document.getElementById("tt-sw").textContent     = fmt(hit.subtree_words);
    document.getElementById("tt-q").textContent      = hit.quality.toFixed(2);
    document.getElementById("tt-links").textContent  = `${{hit.incoming_links}} in / ${{hit.outgoing_links}} out`;
    document.getElementById("tt-struct").textContent = hit.structural.toFixed(3);
    document.getElementById("tt-imp").textContent    = hit.importance.toFixed(3);
    document.getElementById("tt-type").textContent   = hit.type;
    document.getElementById("tt-gem-badge").innerHTML = hit.is_gem
      ? '<span class="tt-gem">buried gem</span>' : "";

    const tx = e.clientX + 18;
    const ty = e.clientY - 10;
    tooltip.style.left    = tx + "px";
    tooltip.style.top     = ty + "px";
    tooltip.style.display = "block";
    canvas.style.cursor   = "crosshair";
  }} else {{
    tooltip.style.display = "none";
    canvas.style.cursor   = "default";
  }}
}});

canvas.addEventListener("mouseleave", () => {{ tooltip.style.display = "none"; }});

// ---- Gems sidebar ----

function buildGemList(nodes) {{
  const gems = nodes
    .filter(n => n.is_gem)
    .sort((a, b) => (b.importance + b.structural) - (a.importance + a.structural));

  const list = document.getElementById("gem-list");
  list.innerHTML = "";

  if (gems.length === 0) {{
    list.innerHTML = `<p style="padding:1rem; font-size:13px; color:var(--text-muted);">No buried gems found at this threshold.</p>`;
    return;
  }}

  gems.forEach(g => {{
    const el = document.createElement("div");
    el.className = "gem-item";
    el.innerHTML = `
      <div class="gem-title">${{g.title}}</div>
      <div class="gem-meta">Depth ${{g.depth}} &middot; ${{g.descendants}} desc &middot; ${{fmt(g.subtree_words)}} words</div>
    `;
    list.appendChild(el);
  }});
}}

// ---- Legend ----

function buildLegend() {{
  const mode = document.getElementById("color-by").value;
  const lg   = document.getElementById("legend");
  lg.innerHTML = "";

  const label = document.createElement("span");
  label.style.fontSize = "12px";
  label.style.color    = "var(--text-muted)";
  label.style.marginRight = "4px";
  label.textContent = "Color:";
  lg.appendChild(label);

  if (mode === "type") {{
    Object.entries(TYPE_PALETTE).forEach(([type, color]) => {{
      const el = document.createElement("div");
      el.className = "legend-item";
      el.innerHTML = `<div class="legend-dot" style="background:${{color}}"></div><span>${{type.replace("_", " ")}}</span>`;
      lg.appendChild(el);
    }});
  }} else if (mode === "depth") {{
    DEPTH_COLORS.slice(0, 6).forEach((color, d) => {{
      const el = document.createElement("div");
      el.className = "legend-item";
      el.innerHTML = `<div class="legend-dot" style="background:${{color}}"></div><span>depth ${{d}}</span>`;
      lg.appendChild(el);
    }});
  }} else {{
    const gradLabel = mode === "total_links" ? "low → high total links (in + out)" : "low → high quality";
    const el = document.createElement("div");
    el.className = "legend-item";
    el.innerHTML = `
      <div class="legend-grad" style="background: linear-gradient(to right, rgb(42,120,214), rgb(227,30,27))"></div>
      <span>${{gradLabel}}</span>`;
    lg.appendChild(el);
  }}

  const gemEl = document.createElement("div");
  gemEl.className = "legend-item";
  gemEl.style.marginLeft = "16px";
  gemEl.innerHTML = `
    <div class="legend-dot" style="width:14px;height:14px;border-radius:50%;border:2px solid #eda100;background:transparent"></div>
    <span>buried gem (deep + high value)</span>`;
  lg.appendChild(gemEl);
}}

// ---- Filtering ----

function applyFilters() {{
  const hideJunk = document.getElementById("hide-junk").checked;

  let nodes = ALL_NODES;
  if (hideJunk) {{
    const avgSubtreePerDesc = n => n.descendants > 0 ? n.subtree_words / n.descendants : n.word_count;
    const threshold = 150;
    nodes = nodes.filter(n => avgSubtreePerDesc(n) >= threshold || n.depth === 0);
  }}

  currentNodes = nodes;
  document.getElementById("node-count").textContent = `${{currentNodes.length}} nodes`;
  buildGemList(currentNodes);
  buildLegend();
  draw();
}}

// ---- Wire up controls ----

["size-by", "color-by", "hide-junk"].forEach(id => {{
  document.getElementById(id).addEventListener("change", () => {{
    if (id === "color-by") buildLegend();
    draw();
    if (id === "hide-junk") applyFilters();
  }});
}});

window.addEventListener("resize", resize);

// ---- Error surface ----
// Catch JS exceptions and show them visibly instead of a silent blank page.
window.addEventListener("error", e => {{
  document.body.innerHTML = `
    <div style="padding:2rem; font-family:monospace; color:#e34948; background:#1a0a0a;">
      <strong>Cartographer JS error</strong><br><br>
      ${{e.message}}<br>
      ${{e.filename}}:${{e.lineno}}
    </div>`;
}});

// ---- Init ----
try {{
  applyFilters();
  resize();
}} catch(e) {{
  document.body.innerHTML = `
    <div style="padding:2rem; font-family:monospace; color:#e34948; background:#1a0a0a;">
      <strong>Cartographer init error</strong><br><br>${{e.message}}<br><pre>${{e.stack}}</pre>
    </div>`;
}}
</script>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_pages_map(
    nodes: list[dict[str, Any]],
    output_path: str = "cartographer.html",
    space_title: str = "Confluence Space",
    open_browser: bool = True,
) -> str:
    """
    Compute scores for `nodes`, write a self-contained HTML visualization to
    `output_path`, optionally open it in the default browser, and return the
    resolved output path.

    Parameters
    ----------
    nodes : list[dict]
        Page node dicts matching the cartographer schema.
    output_path : str
        Destination file path for the HTML output.
    space_title : str
        Human-readable space name shown in the page header.
    open_browser : bool
        If True, open the output file in the system browser after writing.

    Returns
    -------
    str
        Absolute path to the written HTML file.
    """
    if not nodes:
        raise ValueError("nodes list is empty — nothing to visualize.")

    enriched = _compute_scores(nodes)
    # Escape </script> in the JSON so it can't break the HTML <script> block.
    # json.dumps produces valid JSON; we then escape the only dangerous sequence.
    nodes_json = json.dumps(enriched, ensure_ascii=False).replace("</", "<\\/")
    html = _html(nodes_json, space_title)

    output_path = os.path.abspath(output_path)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    if open_browser:
        webbrowser.open(f"file://{output_path}")

    return output_path