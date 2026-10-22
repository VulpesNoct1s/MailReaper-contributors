"""
MailReaper - Steam OSINT
Oyuncu profili — SteamCommunity public HTML + SteamID çözümü
"""
import re
import requests
from bs4 import BeautifulSoup
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_steam(username_or_url: str) -> dict:
    """
    Steam profili kazır.
    Desteklenen: vanity URL (steamcommunity.com/id/X), 64-bit SteamID veya direkt username.
    """
    inp = username_or_url.strip()

    # URL normalize
    m = re.search(r"steamcommunity\.com/(id|profiles)/([^/?]+)", inp)
    if m:
        path_type = m.group(1)
        identifier = m.group(2)
        if path_type == "id":
            url = f"https://steamcommunity.com/id/{identifier}/"
        else:
            url = f"https://steamcommunity.com/profiles/{identifier}/"
    elif inp.isdigit() and len(inp) >= 17:
        url = f"https://steamcommunity.com/profiles/{inp}/"
    else:
        url = f"https://steamcommunity.com/id/{inp}/"

    result = {
        "input": inp,
        "profile_url": url,
        "found": False,
        "steam_id64": None,
        "username": None,
        "real_name": None,
        "location": None,
        "state": None,
        "profile_pic_url": None,
        "level": None,
        "games_count": None,
        "friends_count": None,
        "badges_count": None,
        "hours_played": None,
        "summary": None,
        "is_private": False,
        "is_vac_banned": False,
        "member_since": None,
        "recent_games": [],
        "error": None,
    }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 404 or "the specified profile could not be found" in resp.text.lower():
            result["error"] = "Profil bulunamadı"
            return result

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Private check
        if soup.find(class_="profile_private_info"):
            result["is_private"] = True

        # Username
        name_el = soup.find(class_="actual_persona_name")
        if name_el:
            result["username"] = name_el.get_text(strip=True)
            result["found"] = True

        # Real name
        real_el = soup.find(class_="header_real_name")
        if real_el: result["real_name"] = real_el.get_text(strip=True).strip("()")

        # Location
        loc_el = soup.find(class_="header_real_name")
        if loc_el:
            loc_text = loc_el.get_text(strip=True)
            # Remove real name, get location
            loc_parts = loc_text.split("\n")
            if len(loc_parts) > 1:
                result["location"] = loc_parts[-1].strip()

        loc2 = soup.find(class_="header_location")
        if loc2:
            result["location"] = loc2.get_text(strip=True)

        # Profile pic
        avatar_el = soup.find(class_="playerAvatarAutoSizeInner")
        if avatar_el:
            img = avatar_el.find("img")
            if img: result["profile_pic_url"] = img.get("src")

        if not result["profile_pic_url"]:
            og_img = soup.find("meta", property="og:image")
            if og_img: result["profile_pic_url"] = og_img.get("content")

        # Summary
        summary_el = soup.find(class_="profile_summary")
        if summary_el: result["summary"] = summary_el.get_text(strip=True)[:300]

        # Level
        level_el = soup.find(class_="friendPlayerLevelNum")
        if level_el: result["level"] = level_el.get_text(strip=True)

        # Member since
        member_el = soup.find(class_="profile_header_badgeinfo_subtitle")
        if member_el:
            text = member_el.get_text(strip=True)
            result["member_since"] = text

        # Stats from page
        for badge_el in soup.find_all(class_="profile_count_link_total"):
            val = badge_el.get_text(strip=True)
            parent = badge_el.find_parent(class_="profile_count_link")
            if parent:
                label = parent.get_text(strip=True).lower()
                if "game"   in label: result["games_count"]  = val
                if "friend" in label: result["friends_count"] = val
                if "badge"  in label: result["badges_count"]  = val

        # VAC Ban
        result["is_vac_banned"] = bool(soup.find(class_="profile_ban"))

        # Steam ID64 from page source
        m64 = re.search(r'"steamid":"(\d{17})"', html)
        if m64: result["steam_id64"] = m64.group(1)

        # Online state
        state_el = soup.find(class_=re.compile(r"persona_name_and_status"))
        if state_el:
            online = state_el.find(class_=re.compile(r"online|offline|away|ingame"))
            if online: result["state"] = online.get_text(strip=True)

    except Exception as e:
        result["error"] = str(e)

    return result
