"""
MailReaper - Instagram OSINT
Public profil kazıma — API key gerektirmez
"""
import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instagram.com/",
}

def scrape_instagram(username: str) -> dict:
    username = username.strip().lstrip("@")
    result = {
        "username": username,
        "found": False,
        "profile_url": f"https://www.instagram.com/{username}/",
        "full_name": None,
        "bio": None,
        "followers": None,
        "following": None,
        "posts": None,
        "is_private": None,
        "is_verified": None,
        "profile_pic_url": None,
        "external_url": None,
        "category": None,
        "highlights_count": None,
        "is_business": None,
        "contact_phone": None,
        "contact_email": None,
        "error": None,
    }

    # Method 1: JSON endpoint
    try:
        url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
        h = {**HEADERS, "X-IG-App-ID": "936619743392459", "X-Requested-With": "XMLHttpRequest"}
        resp = requests.get(url, headers=h, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            user = data.get("data", {}).get("user", {})
            if user:
                result["found"] = True
                result["full_name"]       = user.get("full_name")
                result["bio"]             = user.get("biography")
                result["followers"]       = user.get("edge_followed_by", {}).get("count")
                result["following"]       = user.get("edge_follow", {}).get("count")
                result["posts"]           = user.get("edge_owner_to_timeline_media", {}).get("count")
                result["is_private"]      = user.get("is_private")
                result["is_verified"]     = user.get("is_verified")
                result["profile_pic_url"] = user.get("profile_pic_url_hd") or user.get("profile_pic_url")
                result["external_url"]    = user.get("external_url")
                result["category"]        = user.get("category_name")
                result["is_business"]     = user.get("is_business_account")
                result["contact_phone"]   = user.get("business_phone_number")
                result["contact_email"]   = user.get("business_email")
                return result
    except Exception:
        pass

    # Method 2: HTML scrape
    try:
        resp = requests.get(f"https://www.instagram.com/{username}/", headers=HEADERS, timeout=12)
        if resp.status_code == 404:
            result["error"] = "Kullanıcı bulunamadı"
            return result
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "html.parser")
            # Meta tags
            desc_tag = soup.find("meta", attrs={"name": "description"})
            og_img   = soup.find("meta", property="og:image")
            og_title = soup.find("meta", property="og:title")
            title_tag = soup.find("title")

            if og_title:
                result["full_name"] = og_title.get("content", "").split("(")[0].strip()
                result["found"] = True

            if og_img:
                result["profile_pic_url"] = og_img.get("content")

            if desc_tag:
                desc = desc_tag.get("content", "")
                # "1.5M Followers, 400 Following, 2,847 Posts"
                m = re.search(r"([\d,.KM]+)\s*Followers?,\s*([\d,.KM]+)\s*Following,\s*([\d,.KM]+)\s*Posts?", desc, re.I)
                if m:
                    result["found"] = True
                    result["followers"] = m.group(1)
                    result["following"] = m.group(2)
                    result["posts"]     = m.group(3)
                bio_m = re.search(r'Posts?\s*-\s*(.+)', desc)
                if bio_m:
                    result["bio"] = bio_m.group(1).strip()

            # Try embedded JSON
            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    j = json.loads(script.string or "")
                    if j.get("@type") == "ProfilePage":
                        result["found"] = True
                except Exception:
                    pass
    except Exception as e:
        result["error"] = str(e)

    return result
