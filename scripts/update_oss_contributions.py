#!/usr/bin/env python3
"""Recompute merged upstream PR counts and refresh the README section.

Counts pull requests authored by the configured GitHub account that were
merged into approved upstream organizations within a rolling 12-month
window, then rewrites only the content between the OSS_CONTRIBUTIONS
markers in README.md. Everything outside the markers is never touched.

Fail-safe guarantees:
  * API errors, rate limits, and incomplete search results abort the run
    before anything is written.
  * A valid existing table is never replaced by zeros.
  * Unchanged counts leave README.md byte-for-byte untouched, so the
    workflow produces no commit.

Approved organizations are listed explicitly in oss_contributions.json.
A merged PR in an unlisted repository is logged as a candidate and
excluded until the configuration is updated by a human.

Usage:
    python3 scripts/update_oss_contributions.py [--dry-run]
        [--config scripts/oss_contributions.json] [--readme README.md]

Authentication: GITHUB_TOKEN or GH_TOKEN environment variable; falls back
to `gh auth token` for local runs. No third-party dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / "scripts" / "oss_contributions.json"
DEFAULT_README = REPO_ROOT / "README.md"
API_BASE = "https://api.github.com"
PER_PAGE = 100
SEARCH_HARD_LIMIT = 1000  # GitHub Search API never returns more results than this
MAX_PAGES = SEARCH_HARD_LIMIT // PER_PAGE
HTTP_TIMEOUT = 30
MAX_RETRIES = 3


class ApiError(RuntimeError):
    """The GitHub API failed in a way we must not paper over."""


class RateLimitError(ApiError):
    pass


# ---------------------------------------------------------------- GitHub API


def github_token() -> str:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    try:
        out = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True, timeout=15
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    raise ApiError("No GitHub token: set GITHUB_TOKEN (or authenticate gh)")


def api_get(url: str, token: str) -> dict:
    """GET one URL, retrying transient failures, aborting on rate limits."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "oss-contributions-updater",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    last_err: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
                remaining = resp.headers.get("X-RateLimit-Remaining")
                if remaining == "0":
                    raise RateLimitError(f"Rate limit exhausted requesting {url}")
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            if err.code == 403 and err.headers.get("X-RateLimit-Remaining") == "0":
                raise RateLimitError(f"Rate limit exhausted requesting {url}") from err
            if err.code == 403 and "retry-after" in {k.lower() for k in err.headers}:
                wait = int(err.headers.get("retry-after", "30"))
                last_err = ApiError(f"Secondary rate limit on {url}")
                time.sleep(min(wait, 60))
                continue
            if err.code in (401, 404, 422):
                raise ApiError(f"HTTP {err.code} for {url}: {err.read()[:300]}") from err
            if err.code >= 500:
                last_err = err
            else:
                raise ApiError(f"HTTP {err.code} for {url}") from err
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            last_err = err
        if attempt < MAX_RETRIES:
            time.sleep(2 * attempt)
    raise ApiError(f"GET {url} failed after {MAX_RETRIES} attempts: {last_err}")


def search_prs(query: str, token: str) -> tuple[list[dict], bool]:
    """Run one search query with full pagination.

    Returns (items, complete). complete is False when GitHub reported
    incomplete results twice, which the caller must treat as a failure.
    """
    items: list[dict] = []
    for page in range(1, MAX_PAGES + 1):
        qs = urllib.parse.urlencode(
            {"q": query, "per_page": PER_PAGE, "page": page}
        )
        data = api_get(f"{API_BASE}/search/issues?{qs}", token)
        if data.get("incomplete_results"):
            # Transient some of the time; retry the page once before giving up.
            data = api_get(f"{API_BASE}/search/issues?{qs}", token)
            if data.get("incomplete_results"):
                raise ApiError(
                    "GitHub reported incomplete search results; refusing to "
                    "write counts from partial data"
                )
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < PER_PAGE or len(items) >= data.get("total_count", 0):
            break
    return items, True


