"""Automated telemetry and live SVG card synchronization for 1stANUNNAKI profile README."""
import json
import os
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USERNAME = "1stANUNNAKI"
REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
STREAK_SVG_PATH = REPO_ROOT / "streak-stats.svg"
TROPHIES_SVG_PATH = REPO_ROOT / "trophies.svg"

# Exact REPO GALAXY (theme=midnight) Color Palette
GALAXY_BG = "#060b1e"
GALAXY_BORDER = "#5b5c8a"
GALAXY_TITLE = "#8087e2"
GALAXY_TEXT = "#dee7f0"
GALAXY_SUBTEXT = "#9098bf"
GALAXY_GOLD = "#facc15"


def fmt_date(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return dt.strftime("%b %d").replace(" 0", " ")
    except Exception:
        return date_str


def fetch_json(url: str, method: str = "GET", payload: dict | None = None, extra_headers: dict | None = None) -> dict:
    headers = {"User-Agent": "1stANUNNAKI-Profile-Sync/4.0", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token and "api.github.com" in url:
        headers["Authorization"] = f"Bearer {token}"
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "1stANUNNAKI-Profile-Sync/4.0"})
    with urllib.request.urlopen(req, timeout=25) as resp:
        return resp.read().decode("utf-8")


def fetch_live_contributions_and_streaks() -> dict:
    ts = int(time.time())
    streak_len = 4
    curr_len = 4
    curr_range = "Oct 30 - Nov 2"
    long_range = "Oct 30 - Nov 2"
    streak_contribs = 2164
    try:
        s_data = fetch_json(f"https://streak-stats.demolab.com?user={USERNAME}&type=json&v={ts}")
        streak_contribs = int(s_data.get("totalContributions", 2164))
        cs = s_data.get("currentStreak", {})
        ls = s_data.get("longestStreak", {})
        curr_len = int(cs.get("length", 4))
        streak_len = max(int(ls.get("length", 4)), curr_len)
        if cs.get("start") and cs.get("end"):
            curr_range = f"{fmt_date(cs['start'])} - {fmt_date(cs['end'])}"
        if ls.get("start") and ls.get("end"):
            long_range = f"{fmt_date(ls['start'])} - {fmt_date(ls['end'])}"
    except Exception:
        pass

    gql_calendar = 0
    gql_prs = 0
    gql_commits = 0
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        query = (
            'query { user(login: "' + USERNAME + '") { '
            'contributionsCollection { '
            'totalCommitContributions totalPullRequestContributions totalIssueContributions '
            'contributionCalendar { totalContributions weeks { contributionDays { contributionCount date } } } } '
            'pullRequests { totalCount } } }'
        )
        try:
            res = fetch_json("https://api.github.com/graphql", method="POST", payload={"query": query})
            user_node = res.get("data", {}).get("user", {})
            cc = user_node.get("contributionsCollection", {})
            cal = cc.get("contributionCalendar", {})
            gql_calendar = int(cal.get("totalContributions", 0))
            gql_commits = int(cc.get("totalCommitContributions", 0))
            gql_prs = max(
                int(cc.get("totalPullRequestContributions", 0)),
                int(user_node.get("pullRequests", {}).get("totalCount", 0)),
            )
            days = [
                d for w in cal.get("weeks", []) for d in w.get("contributionDays", [])
                if d.get("date")
            ]
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            days = [d for d in days if d["date"] <= today_str]
            if days:
                b_len, b_start, b_end = 0, "", ""
                c_len, c_start, c_end = 0, "", ""
                for d in days:
                    if int(d.get("contributionCount", 0)) > 0:
                        if c_len == 0:
                            c_start = d["date"]
                        c_len += 1
                        c_end = d["date"]
                        if c_len >= b_len:
                            b_len, b_start, b_end = c_len, c_start, c_end
                    else:
                        if d["date"] == today_str and c_len > 0:
                            continue
                        c_len = 0
                if c_len >= curr_len and c_start and c_end:
                    curr_len = c_len
                    curr_range = f"{fmt_date(c_start)} - {fmt_date(c_end)}"
                if b_len >= streak_len and b_start and b_end:
                    streak_len = max(b_len, curr_len)
                    long_range = f"{fmt_date(b_start)} - {fmt_date(b_end)}"
        except Exception:
            pass

    search_commits = 0
    try:
        c_search = fetch_json(f"https://api.github.com/search/commits?q=author:{USERNAME}")
        search_commits = int(c_search.get("total_count", 0))
    except Exception:
        pass

    total_contribs = max(streak_contribs, gql_calendar, search_commits + gql_prs)
    print(
        f"[Telemetry] streak_api={streak_contribs}, gql_calendar={gql_calendar}, "
        f"search_commits={search_commits}, gql_prs={gql_prs} => total_contributions={total_contribs}"
    )
    return {
        "total_contributions": total_contribs,
        "current_streak": curr_len,
        "longest_streak": streak_len,
        "current_range": curr_range,
        "longest_range": long_range,
        "v": ts,
    }


