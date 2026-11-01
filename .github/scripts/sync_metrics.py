"""Automated telemetry synchronization for 1stANUNNAKI profile README."""
import json
import os
import re
import urllib.request
from pathlib import Path

USERNAME = "1stANUNNAKI"
README_PATH = Path(__file__).resolve().parents[2] / "README.md"


def fetch_json(url: str) -> object:
    headers = {"User-Agent": "1stANUNNAKI-Profile-Sync/1.0"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_account_metrics() -> dict:
    user_data = fetch_json(f"https://api.github.com/users/{USERNAME}")
    repos_data = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
    streak_data = fetch_json(f"https://streak-stats.demolab.com?user={USERNAME}&type=json")
    stars = sum(int(r.get("stargazers_count", 0)) for r in repos_data if isinstance(r, dict))
    return {
        "repos": int(user_data.get("public_repos", 8)),
        "stars": stars,
        "contributions": int(streak_data.get("totalContributions", 46)),
        "streak": int(streak_data.get("longestStreak", {}).get("length", 3)),
        "followers": int(user_data.get("followers", 17)),
    }


def build_summary_line(metrics: dict) -> str:
    return (
        f'<p align="center"><b>{metrics["repos"]}</b> public repositories, '
        f'<b>{metrics["stars"]}</b> stars, '
        f'<b>{metrics["contributions"]}</b> contributions in the last year, '
        f'a longest streak of <b>{metrics["streak"]}</b> days and '
        f'<b>{metrics["followers"]}</b> followers.</p>'
    )


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
    if updated == content:
        return False
    README_PATH.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    changed = update_readme()
    print(f"README telemetry updated: {changed}")

# Telemetry revision: 10 (streak-parser-validation)
