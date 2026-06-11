import requests
import os
from datetime import datetime


def fetch_starred_repos(token, username):
    """Fetch all starred repos with star timestamps."""
    repos = []
    page = 1
    per_page = 100

    while True:
        url = f"https://api.github.com/users/{username}/starred"
        headers = {
            "Accept": "application/vnd.github.v3.star+json",
        }
        if token:
            headers["Authorization"] = f"token {token}"
        params = {"page": page, "per_page": per_page}

        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            break

        data = resp.json()
        if not data:
            break

        for item in data:
            repo = item["repo"]
            repos.append(
                {
                    "name": repo["full_name"],
                    "url": repo["html_url"],
                    "description": repo["description"] or "No description",
                    "language": repo["language"] or "Others",
                    "stars": repo["stargazers_count"],
                    "starred_at": item["starred_at"],
                }
            )

        if len(data) < per_page:
            break
        page += 1

    return repos


def generate_stars_md(repos):
    """Generate stars.md with language-based and chronological sections."""
    lang_groups = {}
    for repo in repos:
        lang = repo["language"]
        lang_groups.setdefault(lang, []).append(repo)

    sorted_langs = sorted(lang_groups.keys(), key=lambda x: x.lower())
    for lang in lang_groups:
        lang_groups[lang].sort(key=lambda r: r["stars"], reverse=True)

    chrono_repos = sorted(repos, key=lambda r: r["starred_at"], reverse=True)
    total = len(repos)

    lines = [
        "---",
        'title: "星标项目"',
        f'date: {datetime.now().strftime("%Y-%m-%d")}',
        'layout: "single"',
        "showtoc: true",
        "---",
        "",
        "# My GitHub Stars",
        "",
        f"Total stars: {total}",
        "",
        "## Table of Contents",
        "",
        "- [时间线](#时间线)",
    ]

    for lang in sorted_langs:
        anchor = lang.lower().replace(" ", "-").replace("#", "sharp")
        lines.append(f"  - [{lang}](#{anchor})")
    lines.append("")

    lines.append("## 时间线")
    lines.append("")
    for repo in chrono_repos:
        date = repo["starred_at"][:10]
        desc = repo["description"]
        lines.append(
            f"- [{date}] [{repo['name']}]({repo['url']}) - {desc} (★{repo['stars']})"
        )
    lines.append("")

    for lang in sorted_langs:
        lines.append(f"## {lang}")
        lines.append("")
        for repo in lang_groups[lang]:
            desc = repo["description"]
            lines.append(
                f"- [{repo['name']}]({repo['url']}) - {desc} (★{repo['stars']})"
            )
        lines.append("")

    return "\n".join(lines)


def main():
    token = os.environ["GITHUB_TOKEN"]
    username = os.environ.get("GITHUB_USERNAME", "Yzeph")

    repos = fetch_starred_repos(token, username)
    content = generate_stars_md(repos)

    with open("content/stars.md", "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Generated content/stars.md with {len(repos)} starred repos")


if __name__ == "__main__":
    main()
