"""
MailReaper - Twitter/X OSINT
Public profil — Nitter mirror üzerinden kazıma, API key yok
"""
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

# Nitter public instances (fallback listesi)
NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://nitter.lucabased.xyz",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]


def _try_nitter(username: str) -> dict | None:
    """Nitter instance'larını sırayla dener."""
    for instance in NITTER_INSTANCES:
        try:
            url = f"{instance}/{username}"
            resp = requests.get(url, headers=HEADERS, timeout=8, allow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            # 404/not found kontrolü
            if soup.find(class_="error-panel") or "doesn't exist" in resp.text.lower():
                return {"found": False, "error": "Kullanıcı bulunamadı"}

            result = {"found": True, "source_instance": instance}

            # Full name
            fn = soup.find(class_="fullname")
            if fn: result["full_name"] = fn.get_text(strip=True)

            # Username
            un = soup.find(class_="username")
            if un: result["username_display"] = un.get_text(strip=True)

            # Bio
            bio = soup.find(class_="profile-bio")
            if bio: result["bio"] = bio.get_text(strip=True)

            # Location
            loc = soup.find(class_="profile-location")
            if loc: result["location"] = loc.get_text(strip=True)

            # Website
            web = soup.find(class_="profile-website")
            if web:
                a = web.find("a")
                result["website"] = a["href"] if a else web.get_text(strip=True)

            # Joined date
            joined = soup.find(class_="profile-joindate")
            if joined: result["joined"] = joined.get_text(strip=True)

            # Stats (tweets, following, followers, likes)
            stats = {}
            for item in soup.find_all(class_="profile-stat-num"):
                val = item.get_text(strip=True)
                label_el = item.find_next_sibling() or item.parent
                label = label_el.get_text(strip=True).lower() if label_el else ""
                if "tweet" in label or "post" in label:    stats["tweets"]    = val
                elif "following" in label:                  stats["following"]  = val
                elif "followers" in label:                  stats["followers"]  = val
                elif "like" in label:                       stats["likes"]      = val
            result["stats"] = stats

            # Profile pic
            pic = soup.find("a", class_="profile-card-avatar")
            if pic:
                img = pic.find("img")
                if img and img.get("src"):
                    result["profile_pic_url"] = instance + img["src"]

            # Verified badge
            result["is_verified"] = bool(soup.find(class_="verified-icon") or soup.find(class_="label-gold"))

            # Banner
            banner = soup.find(class_="profile-banner")
            if banner:
                img = banner.find("img")
                if img and img.get("src"):
                    result["banner_url"] = instance + img["src"]

            # Recent tweets
            tweets = []
            for tweet_el in soup.find_all(class_="timeline-item")[:5]:
                content = tweet_el.find(class_="tweet-content")
                date_el = tweet_el.find(class_="tweet-date")
                stats_el = tweet_el.find(class_="tweet-stats")
                if content:
                    t = {"text": content.get_text(strip=True)[:200]}
                    if date_el:
                        a = date_el.find("a")
                        t["date"] = a.get("title", "") if a else ""
                    if stats_el:
                        for stat in stats_el.find_all(class_="icon-container"):
                            t["engagement"] = stat.get_text(strip=True)
                    tweets.append(t)
            result["recent_tweets"] = tweets

            return result

        except Exception:
            continue
    return None


def _try_twitter_direct(username: str) -> dict | None:
    """Twitter.com'dan direkt meta tag kazıma."""
    try:
        resp = requests.get(
            f"https://twitter.com/{username}",
            headers={**HEADERS, "User-Agent": "Twitterbot/1.0"},
            timeout=10
        )
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            result = {"found": True, "source_instance": "twitter.com"}

            og_title = soup.find("meta", property="og:title")
            og_desc  = soup.find("meta", property="og:description")
            og_img   = soup.find("meta", property="og:image")

            if og_title: result["full_name"] = og_title.get("content", "").split("(@")[0].strip()
            if og_desc:  result["bio"] = og_desc.get("content", "")
            if og_img:   result["profile_pic_url"] = og_img.get("content", "")

            # Extract stats from description
            if og_desc:
                desc = og_desc.get("content", "")
                m = re.findall(r"([\d,]+)\s+(Tweets?|Following|Followers?|Likes?)", desc)
                stats = {k.lower().rstrip("s"): v for v, k in m}
                result["stats"] = stats

            return result
    except Exception:
        pass
    return None


def scrape_twitter(username: str) -> dict:
    username = username.strip().lstrip("@")
    result = {
        "username": username,
        "found": False,
        "profile_url": f"https://twitter.com/{username}",
        "nitter_url": None,
        "full_name": None,
        "bio": None,
        "location": None,
        "website": None,
        "joined": None,
        "is_verified": False,
        "stats": {},
        "profile_pic_url": None,
        "recent_tweets": [],
        "error": None,
    }

    # 1. Nitter'ı dene
    nitter_data = _try_nitter(username)
    if nitter_data and nitter_data.get("found"):
        result.update(nitter_data)
        result["nitter_url"] = f"{nitter_data.get('source_instance','https://nitter.net')}/{username}"
        return result

    if nitter_data and not nitter_data.get("found"):
        result["error"] = nitter_data.get("error", "Bulunamadı")
        return result

    # 2. Twitter direkt
    tw_data = _try_twitter_direct(username)
    if tw_data:
        result.update(tw_data)
        return result

    result["error"] = "Tüm yöntemler başarısız (Nitter/Twitter erişim sorunu)"
    return result
