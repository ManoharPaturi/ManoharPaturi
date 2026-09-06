#!/usr/bin/env python3
"""Generate assets/stats.svg + assets/languages.svg from the GitHub API.

Runs locally (GH_TOKEN env) and inside .github/workflows/stats.yml.
Uses only the stdlib so no pip install is needed anywhere.
"""
import json
import os
import urllib.request
from datetime import datetime, timezone
from urllib.parse import quote

USER = "ManoharPaturi"
# repos whose language stats are generated output (Plotly report bundles), not hand-written code
EXCLUDE_REPOS = {"mocap_mac"}
TOKEN = os.environ.get("GH_TOKEN")
API = "https://api.github.com"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

BG, BORDER, BLUE, PURPLE, TEXT, MUTED = "#0D1117", "#30363D", "#58A6FF", "#A371F7", "#E6EDF3", "#8B949E"
MONO = "ui-monospace, Menlo, Consolas, monospace"

# GitHub linguist colors for the languages this account actually has
COLORS = {
    "Python": "#3572A5", "C": "#555555", "C++": "#f34b7d", "Java": "#b07219",
    "Dart": "#00B4AB", "TypeScript": "#3178C6", "JavaScript": "#f1e05a",
    "Go": "#00ADD8", "MATLAB": "#e16737", "HTML": "#e34c26", "CSS": "#563d7c",
    "Shell": "#89e051", "Jupyter Notebook": "#DA5B0B", "TeX": "#3D6117",
    "CMake": "#DA3434", "Makefile": "#427819", "Batchfile": "#C1F12E",
    "Swift": "#F05138", "Kotlin": "#A97BFF", "Rust": "#dea584", "R": "#198CE7",
}


def call(url, gql=None):
    req = urllib.request.Request(url, method="POST" if gql else "GET")
    req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats-generator")
    data = json.dumps({"query": gql}).encode() if gql else None
    with urllib.request.urlopen(req, data=data, timeout=30) as r:
        return json.loads(r.read().decode())


def search_count(q):
    return call(f"{API}/search/issues?per_page=1&q={quote(q)}")["total_count"]


def collect():
    user = call(f"{API}/users/{USER}")
    repos = call(f"{API}/users/{USER}/repos?per_page=100&type=owner")

    lang_bytes = {}
    for r in repos:
        if r["fork"] or r["name"] in EXCLUDE_REPOS:
            continue
        for lang, n in call(r["languages_url"]).items():
            lang_bytes[lang] = lang_bytes.get(lang, 0) + n
    top_langs = sorted(lang_bytes.items(), key=lambda kv: -kv[1])[:8]
    total = sum(lang_bytes.values()) or 1

    now = datetime.now(timezone.utc)
    first_year = datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ").year
    parts = ", ".join(
        f'y{y}: contributionsCollection(from: "{y}-01-01T00:00:00Z", to: "{y}-12-31T23:59:59Z") '
        f"{{ totalCommitContributions }}" for y in range(first_year, now.year + 1)
    )
    gql = f'query {{ user(login: "{USER}") {{ {parts} }} }}'
    res = call(f"{API}/graphql", gql=gql)
    commits = sum(v["totalCommitContributions"] for v in res["data"]["user"].values())

    stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
    prs = search_count(f"is:pr author:{USER}")
    merged = search_count(f"is:pr author:{USER} is:merged")
    issues = search_count(f"is:issue author:{USER}")

    rows = [
        ("total stars", f"{stars:,}"),
        ("public repos", f"{user['public_repos']}"),
        ("commits (all years)", f"{commits:,}"),
        ("pull requests", f"{prs}"),
        ("PRs merged", f"{merged}"),
        ("issues opened", f"{issues}"),
        ("followers", f"{user['followers']}"),
    ]
    return rows, top_langs, total


def card(w, h, title, body):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'font-family="{MONO}">\n'
        f'  <rect width="{w}" height="{h}" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>\n'
        f'  <text x="18" y="30" font-size="12.5" font-weight="600" fill="{BLUE}">{title}</text>\n'
        f'  <line x1="14" y1="42" x2="{w - 14}" y2="42" stroke="{BORDER}"/>\n'
        f"{body}</svg>\n"
    )


def stats_svg(rows):
    body = []
    y = 64
    for label, value in rows:
        body.append(
            f'  <text x="18" y="{y}" font-size="12.5" fill="{MUTED}">{label}</text>\n'
            f'  <text x="482" y="{y}" font-size="12.5" text-anchor="end" fill="{TEXT}">{value}</text>\n'
        )
        y += 26
    h = y - 26 + 18
    return card(500, h, "$ gh api users/" + USER, "".join(body))


def langs_svg(top, total):
    body = []
    y = 62
    for lang, n in top:
        frac = n / total
        body.append(
            f'  <text x="18" y="{y}" font-size="12" fill="{TEXT}">{lang}</text>\n'
            f'  <rect x="150" y="{y - 10}" width="{max(4, round(250 * frac))}" height="10" rx="2" '
            f'fill="{COLORS.get(lang, MUTED)}"/>\n'
            f'  <text x="{150 + max(4, round(250 * frac)) + 10}" y="{y}" font-size="11.5" fill="{MUTED}">'
            f"{frac * 100:.1f}%</text>\n"
        )
        y += 26
    h = y - 26 + 18
    return card(500, h, "$ gh linguist --breakdown", "".join(body))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, top, total = collect()
    with open(os.path.join(OUT_DIR, "stats.svg"), "w") as f:
        f.write(stats_svg(rows))
    with open(os.path.join(OUT_DIR, "languages.svg"), "w") as f:
        f.write(langs_svg(top, total))
    print("stats rows:", rows)
    print("langs:", top)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("GH_TOKEN env var required")
    main()
