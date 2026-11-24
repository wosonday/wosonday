"""Build the GitHub stats card used by the profile README.

Writes assets/github-light.svg and assets/github-dark.svg with contributions in
the last 12 months, stars, public repositories, followers and a language bar.
Only the standard library is used. Needs a token in GITHUB_TOKEN or GH_TOKEN
(the default GitHub Actions token is enough).
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections import Counter
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
USER = os.environ.get("PROFILE_USER", "wosonday")

W, H = 860, 128
SERIF = "Georgia, 'Times New Roman', Times, serif"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

# GitHub Primer colours, so the card blends into the profile page in both themes.
THEMES = {
    "light": {"text": "#1f2328", "muted": "#59636e", "line": "#d1d9e0"},
    "dark": {"text": "#f0f6fc", "muted": "#9198a1", "line": "#3d444d"},
}

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


def fetch(login: str, token: str) -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "profile-card"},
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
    langs = [(n, 100 * s / total, colours[n]) for n, s in sizes.most_common(5)]
    other = 100 - sum(p for _, p, _ in langs)
    if other >= 0.1:
        langs.append(("Other", other, "#8b949e"))

    return {
        "stats": [
            (u["contributionsCollection"]["contributionCalendar"]["totalContributions"], "contributions in 12 months"),
            (sum(r["stargazerCount"] for r in u["repositories"]["nodes"]), "stars"),
            (u["repositories"]["totalCount"], "public repositories"),
            (u["followers"]["totalCount"], "followers"),
        ],
        "languages": langs,
    }


def text(x, y, s, *, size, fill, family=SANS, weight=400):
    return (
        f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}">{escape(str(s))}</text>'
    )


def card(theme: dict, data: dict) -> str:
    body = [f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="6" fill="none" stroke="{theme["line"]}"/>']
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

    label = escape(
        "GitHub: " + ", ".join(f"{v:,} {l}" for v, l in data["stats"])
        + ". Languages: " + ", ".join(f"{n} {p:.1f}%" for n, p, _ in data["languages"])
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
        f'role="img" aria-label="{label}"><title>{label}</title>{"".join(body)}</svg>\n'
    )


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN.")
    data = fetch(USER, token)
    ASSETS.mkdir(exist_ok=True)
    for mode, theme in THEMES.items():
        (ASSETS / f"github-{mode}.svg").write_text(card(theme, data), encoding="utf-8")
    print("wrote github-light.svg and github-dark.svg:", data["stats"])


if __name__ == "__main__":
    main()
