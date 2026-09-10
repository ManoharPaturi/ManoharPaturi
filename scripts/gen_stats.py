#!/usr/bin/env python3
"""Generate the profile telemetry SVGs from the GitHub API.

Design language: "signal lab" — a phosphor oscilloscope bench. Everything on the
profile (hero, readout panes, language spectrum, 52-week trace) is rendered here
so the numbers are recomputed live on every nightly run.

Runs locally (GH_TOKEN env) and inside .github/workflows/stats.yml.
Uses only the stdlib so no pip install is needed anywhere.
"""
import json
import math
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

USER = "ManoharPaturi"
# repos whose language stats are generated output (Plotly report bundles), not hand-written code
EXCLUDE_REPOS = {"mocap_mac"}
# alt/peer accounts excluded from the external-PR headline numbers
EXT_EXCLUDE = f"-user:{USER} -user:Pushpak731 -user:bodapatisaikrishna -user:init-club"
TOKEN = os.environ.get("GH_TOKEN")
API = "https://api.github.com"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

# --- signal-lab palette -------------------------------------------------------
BG = "#0A0E12"        # bezel black
PANEL = "#0D1418"     # screen panel
GRID = "#16231F"      # graticule etching
BORDER = "#1E3530"    # bezel edge
TRACE = "#2DE0A5"     # phosphor green
CYAN = "#3AC8E0"      # channel cyan
VIOLET = "#A371F7"    # decision violet
AMBER = "#FFB454"     # status amber
TEXT = "#E6F2EC"      # bright readout
MUTED = "#7E948C"     # dim readout
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


def latest_pr():
    result = call(
        f"{API}/search/issues?per_page=1&sort=updated&order=desc"
        f"&q={quote(f'is:pr author:{USER}')}"
    )
    item = result["items"][0]
    repo = item["repository_url"].rsplit("repos/", 1)[1]
    return repo, item["number"]


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

    # external (upstream) numbers for the hero readouts
    ext_q = f"is:pr author:{USER} {EXT_EXCLUDE}"
    prs_ext = search_count(ext_q)
    merged_ext = search_count(ext_q + " is:merged")
    # single page is fine at current volume; revisit if external PRs exceed 100
    ext_items = call(f"{API}/search/issues?per_page=100&q={quote(ext_q)}")["items"]
    labs = {i["repository_url"].rsplit("repos/", 1)[1].split("/")[0] for i in ext_items}

    week_cutoff = (now - timedelta(days=7)).date().isoformat()
    week_contributions = sum(
        day["contributionCount"]
        for week in cal["weeks"]
        for day in week["contributionDays"]
        if day["date"] >= week_cutoff
    )

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
    live = {
        "review": latest_pr(),
        "week": week_contributions,
        "systems": user["public_repos"],
        "merged": merged,
        "updated": now.strftime("%Y-%m-%d %H:%M UTC"),
    }
    hero = {
        "signals": prs_ext,
        "labs": len(labs),
        "accepted": merged_ext,
    }
    return rows, top_langs, total, cal, live, hero


# --- shared svg fragments ------------------------------------------------------

def svg_open(w, h, rx=12):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
        f'font-family="{MONO}">\n'
        f'<defs><filter id="glow" x="-30%" y="-30%" width="160%" height="160%">'
        f'<feGaussianBlur stdDeviation="2.4" result="b"/>'
        f"<feMerge><feMergeNode in=\"b\"/><feMergeNode in=\"SourceGraphic\"/></feMerge></filter></defs>\n"
    )


def graticule(x0, y0, w, h, cols, rows, clip=None):
    out = [f'<g {"clip-path=" + chr(34) + "url(#" + clip + ")" + chr(34) + " " if clip else ""}'
           f'stroke="{GRID}" stroke-width="1">']
    for i in range(1, cols):
        x = round(x0 + w * i / cols)
        out.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y0 + h}"/>')
    for j in range(1, rows):
        y = round(y0 + h * j / rows)
        out.append(f'<line x1="{x0}" y1="{y}" x2="{x0 + w}" y2="{y}"/>')
    out.append("</g>")
    return "\n".join(out) + "\n"


