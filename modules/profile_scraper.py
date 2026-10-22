"""
MailReaper - Public Profile Scraper
Reddit, HackerNews, GitHub'dan public JSON API ile profil bilgisi çeker.
Auth/API key gerektirmez.
"""

import requests
import time
from datetime import datetime

HEADERS = {
    "User-Agent": "Mozilla/5.0 MailReaper/2.0 OSINT Tool",
    "Accept": "application/json",
}


# ─── REDDIT ───

def scrape_reddit(username: str) -> dict:
    """Reddit public JSON API ile kullanıcı profili ve aktivitesi."""
    result = {
        "found": False,
        "username": username,
        "profile": {},
        "recent_posts": [],
        "recent_comments": [],
        "subreddits": [],
        "error": None,
    }

    # Profil bilgisi
    try:
        resp = requests.get(
            f"https://www.reddit.com/user/{username}/about.json",
            headers=HEADERS, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            result["found"] = True
            result["profile"] = {
                "username": data.get("name"),
                "id": data.get("id"),
                "created_utc": datetime.utcfromtimestamp(data.get("created_utc", 0)).strftime("%Y-%m-%d") if data.get("created_utc") else None,
                "link_karma": data.get("link_karma"),
                "comment_karma": data.get("comment_karma"),
                "total_karma": data.get("total_karma"),
                "is_gold": data.get("is_gold"),
                "is_mod": data.get("is_mod"),
                "verified": data.get("verified"),
                "icon_img": data.get("icon_img", "").split("?")[0],
                "banner_img": data.get("subreddit", {}).get("banner_img"),
                "description": data.get("subreddit", {}).get("public_description"),
                "profile_url": f"https://www.reddit.com/user/{username}",
                "has_nsfw_profile": data.get("subreddit", {}).get("over_18", False),
            }
        elif resp.status_code == 404:
            result["error"] = "Kullanıcı bulunamadı"
            return result
    except Exception as e:
        result["error"] = str(e)
        return result

    time.sleep(0.5)

    # Son gönderiler
    try:
        resp = requests.get(
            f"https://www.reddit.com/user/{username}/submitted.json?limit=10",
            headers=HEADERS, timeout=10
        )
        if resp.status_code == 200:
            posts = resp.json().get("data", {}).get("children", [])
            subreddits = set()
            for post in posts:
                d = post.get("data", {})
                sub = d.get("subreddit", "")
                subreddits.add(sub)
                result["recent_posts"].append({
                    "title": d.get("title", "")[:100],
                    "subreddit": sub,
                    "score": d.get("score"),
                    "url": f"https://www.reddit.com{d.get('permalink', '')}",
                    "created": datetime.utcfromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%d"),
                    "num_comments": d.get("num_comments"),
                })
            result["subreddits"] = list(subreddits)
    except Exception:
        pass

    time.sleep(0.5)

    # Son yorumlar
    try:
        resp = requests.get(
            f"https://www.reddit.com/user/{username}/comments.json?limit=10",
            headers=HEADERS, timeout=10
        )
        if resp.status_code == 200:
            comments = resp.json().get("data", {}).get("children", [])
            for comment in comments:
                d = comment.get("data", {})
                sub = d.get("subreddit", "")
                if sub not in result["subreddits"]:
                    result["subreddits"].append(sub)
                result["recent_comments"].append({
                    "body": d.get("body", "")[:200],
                    "subreddit": sub,
                    "score": d.get("score"),
                    "url": f"https://www.reddit.com{d.get('permalink', '')}",
                    "created": datetime.utcfromtimestamp(d.get("created_utc", 0)).strftime("%Y-%m-%d"),
                })
    except Exception:
        pass

    return result


# ─── HACKERNEWS ───

def scrape_hackernews(username: str) -> dict:
    """HackerNews public API ile profil ve aktivite."""
    result = {
        "found": False,
        "username": username,
        "profile": {},
        "recent_items": [],
        "error": None,
    }

    try:
        resp = requests.get(
            f"https://hacker-news.firebaseio.com/v0/user/{username}.json",
            headers=HEADERS, timeout=8
        )
        if resp.status_code == 200 and resp.text != "null":
            data = resp.json()
            if data:
                result["found"] = True
                result["profile"] = {
                    "username": data.get("id"),
                    "karma": data.get("karma"),
                    "created": datetime.utcfromtimestamp(data.get("created", 0)).strftime("%Y-%m-%d") if data.get("created") else None,
                    "about": data.get("about", ""),
                    "delay": data.get("delay"),
                    "submitted_count": len(data.get("submitted", [])),
                    "profile_url": f"https://news.ycombinator.com/user?id={username}",
                }

                # Son 5 gönderiyi çek
                submitted = data.get("submitted", [])[:5]
                for item_id in submitted:
                    try:
                        ir = requests.get(
                            f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                            headers=HEADERS, timeout=5
                        )
                        if ir.status_code == 200:
                            item = ir.json()
                            if item:
                                result["recent_items"].append({
                                    "type": item.get("type"),
                                    "title": item.get("title", item.get("text", "")[:80]),
                                    "url": item.get("url"),
                                    "score": item.get("score"),
                                    "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
                                    "time": datetime.utcfromtimestamp(item.get("time", 0)).strftime("%Y-%m-%d"),
                                })
                    except Exception:
                        pass
    except Exception as e:
        result["error"] = str(e)

    return result


# ─── GITHUB DEEP PROFILE ───

def scrape_github_deep(username: str) -> dict:
    """GitHub public API ile tam profil analizi."""
    result = {
        "found": False,
        "username": username,
        "profile": {},
        "repos": [],
        "languages": {},
        "orgs": [],
        "events": [],
        "gists": [],
        "error": None,
    }

    api_headers = {
        "User-Agent": "MailReaper OSINT",
        "Accept": "application/vnd.github+json",
    }

    # Ana profil
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}",
            headers=api_headers, timeout=8
        )
        if resp.status_code == 200:
            d = resp.json()
            result["found"] = True
            result["profile"] = {
                "login": d.get("login"),
                "name": d.get("name"),
                "email": d.get("email"),
                "bio": d.get("bio"),
                "location": d.get("location"),
                "company": d.get("company"),
                "blog": d.get("blog"),
                "twitter_username": d.get("twitter_username"),
                "public_repos": d.get("public_repos"),
                "public_gists": d.get("public_gists"),
                "followers": d.get("followers"),
                "following": d.get("following"),
                "created_at": d.get("created_at"),
                "updated_at": d.get("updated_at"),
                "avatar_url": d.get("avatar_url"),
                "profile_url": d.get("html_url"),
                "type": d.get("type"),
                "site_admin": d.get("site_admin"),
            }
    except Exception as e:
        result["error"] = str(e)
        return result

    time.sleep(0.3)

    # Repolar
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}/repos?sort=updated&per_page=10",
            headers=api_headers, timeout=8
        )
        if resp.status_code == 200:
            repos = resp.json()
            lang_counts = {}
            for repo in repos:
                lang = repo.get("language")
                if lang:
                    lang_counts[lang] = lang_counts.get(lang, 0) + 1
                result["repos"].append({
                    "name": repo.get("name"),
                    "description": (repo.get("description") or "")[:100],
                    "language": lang,
                    "stars": repo.get("stargazers_count"),
                    "forks": repo.get("forks_count"),
                    "url": repo.get("html_url"),
                    "updated": repo.get("updated_at", "")[:10],
                    "fork": repo.get("fork"),
                })
            result["languages"] = lang_counts
    except Exception:
        pass

    time.sleep(0.3)

    # Organizasyonlar
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}/orgs",
            headers=api_headers, timeout=8
        )
        if resp.status_code == 200:
            result["orgs"] = [
                {"login": o.get("login"), "url": f"https://github.com/{o.get('login')}"}
                for o in resp.json()
            ]
    except Exception:
        pass

    time.sleep(0.3)

    # Son aktivite
    try:
        resp = requests.get(
            f"https://api.github.com/users/{username}/events/public?per_page=10",
            headers=api_headers, timeout=8
        )
        if resp.status_code == 200:
            for event in resp.json()[:10]:
                result["events"].append({
                    "type": event.get("type"),
                    "repo": event.get("repo", {}).get("name"),
                    "created_at": event.get("created_at", "")[:10],
                })
    except Exception:
        pass

    return result
