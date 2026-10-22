"""
MailReaper - GitHub Search Module
GitHub'da email ve kullanıcı adı araması yapar (API key gerektirmez)
"""

import time
import requests
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/vnd.github+json",
}

WEB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}


def _get_github_user(username: str) -> dict | None:
    """GitHub public API ile kullanıcı profili çeker."""
    try:
        resp = requests.get(
            f"https://api.github.com/users/{quote(username)}",
            headers=HEADERS,
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "login": data.get("login"),
                "name": data.get("name"),
                "bio": data.get("bio"),
                "location": data.get("location"),
                "company": data.get("company"),
                "blog": data.get("blog"),
                "public_repos": data.get("public_repos"),
                "followers": data.get("followers"),
                "following": data.get("following"),
                "created_at": data.get("created_at"),
                "avatar_url": data.get("avatar_url"),
                "html_url": data.get("html_url"),
                "hireable": data.get("hireable"),
                "twitter_username": data.get("twitter_username"),
            }
    except Exception:
        pass
    return None


def _search_users_by_email(email: str) -> list:
    """GitHub public API ile email'e göre kullanıcı arar."""
    try:
        resp = requests.get(
            f"https://api.github.com/search/users?q={quote(email)}+in:email&per_page=5",
            headers=HEADERS,
            timeout=8,
        )
        if resp.status_code == 200:
            data = resp.json()
            return [item.get("login") for item in data.get("items", []) if item.get("login")]
    except Exception:
        pass
    return []


def _search_commits(email: str) -> list:
    """GitHub public API ile commit geçmişini tarar."""
    commits = []
    try:
        resp = requests.get(
            f"https://api.github.com/search/commits?q=author-email:{quote(email)}&per_page=10&sort=author-date",
            headers={**HEADERS, "Accept": "application/vnd.github.cloak-preview+json"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            for item in data.get("items", [])[:10]:
                commit = item.get("commit", {})
                repo = item.get("repository", {})
                commits.append({
                    "repo": repo.get("full_name", ""),
                    "author": commit.get("author", {}).get("name", ""),
                    "message": commit.get("message", "")[:80],
                    "url": item.get("html_url", ""),
                    "date": commit.get("author", {}).get("date", ""),
                })
    except Exception:
        pass
    return commits


def search_github(email: str, username: str) -> dict:
    """
    GitHub'da email ve kullanıcı adı araması yapar.
    Rate limit sorunlarını önlemek için aralar ekler.
    """
    result = {
        "github_user": None,
        "commits_found": [],
        "code_results": [],
        "search_urls": [
            f"https://github.com/search?q={quote(email)}&type=commits",
            f'https://github.com/search?q="{quote(email)}"&type=code',
        ],
    }

    # 1. Kullanıcı adı ile direkt profil kontrolü
    user_data = _get_github_user(username)
    if user_data:
        result["github_user"] = user_data

    time.sleep(0.5)

    # 2. Email ile kullanıcı araması
    if not result["github_user"]:
        email_users = _search_users_by_email(email)
        if email_users:
            user_data = _get_github_user(email_users[0])
            if user_data:
                result["github_user"] = user_data

    time.sleep(0.5)

    # 3. Commit geçmişi araması
    commits = _search_commits(email)
    result["commits_found"] = commits

    return result