def search_merged_prs(
    query: str, token: str, since: date, until: date
) -> list[dict]:
    """Search merged PRs, partitioning the date window if results overflow
    the Search API's hard limit (requirement: account for the 1000 cap)."""
    scoped = f"{query} merged:{since.isoformat()}..{until.isoformat()}"
    items, _ = search_prs(scoped, token)
    if len(items) < SEARCH_HARD_LIMIT:
        return items
    if (until - since).days <= 1:
        raise ApiError(
            f"More than {SEARCH_HARD_LIMIT} merged PRs within a single day; "
            "cannot partition further"
        )
    mid = since + (until - since) / 2
    left = search_merged_prs(query, token, since, mid)
    right = search_merged_prs(query, token, mid + timedelta(days=1), until)
    seen, merged = set(), []
    for item in left + right:
        url = item.get("html_url")
        if url and url not in seen:
            seen.add(url)
            merged.append(item)
    return merged


def verify_pr(repo_full_name: str, number: int, token: str) -> dict:
    """Fetch the pull request to confirm merged status, merge date, owner,
    and that the repository is not a fork of something else."""
    data = api_get(f"{API_BASE}/repos/{repo_full_name}/pulls/{number}", token)
    base = data.get("base") or {}
    repo = base.get("repo") or {}
    return {
        "merged": bool(data.get("merged")),
        "merged_at": data.get("merged_at"),
        "html_url": data.get("html_url"),
        "owner": (repo.get("owner") or {}).get("login", ""),
        "full_name": repo.get("full_name", repo_full_name),
        "fork": bool(repo.get("fork")),
    }


# ------------------------------------------------------------- window logic


def subtract_months(day: date, months: int) -> date:
    """Rolling calendar window: 2026-10-29 minus 12 months is 2025-10-29."""
    month_index = day.month - 1 - months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
                else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1]
    return date(year, month, min(day.day, last_day))


# ------------------------------------------------------------- aggregation


def collect_counts(cfg: dict, token: str) -> tuple[dict[str, int], list[str]]:
    author = cfg["author"]
    cutoff = subtract_months(datetime.now(timezone.utc).date(),
                             cfg["rolling_window_months"])
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)
    print(f"Window: merged {cutoff.isoformat()} .. {tomorrow.isoformat()}")

    owner_to_display = {
        o.lower(): g["display"]
        for g in cfg["groups"]
        for o in g.get("owners", [])
    }
    excluded_owners = {o.lower() for o in cfg.get("exclude_owners", [])}
    excluded_repos = {r.lower() for r in cfg.get("exclude_repos", [])}
    repo_quals = " ".join(f"-user:{o}" for o in cfg.get("exclude_owners", []))
    base_query = f"is:pr is:merged author:{author} {repo_quals}".strip()

    counts: dict[str, int] = {g["display"]: 0 for g in cfg["groups"]}
    unapproved: dict[str, int] = {}
    dedupe: set[tuple[str, int]] = set()

    for group in cfg["groups"]:
        owners = group.get("owners", [])
        owner_quals = " ".join(f"user:{o}" for o in owners)
        query = f"{base_query} {owner_quals}".strip()
        candidates = search_merged_prs(query, token, cutoff, tomorrow)
        for item in candidates:
            repo_url = item.get("repository_url", "")
            match = re.search(r"/repos/([^/]+/[^/]+)$", repo_url)
            if not match:
                continue
            full_name = match.group(1)
            number = item.get("number")
            key = (full_name.lower(), number)
            if key in dedupe:
                continue
            dedupe.add(key)

            verified = verify_pr(full_name, number, token)
            # Requirements: count only merged PRs in the window, never from
            # forks, never from owned/affiliated accounts, grouped by the
            # repository's actual owner.
            if not verified["merged"] or not verified["merged_at"]:
                continue
            merged_on = datetime.fromisoformat(
                verified["merged_at"].replace("Z", "+00:00")
            ).date()
            if merged_on < cutoff or merged_on >= tomorrow:
                continue
            if verified["fork"]:
                continue
            owner = verified["owner"].lower()
            full = verified["full_name"].lower()
            if owner in excluded_owners or full in excluded_repos:
                continue
            display = owner_to_display.get(owner)
            if display is None:
                unapproved[owner] = unapproved.get(owner, 0) + 1
                continue
            counts[display] += 1

    return counts, sorted(unapproved.items())