def poly_path(pts, x0, y0):
    d = f"M {round(x0 + pts[0][0])},{round(y0 + pts[0][1])}"
    for x, y in pts[1:]:
        d += f" L {round(x0 + x)},{round(y0 + y)}"
    return d


def _frac(x):
    return (math.sin(x * 12.9898) * 43758.5453) % 1.0


# --- hero ----------------------------------------------------------------------

def hero_svg(counts):
    W, H = 828, 348
    wx, wy, ww, wh = 24, 126, 780, 148
    mid = wh / 2
    body = [svg_open(W, H, rx=14)]

    # bezel + top bar
    body.append(f'<rect width="{W}" height="{H}" rx="14" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>')
    body.append(f'<line x1="0" y1="46" x2="{W}" y2="46" stroke="{BORDER}"/>')
    body.append(f'<circle cx="30" cy="27" r="5" fill="{AMBER}"/>')
    body.append(f'<text x="42" y="31" font-size="11" letter-spacing="1" fill="{AMBER}">REC</text>')
    body.append(f'<text x="96" y="31" font-size="13" font-weight="700" letter-spacing="3" fill="{TRACE}">M.PATURI · SIGNAL LAB</text>')
    body.append(f'<text x="{W - 24}" y="31" font-size="11" text-anchor="end" fill="{MUTED}">self-hosted telemetry</text>')

    # name plate
    body.append(f'<text x="26" y="90" font-size="26" font-weight="700" letter-spacing="1" fill="{TEXT}">MANOHAR PATURI</text>')
    body.append(
        f'<text x="26" y="113" font-size="12" fill="{MUTED}">'
        f"AI engineering undergrad @ Amrita Vishwa Vidyapeetham — RL · EEG/biosignals · motion capture · Flutter</text>"
    )

    # scope window
    body.append(f'<rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" rx="6" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(
        f'<clipPath id="cw"><rect x="{wx}" y="{wy}" width="{ww}" height="{wh}" rx="6"/></clipPath>'
    )
    body.append(graticule(wx, wy, ww, wh, 10, 4, clip="cw"))

    def wave(fn, color, width, glow=True):
        pts = [(x, mid + fn(x)) for x in range(0, ww + 1, 3)]
        g = ' filter="url(#glow)"' if glow else ""
        return f'<path d="{poly_path(pts, wx, wy)}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linejoin="round"{g} clip-path="url(#cw)"/>'

    # ch2 decision: ascending staircase reward curve
    def decision(x):
        return 40 - min(80, math.floor(x / 58) * 6.5)

    # ch1 motion: smooth gait
    def motion(x):
        return 26 * math.sin(x * 2 * math.pi / 240) + 7 * math.sin(x * 2 * math.pi / 83 + 1.3)

    # ch3 biosignal: low-amp noise with recurring spikes
    def biosignal(x):
        y = 10 * math.sin(x * 2 * math.pi / 61) + 6 * math.sin(x * 2 * math.pi / 23.7)
        y += (_frac(x) - 0.5) * 14
        for k in range(9):
            sx = 40 + k * 88
            if abs(x - sx) < 6:
                y += (6 - abs(x - sx)) * 4.5
        return y

    body.append(wave(decision, VIOLET, 1.6, glow=False))
    body.append(wave(motion, CYAN, 1.6, glow=False))
    body.append(wave(biosignal, TRACE, 2.2, glow=True))

    # legend inside window, bottom-left
    ly = wy + wh - 14
    for i, (c, lab) in enumerate([(TRACE, "ch3 biosignal"), (CYAN, "ch1 motion"), (VIOLET, "ch2 decision")]):
        cx = 38 + i * 118
        body.append(f'<circle cx="{cx}" cy="{ly - 4}" r="3.5" fill="{c}"/>')
        body.append(f'<text x="{cx + 9}" y="{ly}" font-size="9.5" fill="{MUTED}">{lab}</text>')

    # readout strip
    groups = [("signals sent", f"{counts['signals']}"), ("labs pinged", f"{counts['labs']}"), ("accepted", f"{counts['accepted']}")]
    for i, (lab, val) in enumerate(groups):
        x = 24 + i * 168
        body.append(f'<text x="{x}" y="302" font-size="9.5" letter-spacing="1.5" fill="{MUTED}">{lab.upper()}</text>')
        body.append(f'<text x="{x}" y="326" font-size="19" font-weight="700" fill="{TRACE}">{val}</text>')
    body.append(f'<text x="{W - 24}" y="326" font-size="11" text-anchor="end" fill="{MUTED}">probe: github.com/{USER}</text>')

    body.append("</svg>\n")
    return "".join(body)


