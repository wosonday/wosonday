"""Build the SVG cards used by the profile README.

Writes light and dark variants of:
  assets/banner-*.svg   name block over a field of synthetic hydrographs
  assets/skills-*.svg   two-column skills list (text only, no icons)
  assets/github-*.svg   contributions, stars, repositories, followers, languages

Only the standard library is used. The GitHub card needs a token in
GITHUB_TOKEN or GH_TOKEN (the default Actions token is enough); run with
--offline to build only the banner and skills cards.
"""

from __future__ import annotations

import json
import math
import os
import random
import sys
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
PROFILE = json.loads((ROOT / "scripts" / "profile.json").read_text(encoding="utf-8"))

W = 860
SERIF = "Georgia, 'Times New Roman', Times, serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

# GitHub Primer colours, so the cards blend into the profile page in both themes.
THEMES = {
    "light": {"text": "#1f2328", "muted": "#59636e", "line": "#d1d9e0", "art": ["#0f4c75", "#1b998b", "#3a7d44"]},
    "dark": {"text": "#f0f6fc", "muted": "#9198a1", "line": "#3d444d", "art": ["#5fa8d3", "#3ccfb4", "#7cc47f"]},
}


def svg(width: int, height: int, label: str, body: str) -> str:
    label = escape(label)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">'
        f"<title>{label}</title>{body}</svg>\n"
    )


def text(x, y, s, *, size, fill, family=SANS, weight=400, anchor="start", extra=""):
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}"{extra}>{escape(str(s))}</text>'
    )


def wrap(s: str, size: float, width: float) -> list[str]:
    """Greedy word wrap using an average glyph width (no font metrics needed)."""
    per_line = max(8, int(width / (size * 0.54)))
    lines, cur = [], ""
    for word in s.split():
        if cur and len(cur) + 1 + len(word) > per_line:
            lines.append(cur)
            cur = word
        else:
            cur = f"{cur} {word}".strip()
    return lines + ([cur] if cur else [])


# --------------------------------------------------------------------------- banner

def hydrograph(rng: random.Random, days: int = 365) -> list[float]:
    """One synthetic year of daily streamflow (arbitrary units).

    Rain events (more frequent in the wet season, late in the year in central
    Vietnam) are routed through two linear reservoirs in series, a small Nash
    cascade, so each storm gives a smooth rise and an exponential recession.
    """
    k = 0.72  # fraction of storage kept each day; higher = slower recession
    s1 = s2 = 0.0
    flow = []
    for d in range(days):
        season = 0.5 + 0.5 * math.sin(2 * math.pi * (d - 200) / days)
        rain = rng.expovariate(1.0) * (0.5 + season) if rng.random() < 0.03 + 0.08 * season else 0.0
        s1 += rain
        q1 = (1 - k) * s1
        s1 -= q1
        s2 += q1
        q2 = (1 - k) * s2
        s2 -= q2
        flow.append(0.2 + 0.4 * season + q2)
    return flow


