"""
MailReaper - TikTok OSINT
Public profil kazıma, API key gerektirmez
"""
import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.tiktok.com/",
}


def scrape_tiktok(username: str) -> dict:
    username = username.strip().lstrip("@")
    result = {
        "username": username,
        "found": False,
        "profile_url": f"https://www.tiktok.com/@{username}",
        "nickname": None,
        "bio": None,
        "followers": None,
        "following": None,
        "likes": None,
        "videos": None,
        "is_verified": False,
        "profile_pic_url": None,
        "region": None,
        "error": None,
    }

    try:
        url = f"https://www.tiktok.com/@{username}"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 404 or "couldn't find this account" in resp.text.lower():
            result["error"] = "Kullanıcı bulunamadı"
            return result

        html = resp.text

        # SIGI_STATE veya __UNIVERSAL_DATA_FOR_REHYDRATION__ JSON'ı çıkar
        patterns = [
            r'<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>(\{.+?\})</script>',
            r'window\[\'SIGI_STATE\'\]\s*=\s*(\{.+?\});\s*window',
            r'<script id="SIGI_STATE"[^>]*>(\{.+?\})</script>',
        ]

        for pattern in patterns:
            m = re.search(pattern, html, re.DOTALL)
            if m:
                try:
                    data = json.loads(m.group(1))
                    # UserModule veya userInfo altında
                    user_info = None

                    # Path 1
                    try:
                        user_info = list(data.get("UserModule", {}).get("users", {}).values())[0]
                    except Exception:
                        pass

                    # Path 2
                    if not user_info:
                        try:
                            user_info = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["user"]
                        except Exception:
                            pass

                    if user_info:
                        result["found"] = True
                        result["nickname"]    = user_info.get("nickname")
                        result["bio"]         = user_info.get("signature")
                        result["is_verified"] = user_info.get("verified", False)
                        result["profile_pic_url"] = user_info.get("avatarLarger") or user_info.get("avatarMedium")
                        result["region"]      = user_info.get("region")

                    # Stats
                    try:
                        stats_map = list(data.get("UserModule", {}).get("stats", {}).values())[0]
                        result["followers"] = stats_map.get("followerCount")
                        result["following"] = stats_map.get("followingCount")
                        result["likes"]     = stats_map.get("heartCount") or stats_map.get("diggCount")
                        result["videos"]    = stats_map.get("videoCount")
                    except Exception:
                        pass

                    # Path 2 stats
                    if not result["followers"]:
                        try:
                            stats = data["__DEFAULT_SCOPE__"]["webapp.user-detail"]["userInfo"]["stats"]
                            result["followers"] = stats.get("followerCount")
                            result["following"] = stats.get("followingCount")
                            result["likes"]     = stats.get("heartCount")
                            result["videos"]    = stats.get("videoCount")
                        except Exception:
                            pass

                    if result["found"]:
                        return result

                except Exception:
                    continue

        # Fallback: OG meta tags
        soup = BeautifulSoup(html, "html.parser")
        og_title = soup.find("meta", property="og:title")
        og_desc  = soup.find("meta", property="og:description")
        og_img   = soup.find("meta", property="og:image")

        if og_title and og_title.get("content"):
            result["found"] = True
            result["nickname"] = og_title.get("content", "").split("|")[0].strip()

        if og_desc:
            desc = og_desc.get("content", "")
            # "123.4K Followers, 456 Following, 7890 Likes"
            m2 = re.search(r"([\d.,KkMm]+)\s*Followers?", desc)
            if m2: result["followers"] = m2.group(1)

        if og_img:
            result["profile_pic_url"] = og_img.get("content")

    except Exception as e:
        result["error"] = str(e)

    return result