# --- instrument readout pane ----------------------------------------------------

def stats_svg(rows):
    body = [svg_open(500, 280)]
    body.append(f'<rect width="500" height="280" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>')
    body.append(f'<text x="18" y="30" font-size="12.5" font-weight="700" letter-spacing="2" fill="{TRACE}">INSTRUMENT READOUT</text>')
    body.append(f'<line x1="14" y1="42" x2="486" y2="42" stroke="{BORDER}"/>')
    y = 68
    for label, value in rows:
        body.append(f'<text x="18" y="{y}" font-size="12.5" fill="{MUTED}">▸ {label}</text>')
        body.append(f'<text x="482" y="{y}" font-size="12.5" font-weight="600" text-anchor="end" fill="{TEXT}">{value}</text>')
        y += 26
    body.append("</svg>\n")
    return "".join(body)


# --- language spectrum pane ------------------------------------------------------

def langs_svg(top, total):
    body = [svg_open(500, 280)]
    body.append(f'<rect width="500" height="280" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>')
    body.append(f'<text x="18" y="30" font-size="12.5" font-weight="700" letter-spacing="2" fill="{TRACE}">SIGNAL SPECTRUM</text>')
    body.append(f'<line x1="14" y1="42" x2="486" y2="42" stroke="{BORDER}"/>')
    y = 68
    for lang, n in top:
        frac = n / total
        bw = max(4, round(250 * frac))
        body.append(f'<text x="18" y="{y}" font-size="12" fill="{TEXT}">{lang}</text>')
        body.append(f'<rect x="150" y="{y - 10}" width="{bw}" height="10" rx="2" fill="{COLORS.get(lang, MUTED)}"/>')
        body.append(f'<text x="{150 + bw + 10}" y="{y}" font-size="11.5" fill="{MUTED}">{frac * 100:.1f}%</text>')
        y += 26
    body.append("</svg>\n")
    return "".join(body)


# --- live probe pane ---------------------------------------------------------------

def now_svg(live):
    repo, number = live["review"]
    rows = [
        ("latest review", f"{repo.split('/')[-1]} #{number}"),
        ("7-day signal", f"{live['week']} contributions"),
        ("merged upstream", f"{live['merged']} PRs"),
        ("public systems", f"{live['systems']}"),
    ]
    body = [svg_open(360, 240)]
    body.append(f'<rect width="360" height="240" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>')
    body.append(f'<circle cx="26" cy="26" r="4" fill="{TRACE}"/>')
    body.append(f'<text x="38" y="30" font-size="12.5" font-weight="700" letter-spacing="2" fill="{TRACE}">LIVE PROBE</text>')
    body.append(f'<line x1="14" y1="42" x2="346" y2="42" stroke="{BORDER}"/>')
    y = 70
    for label, value in rows:
        body.append(f'<text x="18" y="{y}" font-size="13" fill="{MUTED}">{label}</text>')
        body.append(f'<text x="342" y="{y}" font-size="13" font-weight="600" text-anchor="end" fill="{TEXT}">{value}</text>')
        y += 32
    body.append(f'<text x="18" y="224" font-size="10" fill="{MUTED}">sampled {live["updated"]}</text>')
    body.append("</svg>\n")
    return "".join(body)