def render_streak_svg(data: dict) -> str:
    """Renders streak-stats.svg unified with the REPO GALAXY (midnight) color palette."""
    total_formatted = f"{data['total_contributions']:,}"
    curr_streak = str(data["current_streak"])
    long_streak = str(data["longest_streak"])
    curr_range = data["current_range"]
    long_range = data["longest_range"]

    return f"""<svg xmlns='http://www.w3.org/2000/svg' xmlns:xlink='http://www.w3.org/1999/xlink'
                style='isolation: isolate' viewBox='0 0 495 195' width='495px' height='195px' direction='ltr'>
        <style>
            @keyframes currstreak {{
                0% {{ font-size: 3px; opacity: 0.2; }}
                80% {{ font-size: 34px; opacity: 1; }}
                100% {{ font-size: 28px; opacity: 1; }}
            }}
            @keyframes fadein {{
                0% {{ opacity: 0; }}
                100% {{ opacity: 1; }}
            }}
        </style>
        <defs>
            <clipPath id='outer_rectangle'>
                <rect width='495' height='195' rx='4.5'/>
            </clipPath>
            <mask id='mask_out_ring_behind_fire'>
                <rect width='495' height='195' fill='white'/>
                <ellipse id='mask-ellipse' cx='247.5' cy='32' rx='13' ry='18' fill='black'/>
            </mask>
        </defs>
        <g clip-path='url(#outer_rectangle)'>
            <g style='isolation: isolate'>
                <rect stroke='{GALAXY_BORDER}' fill='{GALAXY_BG}' rx='4.5' x='0.5' y='0.5' width='494' height='194'/>
            </g>
            <g style='isolation: isolate'>
                <line x1='165' y1='28' x2='165' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='{GALAXY_BORDER}' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
                <line x1='330' y1='28' x2='330' y2='170' vector-effect='non-scaling-stroke' stroke-width='1' stroke='{GALAXY_BORDER}' stroke-linejoin='miter' stroke-linecap='square' stroke-miterlimit='3'/>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(82.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_TEXT}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                        {total_formatted}
                    </text>
                </g>
                <g transform='translate(82.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_TITLE}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='600' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.7s'>
                        Total Contributions
                    </text>
                </g>
                <g transform='translate(82.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_SUBTEXT}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.8s'>
                        Mar 30, 2013 - Present
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(247.5, 108)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_TITLE}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        Current Streak
                    </text>
                </g>
                <g transform='translate(247.5, 145)'>
                    <text x='0' y='21' stroke-width='0' text-anchor='middle' fill='{GALAXY_SUBTEXT}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 0.9s'>
                        {curr_range}
                    </text>
                </g>
                <g mask='url(#mask_out_ring_behind_fire)'>
                    <circle cx='247.5' cy='71' r='40' fill='none' stroke='{GALAXY_TITLE}' stroke-width='5' style='opacity: 0; animation: fadein 0.5s linear forwards 0.4s'></circle>
                </g>
                <g transform='translate(247.5, 19.5)' stroke-opacity='0' style='opacity: 0; animation: fadein 0.5s linear forwards 0.6s'>
                    <path d='M -12 -0.5 L 15 -0.5 L 15 23.5 L -12 23.5 L -12 -0.5 Z' fill='none'/>
                    <path d='M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 C 4.51 16.85 2.36 19 -0.29 19 Z' fill='{GALAXY_GOLD}' stroke-opacity='0'/>
                </g>
                <g transform='translate(247.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_GOLD}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='animation: currstreak 0.6s linear forwards'>
                        {curr_streak}
                    </text>
                </g>
            </g>
            <g style='isolation: isolate'>
                <g transform='translate(412.5, 48)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_TEXT}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='700' font-size='28px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.2s'>
                        {long_streak}
                    </text>
                </g>
                <g transform='translate(412.5, 84)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_TITLE}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='600' font-size='14px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.3s'>
                        Longest Streak
                    </text>
                </g>
                <g transform='translate(412.5, 114)'>
                    <text x='0' y='32' stroke-width='0' text-anchor='middle' fill='{GALAXY_SUBTEXT}' stroke='none' font-family='"Segoe UI", Ubuntu, sans-serif' font-weight='400' font-size='12px' font-style='normal' style='opacity: 0; animation: fadein 0.5s linear forwards 1.4s'>
                        {long_range}
                    </text>
                </g>
            </g>
        </g>
    </svg>"""