def banner(theme: dict) -> str:
    h = 300
    rng = random.Random(27)
    rows, top, step, amp = 12, 20, 15, 64
    paths = []
    for i in range(rows):
        series = hydrograph(rng)
        peak = max(series)
        base = top + amp + i * step
        pts = [
            f"{W * d / (len(series) - 1):.1f} {base - amp * math.sqrt(v / peak):.1f}"
            for d, v in enumerate(series)
        ]
        colour = theme["art"][i * len(theme["art"]) // rows]
        opacity = 0.25 + 0.5 * (i / (rows - 1))
        paths.append(
            f'<path d="M{" L".join(pts)}" fill="none" stroke="{colour}" '
            f'stroke-width="1.1" stroke-opacity="{opacity:.2f}" stroke-linejoin="round"/>'
        )

    # Fade the hydrographs out behind the name block on the lower left.
    defs = (
        '<defs><linearGradient id="fade" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="#000"/><stop offset="0.45" stop-color="#000"/>'
        '<stop offset="0.8" stop-color="#fff"/></linearGradient>'
        f'<mask id="quiet" maskUnits="userSpaceOnUse" x="0" y="0" width="{W}" height="{h}">'
        f'<rect width="{W}" height="{h}" fill="#fff"/>'
        f'<rect x="0" y="150" width="{W}" height="{h - 150}" fill="url(#fade)"/></mask></defs>'
    )
    art = f'<g mask="url(#quiet)">{"".join(paths)}</g>'
    name = (
        text(24, 238, PROFILE["name"], size=44, fill=theme["text"], family=SERIF)
        + text(26, 266, PROFILE["title"], size=16, fill=theme["text"])
        + text(26, 288, PROFILE["affiliation"], size=14, fill=theme["muted"])
    )
    label = f'{PROFILE["name"]}, {PROFILE["title"]}. {PROFILE["affiliation"]}.'
    return svg(W, h, label, defs + art + name)


# --------------------------------------------------------------------------- skills

def skills(theme: dict) -> str:
    col_w, gap = 404, 52
    groups = PROFILE["skills"]
    half = math.ceil(len(groups) / 2)
    body, heights = [], []
    for col, chunk in enumerate((groups[:half], groups[half:])):
        x, y = col * (col_w + gap), 0
        for g in chunk:
            lines = wrap(g["items"], 14, col_w)
            body.append(f'<rect x="{x}" y="{y}" width="{col_w}" height="1" fill="{theme["line"]}"/>')
            body.append(text(x, y + 28, g["group"], size=15, fill=theme["text"], weight=600))
            for j, line in enumerate(lines):
                body.append(text(x, y + 51 + j * 21, line, size=14, fill=theme["muted"]))
            y += 51 + len(lines) * 21 + 12
        heights.append(y)
    label = "Technical skills. " + " ".join(f'{g["group"]}: {g["items"]}.' for g in groups)
    return svg(W, int(max(heights)), label, "".join(body))


# --------------------------------------------------------------------------- github

QUERY = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection { contributionCalendar { totalContributions } }
    repositories(ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC, first: 100) {
      totalCount
      nodes {
        stargazerCount
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""


def fetch_github(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-cards"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        raise SystemExit(f"GitHub API error: {payload['errors']}")
    u = payload["data"]["user"]
    sizes, colours = Counter(), {}
    for repo in u["repositories"]["nodes"]:
        for e in repo["languages"]["edges"]:
            sizes[e["node"]["name"]] += e["size"]
            colours[e["node"]["name"]] = e["node"]["color"] or "#8b949e"
    total = sum(sizes.values()) or 1
    top = [(n, 100 * s / total, colours[n]) for n, s in sizes.most_common(5)]
    other = 100 - sum(p for _, p, _ in top)
    if other >= 0.1:
        top.append(("Other", other, "#8b949e"))
    return {
        "stats": [
            (u["contributionsCollection"]["contributionCalendar"]["totalContributions"], "contributions in 12 months"),
            (sum(r["stargazerCount"] for r in u["repositories"]["nodes"]), "stars"),
            (u["repositories"]["totalCount"], "public repositories"),
            (u["followers"]["totalCount"], "followers"),
        ],
        "languages": top,
    }


def github(theme: dict, data: dict) -> str:
    h = 128
    body = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{h - 1}" rx="6" fill="none" stroke="{theme["line"]}"/>']
    for x, (value, label) in zip((26, 216, 284, 420), data["stats"]):
        body.append(text(x, 64, f"{value:,}", size=28, fill=theme["text"], family=SERIF))
        body.append(text(x, 88, label, size=13, fill=theme["muted"]))

    lx, bar_w = 520, 314
    body.append(text(lx, 34, "Languages", size=14, fill=theme["text"], weight=600))
    body.append(f'<clipPath id="bar"><rect x="{lx}" y="46" width="{bar_w}" height="8" rx="4"/></clipPath><g clip-path="url(#bar)">')
    bx = lx
    for _, pct, colour in data["languages"]:
        w = bar_w * pct / 100
        body.append(f'<rect x="{bx:.1f}" y="46" width="{w + 0.5:.1f}" height="8" fill="{colour}"/>')
        bx += w
    body.append("</g>")
    for i, (name, pct, colour) in enumerate(data["languages"]):
        cx, cy = lx + (i % 3) * 108, 80 + (i // 3) * 24
        body.append(f'<circle cx="{cx + 5}" cy="{cy - 4}" r="5" fill="{colour}"/>')
        body.append(
            f'<text x="{cx + 16}" y="{cy}" font-family="{SANS}" font-size="13" fill="{theme["text"]}">'
            f'{escape(name)} <tspan fill="{theme["muted"]}">{pct:.1f}%</tspan></text>'
        )
    label = "GitHub: " + ", ".join(f"{v:,} {l}" for v, l in data["stats"]) + ". Languages: " + ", ".join(
        f"{n} {p:.1f}%" for n, p, _ in data["languages"]
    )
    return svg(W, h, label, "".join(body))


# --------------------------------------------------------------------------- main

def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    offline = "--offline" in sys.argv
    data = None
    if not offline:
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if not token:
            raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN, or pass --offline.")
        data = fetch_github(PROFILE["user"], token)
    for mode, theme in THEMES.items():
        (ASSETS / f"banner-{mode}.svg").write_text(banner(theme), encoding="utf-8")
        (ASSETS / f"skills-{mode}.svg").write_text(skills(theme), encoding="utf-8")
        if data:
            (ASSETS / f"github-{mode}.svg").write_text(github(theme, data), encoding="utf-8")
    print("wrote", sorted(p.name for p in ASSETS.glob("*.svg")))


if __name__ == "__main__":
    main()
