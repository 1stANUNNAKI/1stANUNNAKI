"""Automated telemetry and live card cache-busting synchronization for 1stANUNNAKI profile README."""
import json
import os
import re
import time
import urllib.request
from pathlib import Path

USERNAME = "1stANUNNAKI"
README_PATH = Path(__file__).resolve().parents[2] / "README.md"


def fetch_json(url: str, method: str = "GET", payload: dict | None = None) -> object:
    headers = {"User-Agent": "1stANUNNAKI-Profile-Sync/2.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_graphql_contributions() -> int:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return 0
    query = (
        'query { user(login: "' + USERNAME + '") { '
        'contributionsCollection { contributionCalendar { totalContributions } } } }'
    )
    try:
        res = fetch_json("https://api.github.com/graphql", method="POST", payload={"query": query})
        return int(
            res.get("data", {})
            .get("user", {})
            .get("contributionsCollection", {})
            .get("contributionCalendar", {})
            .get("totalContributions", 0)
        )
    except Exception:
        return 0


def fetch_account_metrics() -> dict:
    ts = int(time.time())
    user_data = fetch_json(f"https://api.github.com/users/{USERNAME}")
    repos_data = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
    streak_data = fetch_json(f"https://streak-stats.demolab.com?user={USERNAME}&type=json&v={ts}")
    gql_contribs = fetch_graphql_contributions()
    streak_contribs = int(streak_data.get("totalContributions", 46))
    stars = sum(int(r.get("stargazers_count", 0)) for r in repos_data if isinstance(r, dict))
    return {
        "repos": int(user_data.get("public_repos", 8)),
        "stars": stars,
        "contributions": max(gql_contribs, streak_contribs),
        "streak": int(streak_data.get("longestStreak", {}).get("length", 3)),
        "followers": int(user_data.get("followers", 17)),
        "v": ts,
    }


def build_summary_line(metrics: dict) -> str:
    return (
        f'<p align="center"><b>{metrics["repos"]}</b> public repositories, '
        f'<b>{metrics["stars"]}</b> stars, '
        f'<b>{metrics["contributions"]}</b> contributions in the last year, '
        f'a longest streak of <b>{metrics["streak"]}</b> days and '
        f'<b>{metrics["followers"]}</b> followers.</p>'
    )


def refresh_card_urls(content: str, v: int) -> str:
    """Appends or updates &cache_seconds=1800&v=<timestamp> on stats and streak cards to bust Camo cache."""
    def _update_url(match: re.Match) -> str:
        prefix = match.group(1)
        url = match.group(2)
        suffix = match.group(3)
        url = re.sub(r"&cache_seconds=\d+", "", url)
        url = re.sub(r"&v=[\w-]+", "", url)
        return f'{prefix}{url}&cache_seconds=1800&v={v}{suffix}'

    card_pattern = re.compile(
        r'(<img[^>]+src=")(https://(?:github-readme-stats-eight-theta\.vercel\.app|streak-stats\.demolab\.com|github-trophies\.vercel\.app)[^"]+)(")'
    )
    return card_pattern.sub(_update_url, content)


def update_readme() -> bool:
    if not README_PATH.exists():
        return False
    metrics = fetch_account_metrics()
    content = README_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r'<p align="center"><b>\d+</b> public repositories, <b>\d+</b> stars, '
        r'<b>\d+</b> contributions in the last year, a longest streak of '
        r'<b>\d+</b> days and <b>\d+</b> followers\.</p>'
    )
    updated = pattern.sub(build_summary_line(metrics), content)
    updated = refresh_card_urls(updated, metrics["v"])
    if updated == content:
        return False
    README_PATH.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    changed = update_readme()
    print(f"README telemetry updated: {changed}")