def sync_trophies_svg(v: int) -> None:
    """Fetches github-trophies SVG and re-themes it to match REPO GALAXY (midnight) with zero green."""
    url = (
        f"https://github-trophies.vercel.app/?username={USERNAME}"
        f"&theme=tokyonight&no-frame=false&no-bg=false&margin-w=12&row=1&column=7&v={v}"
    )
    try:
        svg = fetch_text(url)
        # 1. Card background and border matching REPO GALAXY (#060b1e bg, #5b5c8a border)
        svg = svg.replace('fill="#1a1b27"', f'fill="{GALAXY_BG}"')
        svg = svg.replace('stroke="#e1e4e8"', f'stroke="{GALAXY_BORDER}"')
        # 2. Trophy header title -> Cosmic Periwinkle Indigo (#8087e2)
        svg = svg.replace('fill="#70a5fd"', f'fill="{GALAXY_TITLE}"')
        # 3. Rank title (y="85") -> Starlight Ice White (#dee7f0), Points subtitle (y="97") -> Lavender-Slate (#9098bf)
        svg = re.sub(
            r'(<text x="50%" y="85"[^>]+fill=")#38bdae(")',
            rf'\g<1>{GALAXY_TEXT}\2',
            svg,
        )
        svg = re.sub(
            r'(<text x="50%" y="97"[^>]+fill=")#38bdae(")',
            rf'\g<1>{GALAXY_SUBTEXT}\2',
            svg,
        )
        # 4. Replace hardcoded green laurel wreaths (#178600) and green/teal accents (#2dde98) with Galaxy Indigo/Gold
        svg = svg.replace('fill="#178600"', f'fill="{GALAXY_TITLE}"')
        svg = svg.replace('stop-color="#2dde98"', f'stop-color="{GALAXY_TITLE}"')
        svg = svg.replace('fill="#00aeff"', f'fill="{GALAXY_TITLE}"')
        TROPHIES_SVG_PATH.write_text(svg, encoding="utf-8")
    except Exception as exc:
        print(f"[Telemetry] Trophies SVG sync warning: {exc}")


def fetch_account_metrics() -> dict:
    user_data = fetch_json(f"https://api.github.com/users/{USERNAME}")
    repos_data = fetch_json(f"https://api.github.com/users/{USERNAME}/repos?per_page=100")
    live = fetch_live_contributions_and_streaks()
    STREAK_SVG_PATH.write_text(render_streak_svg(live), encoding="utf-8")
    sync_trophies_svg(live["v"])

    stars = sum(int(r.get("stargazers_count", 0)) for r in repos_data if isinstance(r, dict))
    return {
        "repos": int(user_data.get("public_repos", 10)),
        "stars": stars,
        "contributions": live["total_contributions"],
        "streak": live["longest_streak"],
        "followers": int(user_data.get("followers", 24)),
        "v": live["v"],
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
    # 1. Self-hosted streak-stats.svg in REPO GALAXY midnight theme
    content = re.sub(
        r'<img src="https://(?:streak-stats\.demolab\.com|raw\.githubusercontent\.com/1stANUNNAKI/1stANUNNAKI/main/streak-stats\.svg)[^"]*" />',
        f'<img src="https://raw.githubusercontent.com/1stANUNNAKI/1stANUNNAKI/main/streak-stats.svg?v={v}" />',
        content,
    )
    # 2. Self-hosted trophies.svg in REPO GALAXY midnight theme
    content = re.sub(
        r'<img src="https://(?:github-trophies\.vercel\.app|raw\.githubusercontent\.com/1stANUNNAKI/1stANUNNAKI/main/trophies\.svg)[^"]*" />',
        f'<img src="https://raw.githubusercontent.com/1stANUNNAKI/1stANUNNAKI/main/trophies.svg?v={v}" />',
        content,
    )
    # 3. Unify PLAYER STATS and WEAPON MASTERY colors with REPO GALAXY midnight palette
    content = re.sub(
        r'<img height="180" src="https://github-readme-stats-eight-theta\.vercel\.app/api\?username=1stANUNNAKI[^"]*" />',
        (
            f'<img height="180" src="https://github-readme-stats-eight-theta.vercel.app/api?username=1stANUNNAKI'
            f'&show_icons=true&hide_border=false&bg_color=060B1E&title_color=8087E2&icon_color=FACC15'
            f'&text_color=DEE7F0&border_color=5B5C8A&ring_color=8087E2&include_all_commits=true'
            f'&count_private=true&custom_title=%F0%9F%8E%AE%20PLAYER%20STATS&cache_seconds=1800&v={v}" />'
        ),
        content,
    )
    content = re.sub(
        r'<img height="180" src="https://github-readme-stats-eight-theta\.vercel\.app/api/top-langs/\?username=1stANUNNAKI[^"]*" />',
        (
            f'<img height="180" src="https://github-readme-stats-eight-theta.vercel.app/api/top-langs/?username=1stANUNNAKI'
            f'&layout=compact&hide_border=false&bg_color=060B1E&title_color=8087E2&text_color=DEE7F0'
            f'&border_color=5B5C8A&langs_count=8&custom_title=%E2%9A%94%EF%B8%8F%20WEAPON%20MASTERY&cache_seconds=1800&v={v}" />'
        ),
        content,
    )
    return content


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
    README_PATH.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    changed = update_readme()
    print(f"README, streak-stats.svg, and trophies.svg telemetry updated: {changed}")
