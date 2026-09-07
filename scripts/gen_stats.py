#!/usr/bin/env python3
"""Generate assets/stats.svg, assets/languages.svg, assets/heatmap.svg from the GitHub API.

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

HEAT_LEVELS = ["#161B22", "#0E4429", "#006D32", "#26A641", "#39D353"]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


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
    gql = (
        f'query {{ user(login: "{USER}") {{ {parts} '
        'contributionsCollection { contributionCalendar { totalContributions '
        "weeks { contributionDays { date contributionCount } } } } } }"
    )
    res = call(f"{API}/graphql", gql=gql)
    node = res["data"]["user"]
    commits = sum(node[f"y{y}"]["totalCommitContributions"] for y in range(first_year, now.year + 1))
    cal = node["contributionsCollection"]["contributionCalendar"]

    stars = sum(r["stargazers_count"] for r in repos if not r["fork"])
    prs = search_count(f"is:pr author:{USER}")
    merged = search_count(f"is:pr author:{USER} is:merged")
    issues = search_count(f"is:issue author:{USER}")

    rows = [
        ("total stars", f"{stars:,}"),
        ("public repos", f"{user['public_repos']}"),
        ("commits (all years)", f"{commits:,}"),
        ("contributions (12 mo)", f"{cal['totalContributions']:,}"),
        ("pull requests", f"{prs}"),
        ("PRs merged", f"{merged}"),
        ("issues opened", f"{issues}"),
        ("followers", f"{user['followers']}"),
    ]
    return rows, top_langs, total, cal


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


def heatmap_svg(cal):
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    max_count = max((d["contributionCount"] for w in weeks for d in w), default=1) or 1

    def level(c):
        if c == 0:
            return 0
        if c <= max_count * 0.25:
            return 1
        if c <= max_count * 0.5:
            return 2
        if c <= max_count * 0.75:
            return 3
        return 4

    flat = [d for w in weeks for d in w]
    longest = cur = 0
    for d in flat:
        cur = cur + 1 if d["contributionCount"] else 0
        longest = max(longest, cur)
    scan = flat[:-1] if flat and flat[-1]["contributionCount"] == 0 else flat
    cur_streak = 0
    for d in reversed(scan):
        if d["contributionCount"]:
            cur_streak += 1
        else:
            break

    body = []
    # month labels (place a label wherever the month changes)
    prev_m = None
    for i, w in enumerate(weeks):
        m = int(w[0]["date"][5:7])
        if i and m != prev_m:
            body.append(
                f'  <text x="{28 + i * 13}" y="46" font-size="9.5" fill="{MUTED}">{MONTHS[m - 1]}</text>\n'
            )
        prev_m = m
    # day labels: Mon / Wed / Fri (rows 1 / 3 / 5, grid rows are Sun..Sat)
    for row, lab in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        body.append(
            f'  <text x="24" y="{61 + row * 13}" font-size="9.5" text-anchor="end" fill="{MUTED}">{lab}</text>\n'
        )
    # cells
    for i, w in enumerate(weeks):
        for j, d in enumerate(w):
            body.append(
                f'  <rect x="{28 + i * 13}" y="{52 + j * 13}" width="11" height="11" rx="2.5" '
                f'fill="{HEAT_LEVELS[level(d["contributionCount"])]}"/>\n'
            )
    # footer: totals left, legend right
    total = cal["totalContributions"]
    body.append(
        f'  <text x="18" y="168" font-size="11" fill="{TEXT}">{total:,} contributions</text>\n'
        f'  <text x="150" y="168" font-size="11" fill="{MUTED}">current streak {cur_streak}d</text>\n'
        f'  <text x="290" y="168" font-size="11" fill="{MUTED}">longest {longest}d</text>\n'
    )
    lx = 470
    body.append(f'  <text x="{lx}" y="168" font-size="9.5" fill="{MUTED}">less</text>\n')
    for k, c in enumerate(HEAT_LEVELS):
        body.append(f'  <rect x="{lx + 30 + k * 13}" y="159" width="10" height="10" rx="2" fill="{c}"/>\n')
    body.append(f'  <text x="{lx + 30 + 5 * 13 + 4}" y="168" font-size="9.5" fill="{MUTED}">more</text>\n')

    w = 28 + len(weeks) * 13 + 12
    h = 182
    return card(w, h, "$ git log --since=1y --pretty=contributions", "".join(body))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, top, total, cal = collect()
    with open(os.path.join(OUT_DIR, "stats.svg"), "w") as f:
        f.write(stats_svg(rows))
    with open(os.path.join(OUT_DIR, "languages.svg"), "w") as f:
        f.write(langs_svg(top, total))
    with open(os.path.join(OUT_DIR, "heatmap.svg"), "w") as f:
        f.write(heatmap_svg(cal))
    print("stats rows:", rows)
    print("langs:", top)
    print(f"heatmap: {cal['totalContributions']} contributions, {len(cal['weeks'])} weeks")


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("GH_TOKEN env var required")
    main()