def build_table(cfg: dict, counts: dict[str, int]) -> str:
    author = cfg["author"]
    total = sum(counts.values())
    lines = [
        "| Organization | Merged PRs |",
        "| --- | --: |",
    ]
    rows = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))
    for display, count in rows:
        group = next(g for g in cfg["groups"] if g["display"] == display)
        query = f"is:pr is:merged author:{author} " + " ".join(
            f"user:{o}" for o in group.get("owners", [])
        )
        url = "https://github.com/search?" + urllib.parse.urlencode(
            {"q": query.strip(), "type": "pullrequests"}
        )
        lines.append(f"| [{display}]({url}) | {count} |")
    lines.append(f"| **Total** | **{total}** |")
    return "\n".join(lines)


# ------------------------------------------------------------- README splice


def read_section(readme: Path, start: str, end: str) -> str | None:
    text = readme.read_text(encoding="utf-8")
    if start not in text or end not in text:
        return None
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def write_section(readme: Path, start: str, end: str, body: str) -> None:
    text = readme.read_text(encoding="utf-8")
    if start not in text or end not in text:
        raise SystemExit(
            f"{readme}: markers not found; add '{start}' and '{end}' around "
            "the contribution table once, then rerun"
        )
    before = text.split(start, 1)[0]
    after = text.split(end, 1)[1]
    updated = f"{before}{start}\n{body}\n{end}{after}"
    if updated != text:
        readme.write_text(updated, encoding="utf-8")


# --------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--readme", type=Path, default=DEFAULT_README)
    parser.add_argument("--dry-run", action="store_true",
                        help="print the computed table; write nothing")
    args = parser.parse_args()

    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    for key in ("author", "rolling_window_months", "section_markers",
                "groups"):
        if key not in cfg:
            raise SystemExit(f"config missing required key: {key}")

    token = github_token()
    counts, unapproved = collect_counts(cfg, token)
    total = sum(counts.values())
    print(f"\nComputed counts (total {total}):")
    for display, count in sorted(counts.items(),
                                 key=lambda kv: (-kv[1], kv[0].lower())):
        print(f"  {display:<20} {count}")
    if unapproved:
        print(
            "\nWARNING: merged PRs in organizations that are NOT in the "
            "approved config; they are excluded until you approve them:",
            file=sys.stderr,
        )
        for owner, n in unapproved:
            print(f"  {owner}: {n} merged", file=sys.stderr)

    body = build_table(cfg, counts)
    start = cfg["section_markers"]["start"]
    end = cfg["section_markers"]["end"]

    if args.dry_run:
        print(f"\n--- generated section ---\n{body}")
        return 0

    existing = read_section(args.readme, start, end)
    if existing is None:
        raise SystemExit(
            f"{args.readme}: markers '{start}' / '{end}' not found"
        )

    # Never overwrite valid counts with zeros because an API call came back
    # empty; treat that as a failure so the workflow leaves the file alone.
    if total == 0 and existing.strip():
        raise SystemExit(
            "computed total is 0 but the README already shows nonzero "
            "counts; refusing to write (likely an API failure or a config "
            "mistake)"
        )

    # The block is deterministic from the counts (no timestamps inside), so
    # an exact match means the file would not change and no commit is needed.
    if existing.strip() == body.strip():
        print("\nCounts unchanged; README left untouched (no commit needed).")
        return 0

    write_section(args.readme, start, end, body)
    print(f"\nUpdated the generated section in {args.readme}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
