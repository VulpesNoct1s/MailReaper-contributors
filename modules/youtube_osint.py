"""
MailReaper - YouTube OSINT
Channel analizi — RSS feed + HTML kazıma, API key yok
"""
import re
import json
import requests
import xml.etree.ElementTree as ET
from urllib.parse import quote, urlparse

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _extract_channel_id(handle_or_url: str) -> str | None:
    """Handle veya URL'den channel ID/handle çıkarır."""
    handle_or_url = handle_or_url.strip()
    # youtube.com/@handle
    m = re.search(r"youtube\.com/@([^/?&\s]+)", handle_or_url)
    if m: return f"@{m.group(1)}"
    # youtube.com/channel/UC...
    m = re.search(r"youtube\.com/channel/([^/?&\s]+)", handle_or_url)
    if m: return m.group(1)
    # youtube.com/user/...
    m = re.search(r"youtube\.com/user/([^/?&\s]+)", handle_or_url)
    if m: return m.group(1)
    # youtube.com/c/...
    m = re.search(r"youtube\.com/c/([^/?&\s]+)", handle_or_url)
    if m: return m.group(1)
    # @handle
    if handle_or_url.startswith("@"):
        return handle_or_url
    # Düz handle
    return f"@{handle_or_url}"


def _get_rss_videos(channel_id: str) -> list:
    """YouTube RSS feed'inden son videoları çeker."""
    # channel ID ile RSS
    if channel_id.startswith("UC"):
        rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    else:
        return []

    try:
        resp = requests.get(rss_url, headers=HEADERS, timeout=10)
        if resp.status_code != 200:
            return []

        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/", "yt": "http://www.youtube.com/xml/schemas/2015"}
        videos = []
        for entry in root.findall("atom:entry", ns)[:10]:
            video = {}
            title = entry.find("atom:title", ns)
            vid_id = entry.find("yt:videoId", ns)
            published = entry.find("atom:published", ns)
            views_el = entry.find(".//yt:statistics", ns)
            likes_el = entry.find(".//media:community/media:starRating", ns)

            if title:    video["title"]     = title.text
            if vid_id:   video["video_id"]  = vid_id.text
            if vid_id:   video["url"]       = f"https://www.youtube.com/watch?v={vid_id.text}"
            if published: video["published"] = published.text[:10]
            if views_el: video["views"]     = views_el.get("views", "")

            thumbnail_el = entry.find(".//media:thumbnail", ns)
            if thumbnail_el: video["thumbnail"] = thumbnail_el.get("url", "")

            videos.append(video)
        return videos
    except Exception:
        return []


def scrape_youtube(handle_or_url: str) -> dict:
    handle = _extract_channel_id(handle_or_url)
    display_handle = handle

    result = {
        "input": handle_or_url,
        "handle": handle,
        "found": False,
        "channel_url": f"https://www.youtube.com/{handle}" if handle else None,
        "channel_id": None,
        "name": None,
        "description": None,
        "subscriber_count": None,
        "video_count": None,
        "view_count": None,
        "country": None,
        "profile_pic_url": None,
        "banner_url": None,
        "links": [],
        "keywords": [],
        "recent_videos": [],
        "created": None,
        "is_verified": False,
        "error": None,
    }

    try:
        url = f"https://www.youtube.com/{handle}"
        resp = requests.get(url, headers=HEADERS, timeout=12)
        if resp.status_code == 404:
            result["error"] = "Kanal bulunamadı"
            return result

        if resp.status_code != 200:
            result["error"] = f"HTTP {resp.status_code}"
            return result

        html = resp.text

        # ytInitialData içinden JSON çıkar
        m = re.search(r'var ytInitialData\s*=\s*(\{.+?\});\s*</script>', html, re.DOTALL)
        if not m:
            m = re.search(r'ytInitialData\s*=\s*(\{.+?\})\s*;', html, re.DOTALL)

        if m:
            try:
                yt_data = json.loads(m.group(1))
                result["found"] = True

                # Channel metadata
                header = (
                    yt_data.get("header", {})
                    .get("c4TabbedHeaderRenderer", {})
                )
                if not header:
                    header = yt_data.get("header", {}).get("pageHeaderRenderer", {})

                name = header.get("title", "")
                if not name:
                    # Try alternative path
                    try:
                        name = yt_data["metadata"]["channelMetadataRenderer"]["title"]
                    except Exception:
                        pass
                result["name"] = name

                # Subscriber count
                sub_text = header.get("subscriberCountText", {})
                if isinstance(sub_text, dict):
                    run = sub_text.get("simpleText") or sub_text.get("runs", [{}])[0].get("text", "")
                    result["subscriber_count"] = run
                elif isinstance(sub_text, str):
                    result["subscriber_count"] = sub_text

                # Channel ID
                try:
                    result["channel_id"] = yt_data["metadata"]["channelMetadataRenderer"]["externalId"]
                except Exception:
                    pass

                # Description
                try:
                    result["description"] = yt_data["metadata"]["channelMetadataRenderer"]["description"]
                except Exception:
                    pass

                # Country
                try:
                    result["country"] = yt_data["metadata"]["channelMetadataRenderer"]["country"]
                except Exception:
                    pass

                # Keywords
                try:
                    kws = yt_data["metadata"]["channelMetadataRenderer"]["keywords"]
                    result["keywords"] = kws.split() if isinstance(kws, str) else kws
                except Exception:
                    pass

                # Profile pic
                try:
                    thumbnails = header.get("avatar", {}).get("thumbnails", [])
                    if not thumbnails:
                        thumbnails = yt_data["metadata"]["channelMetadataRenderer"].get("avatar", {}).get("thumbnails", [])
                    if thumbnails:
                        result["profile_pic_url"] = thumbnails[-1].get("url")
                except Exception:
                    pass

                # Banner
                try:
                    banner = header.get("banner", {}).get("thumbnails", [])
                    if banner:
                        result["banner_url"] = banner[-1].get("url")
                except Exception:
                    pass

                # Links
                try:
                    header_links = header.get("headerLinks", {}).get("channelHeaderLinksViewModel", {})
                    for link_group in [header_links.get("firstLink", {}), *header_links.get("moreEndpoint", {}).values()]:
                        if isinstance(link_group, dict):
                            url_ep = link_group.get("commandRuns", [{}])[0].get("onTap", {}).get("innertubeCommand", {}).get("urlEndpoint", {})
                            if url_ep.get("url"):
                                result["links"].append(url_ep["url"])
                except Exception:
                    pass

            except Exception as e:
                result["error"] = f"JSON parse hatası: {e}"

        # OG meta fallback
        if not result["name"]:
            og_title = re.search(r'<meta property="og:title" content="([^"]+)"', html)
            og_img   = re.search(r'<meta property="og:image" content="([^"]+)"', html)
            if og_title:
                result["name"] = og_title.group(1)
                result["found"] = True
            if og_img:
                result["profile_pic_url"] = og_img.group(1)

        # RSS videos (eğer channel ID varsa)
        if result.get("channel_id"):
            result["recent_videos"] = _get_rss_videos(result["channel_id"])

    except Exception as e:
        result["error"] = str(e)

    return result
