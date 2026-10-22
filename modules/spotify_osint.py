"""
MailReaper - Spotify OSINT
Public profil + playlist analizi, API key gerektirmez
"""
import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _extract_username_from_url(input_str: str) -> str:
    """Spotify URL'inden kullanıcı adı çıkarır."""
    # open.spotify.com/user/{id}
    m = re.search(r"spotify\.com/user/([^/?]+)", input_str)
    if m: return m.group(1)
    # open.spotify.com/artist/{id}
    m = re.search(r"spotify\.com/artist/([^/?]+)", input_str)
    if m: return m.group(1)
    return input_str.strip()


def scrape_spotify(username_or_url: str) -> dict:
    username = _extract_username_from_url(username_or_url)

    result = {
        "input": username_or_url,
        "username": username,
        "found": False,
        "profile_url": f"https://open.spotify.com/user/{username}",
        "display_name": None,
        "followers": None,
        "following": None,
        "profile_pic_url": None,
        "public_playlists": [],
        "playlist_count": None,
        "error": None,
    }

    # 1. User profile page
    try:
        url = f"https://open.spotify.com/user/{username}"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 404:
            result["error"] = "Kullanıcı bulunamadı"
            return result

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Embedded JSON (next.js __NEXT_DATA__ veya Spotify'ın kendi JSON'ı)
        next_data = soup.find("script", id="__NEXT_DATA__")
        if next_data:
            try:
                data = json.loads(next_data.string)
                # Spotify Next.js data yapısı değişken ama deneyelim
                props = data.get("props", {}).get("pageProps", {})
                state = props.get("state", {})

                # User entity
                entities = state.get("entities", {})
                users = entities.get("users", {}).get("byId", {})
                for uid, user_data in users.items():
                    if username.lower() in uid.lower():
                        result["found"] = True
                        result["display_name"] = user_data.get("name") or user_data.get("displayName")
                        result["followers"] = user_data.get("followers", {}).get("total")
                        imgs = user_data.get("images", [])
                        if imgs: result["profile_pic_url"] = imgs[-1].get("url")
                        break
            except Exception:
                pass

        # OG meta fallback
        og_title = soup.find("meta", property="og:title")
        og_img   = soup.find("meta", property="og:image")
        og_desc  = soup.find("meta", property="og:description")

        if og_title and og_title.get("content"):
            result["found"] = True
            result["display_name"] = og_title.get("content", "").replace(" | Spotify", "").strip()

        if og_img:
            result["profile_pic_url"] = og_img.get("content")

        if og_desc:
            desc = og_desc.get("content", "")
            m = re.search(r"([\d,]+)\s+followers?", desc, re.I)
            if m: result["followers"] = m.group(1)

        # Title tag
        title = soup.find("title")
        if title and not result["display_name"]:
            result["display_name"] = title.get_text().replace("| Spotify", "").replace("| Listen on Spotify", "").strip()
            if result["display_name"]: result["found"] = True

    except Exception as e:
        result["error"] = str(e)
        return result

    # 2. Public playlists (ayrı istek)
    if result.get("found"):
        try:
            pl_url = f"https://open.spotify.com/user/{username}/playlists"
            pl_resp = requests.get(pl_url, headers=HEADERS, timeout=10)
            if pl_resp.status_code == 200:
                pl_soup = BeautifulSoup(pl_resp.text, "html.parser")
                playlists = []

                # JSON extraction
                pl_next = pl_soup.find("script", id="__NEXT_DATA__")
                if pl_next:
                    try:
                        pl_data = json.loads(pl_next.string)
                        entities = pl_data.get("props", {}).get("pageProps", {}).get("state", {}).get("entities", {})
                        for pid, pl in entities.get("playlists", {}).get("byId", {}).items():
                            playlists.append({
                                "name": pl.get("name"),
                                "track_count": pl.get("tracks", {}).get("total"),
                                "url": f"https://open.spotify.com/playlist/{pid}",
                                "public": pl.get("public", True),
                            })
                    except Exception:
                        pass

                result["public_playlists"] = playlists[:10]
                result["playlist_count"] = len(playlists)

        except Exception:
            pass

    return result


def scrape_spotify_artist(artist_id_or_url: str) -> dict:
    """Spotify artist profili (sanatçı sayfası)."""
    artist_id = _extract_username_from_url(artist_id_or_url)

    result = {
        "artist_id": artist_id,
        "found": False,
        "profile_url": f"https://open.spotify.com/artist/{artist_id}",
        "name": None,
        "genres": [],
        "followers": None,
        "monthly_listeners": None,
        "profile_pic_url": None,
        "error": None,
    }

    try:
        url = f"https://open.spotify.com/artist/{artist_id}"
        resp = requests.get(url, headers=HEADERS, timeout=12)

        if resp.status_code == 200:
            html = resp.text
            soup = BeautifulSoup(html, "html.parser")

            og_title = soup.find("meta", property="og:title")
            og_img   = soup.find("meta", property="og:image")
            og_desc  = soup.find("meta", property="og:description")

            if og_title:
                result["found"] = True
                result["name"] = og_title.get("content", "").replace(" | Spotify", "").strip()

            if og_img:
                result["profile_pic_url"] = og_img.get("content")

            if og_desc:
                desc = og_desc.get("content", "")
                m = re.search(r"([\d,.]+[KkMm]?)\s+monthly listeners", desc, re.I)
                if m: result["monthly_listeners"] = m.group(1)

    except Exception as e:
        result["error"] = str(e)

    return result