# --- 52-week signal trace ------------------------------------------------------------

def trace_svg(cal):
    days = [d for week in cal["weeks"] for d in week["contributionDays"]]
    days = days[-364:] if len(days) > 364 else days
    total = sum(d["contributionCount"] for d in days)
    peak = max((d["contributionCount"] for d in days), default=1) or 1

    # streaks — longest run anywhere in the window; current run counts back from
    # the most recent active day (an unfinished today with 0 shouldn't break it)
    longest = run = 0
    prev = None
    for d in days:
        if d["contributionCount"] > 0:
            run = run + 1 if prev is not None and (datetime.fromisoformat(d["date"]) - datetime.fromisoformat(prev)).days == 1 else 1
            longest = max(longest, run)
            prev = d["date"]
        else:
            run, prev = 0, None

    W, H = 828, 196
    x0, y0, w, h = 18, 44, 792, 126
    base = y0 + h
    body = [svg_open(W, H)]

    body.append(f'<rect width="{W}" height="{H}" rx="12" fill="{BG}" stroke="{BORDER}" stroke-width="1.5"/>')
    body.append(f'<text x="18" y="28" font-size="12.5" font-weight="700" letter-spacing="2" fill="{TRACE}">52-WEEK SIGNAL TRACE</text>')
    body.append(
        f'<text x="{W - 18}" y="28" font-size="11" text-anchor="end" fill="{MUTED}">'
        f"{total:,} contributions · peak day {peak} · longest streak {longest}d</text>"
    )

    body.append(f'<rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6" fill="{PANEL}" stroke="{BORDER}"/>')
    body.append(f'<clipPath id="tw"><rect x="{x0}" y="{y0}" width="{w}" height="{h}" rx="6"/></clipPath>')
    body.append(graticule(x0, y0, w, h, 12, 4, clip="tw"))

    pts = []
    n = len(days)
    for i, d in enumerate(days):
        x = w * i / max(1, n - 1)
        # sqrt scale so quiet days still register on the scope
        y = h - (math.sqrt(d["contributionCount"]) / math.sqrt(peak)) * (h - 10)
        pts.append((x, y))
    line = poly_path(pts, x0, y0)
    area = line + f" L {x0 + w},{base} L {x0},{base} Z"

    body.append(f'<path d="{area}" fill="{TRACE}" opacity="0.13" clip-path="url(#tw)"/>')
    body.append(f'<path d="{line}" fill="none" stroke="{TRACE}" stroke-width="2" filter="url(#glow)" clip-path="url(#tw)"/>')

    body.append(f'<text x="{x0}" y="{H - 10}" font-size="9.5" fill="{MUTED}">52 wks ago</text>')
    body.append(f'<text x="{x0 + w}" y="{H - 10}" font-size="9.5" text-anchor="end" fill="{MUTED}">today</text>')
    body.append("</svg>\n")
    return "".join(body)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, top, total, cal, live, hero = collect()
    for name, svg in [
        ("scope-hero.svg", hero_svg(hero)),
        ("stats.svg", stats_svg(rows)),
        ("languages.svg", langs_svg(top, total)),
        ("now.svg", now_svg(live)),
        ("trace.svg", trace_svg(cal)),
    ]:
        with open(os.path.join(OUT_DIR, name), "w") as f:
            f.write(svg)
    print("hero readouts:", hero)
    print("stats rows:", rows)
    print("langs:", top)
    print(f"contributions (12 mo): {cal['totalContributions']:,}")
    print("live probe:", live)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("GH_TOKEN env var required")
    main()
