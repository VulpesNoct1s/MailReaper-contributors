"""
MailReaper - Social Media Presence Module
45+ platformda email yerel kısmı ile hesap araması yapar
API gerektirmez — HTTP scrape
"""

import re
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

PLATFORMS = [
    {"name": "GitHub",         "url": "https://github.com/{u}",                     "expected": 200},
    {"name": "Twitter/X",      "url": "https://twitter.com/{u}",                    "expected": 200},
    {"name": "Instagram",      "url": "https://www.instagram.com/{u}/",             "expected": 200},
    {"name": "Reddit",         "url": "https://www.reddit.com/user/{u}",            "expected": 200},
    {"name": "Pinterest",      "url": "https://www.pinterest.com/{u}/",             "expected": 200},
    {"name": "Tumblr",         "url": "https://{u}.tumblr.com",                     "expected": 200, "subdomain": True},
    {"name": "Medium",         "url": "https://medium.com/@{u}",                    "expected": 200},
    {"name": "Dev.to",         "url": "https://dev.to/{u}",                         "expected": 200},
    {"name": "GitLab",         "url": "https://gitlab.com/{u}",                     "expected": 200},
    {"name": "Bitbucket",      "url": "https://bitbucket.org/{u}/",                 "expected": 200},
    {"name": "Keybase",        "url": "https://keybase.io/{u}",                     "expected": 200},
    {"name": "TikTok",         "url": "https://www.tiktok.com/@{u}",               "expected": 200},
    {"name": "YouTube",        "url": "https://www.youtube.com/@{u}",              "expected": 200},
    {"name": "Twitch",         "url": "https://www.twitch.tv/{u}",                 "expected": 200},
    {"name": "SoundCloud",     "url": "https://soundcloud.com/{u}",                "expected": 200},
    {"name": "Flickr",         "url": "https://www.flickr.com/people/{u}",         "expected": 200},
    {"name": "Behance",        "url": "https://www.behance.net/{u}",               "expected": 200},
    {"name": "Dribbble",       "url": "https://dribbble.com/{u}",                  "expected": 200},
    {"name": "ProductHunt",    "url": "https://www.producthunt.com/@{u}",          "expected": 200},
    {"name": "HackerNews",     "url": "https://news.ycombinator.com/user?id={u}",  "expected": 200, "check_text": "user?id="},
    {"name": "Patreon",        "url": "https://www.patreon.com/{u}",               "expected": 200},
    {"name": "About.me",       "url": "https://about.me/{u}",                      "expected": 200},
    {"name": "Linktree",       "url": "https://linktr.ee/{u}",                     "expected": 200},
    {"name": "Vimeo",          "url": "https://vimeo.com/{u}",                     "expected": 200},
    {"name": "Last.fm",        "url": "https://www.last.fm/user/{u}",              "expected": 200},
    {"name": "Goodreads",      "url": "https://www.goodreads.com/{u}",             "expected": 200},
    {"name": "Steam",          "url": "https://steamcommunity.com/id/{u}",         "expected": 200},
    {"name": "Replit",         "url": "https://replit.com/@{u}",                   "expected": 200},
    {"name": "CodePen",        "url": "https://codepen.io/{u}",                    "expected": 200},
    {"name": "npm",            "url": "https://www.npmjs.com/~{u}",                "expected": 200},
    {"name": "PyPI",           "url": "https://pypi.org/user/{u}/",                "expected": 200},
    {"name": "Substack",       "url": "https://{u}.substack.com",                  "expected": 200, "subdomain": True},
    {"name": "Hashnode",       "url": "https://hashnode.com/@{u}",                 "expected": 200},
    {"name": "Dailymotion",    "url": "https://www.dailymotion.com/{u}",           "expected": 200},
    {"name": "Scribd",         "url": "https://www.scribd.com/{u}",                "expected": 200},
    {"name": "Slideshare",     "url": "https://www.slideshare.net/{u}",            "expected": 200},
    {"name": "Mix",            "url": "https://mix.com/{u}",                       "expected": 200},
    {"name": "Spotify",        "url": "https://open.spotify.com/user/{u}",         "expected": 200},
    {"name": "Xbox Live",      "url": "https://xboxgamertag.com/search/{u}",       "expected": 200},
    {"name": "JSFiddle",       "url": "https://jsfiddle.net/user/{u}/",            "expected": 200},
    {"name": "Gravatar",       "url": "https://gravatar.com/{u}",                  "expected": 200},
    {"name": "Disqus",         "url": "https://disqus.com/by/{u}/",                "expected": 200},
    {"name": "Foursquare",     "url": "https://foursquare.com/{u}",                "expected": 200},
    {"name": "Quora",          "url": "https://www.quora.com/profile/{u}",         "expected": 200},
]


def _generate_usernames(email: str) -> list:
    """Email'den kullanıcı adı varyasyonları üretir."""
    local = email.split("@")[0].lower()
    variants = {local}
    variants.add(local.replace(".", ""))
    variants.add(local.replace("_", ""))
    variants.add(local.replace("-", ""))
    # Parçalara böl
    parts = re.split(r'[._\-]', local)
    if len(parts) > 1:
        variants.add(parts[0])
        variants.add(parts[-1])
    return list(variants)[:4]  # max 4 varyasyon


def _check_platform(platform: dict, username: str) -> dict | None:
    """Tek bir platformu kontrol eder."""
    url_template = platform["url"]
    if platform.get("subdomain"):
        url = url_template.replace("{u}", username)
    else:
        url = url_template.replace("{u}", username)

    try:
        resp = requests.get(url, headers=HEADERS, timeout=6, allow_redirects=True)
        status = resp.status_code
        expected = platform.get("expected", 200)

        if status == expected:
            # Bazı platformlar 200 döndürse de "not found" içeriği gösterebilir
            not_found_patterns = [
                "page not found", "404", "user not found",
                "doesn't exist", "no longer available",
                "this account doesn't exist", "sorry, this page"
            ]
            text_lower = resp.text.lower()[:2000]
            for pattern in not_found_patterns:
                if pattern in text_lower:
                    return None

            return {
                "platform": platform["name"],
                "url": url,
                "status": status,
                "username": username,
            }
    except Exception:
        pass
    return None


def check_social_media(email: str) -> dict:
    """Tüm platformlarda sosyal medya varlığını kontrol eder."""
    result = {
        "username_checked": "",
        "found": [],
        "not_found": [],
        "errors": [],
        "total_found": 0,
    }

    usernames = _generate_usernames(email)
    result["username_checked"] = usernames[0] if usernames else email.split("@")[0]

    tasks = []
    for platform in PLATFORMS:
        for username in usernames:
            tasks.append((platform, username))

    found_platforms = set()

    with ThreadPoolExecutor(max_workers=20) as executor:
        future_to_task = {
            executor.submit(_check_platform, platform, username): (platform, username)
            for platform, username in tasks
        }
        for future in as_completed(future_to_task):
            try:
                check_result = future.result()
                if check_result:
                    platform_name = check_result["platform"]
                    if platform_name not in found_platforms:
                        found_platforms.add(platform_name)
                        result["found"].append(check_result)
            except Exception as e:
                platform, _ = future_to_task[future]
                result["errors"].append(f"{platform['name']}: {str(e)}")

    # Not found
    all_platform_names = {p["name"] for p in PLATFORMS}
    result["not_found"] = list(all_platform_names - found_platforms)
    result["total_found"] = len(result["found"])

    # Alfabetik sırala
    result["found"].sort(key=lambda x: x["platform"])

    return result
