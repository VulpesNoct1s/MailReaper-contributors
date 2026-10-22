"""
MailReaper - Correlation Engine
Tüm modüllerin bulgularını çapraz referanslar ve ilişki haritası çıkartır.
"""

from datetime import datetime


def correlate(results: dict) -> dict:
    """
    Tüm OSINT bulgularını analiz eder, çapraz ilişkiler bulur
    ve birleşik bir profil sentezler.
    """
    corr = {
        "identified_names": [],
        "identified_locations": [],
        "identified_languages": [],
        "identified_platforms": [],
        "identified_usernames": [],
        "identified_domains": [],
        "identified_emails": [],
        "identified_orgs": [],
        "avatar_urls": [],
        "timeline": [],
        "connections": [],   # Platform çiftleri arası bağlantılar
        "confidence": {},    # Her bulgu için güven skoru (0-100)
        "summary": "",
    }

    # ─── İSİM TOPLAMA ───
    names = set()
    locations = set()
    orgs = set()
    usernames = set()
    domains = set()
    emails_found = set()
    platforms = set()
    langs = set()
    avatars = []
    timeline_events = []

    # Email validator
    ev = results.get("email_validator", {})
    if ev.get("email"):
        emails_found.add(ev["email"])

    # Email parts
    ep = results.get("email_parts", {})
    if ep.get("domain"):
        domains.add(ep["domain"])

    # Gravatar
    gr = results.get("gravatar", {})
    if gr.get("display_name"):
        names.add(gr["display_name"])
    if gr.get("location"):
        locations.add(gr["location"])
    if gr.get("avatar_url"):
        avatars.append({"source": "Gravatar", "url": gr["avatar_url"]})
    if gr.get("has_gravatar"):
        platforms.add("Gravatar")
        timeline_events.append({
            "source": "Gravatar",
            "event": "Gravatar profili mevcut",
            "date": None,
        })
    for acc in gr.get("accounts", []):
        if acc.get("shortname"):
            platforms.add(acc["shortname"].capitalize())

    # GitHub
    gh = results.get("github_search", {})
    gh_user = gh.get("github_user") or {}
    if gh_user:
        platforms.add("GitHub")
        if gh_user.get("name"):
            names.add(gh_user["name"])
        if gh_user.get("location"):
            locations.add(gh_user["location"])
        if gh_user.get("company"):
            orgs.add(gh_user["company"].lstrip("@"))
        if gh_user.get("login"):
            usernames.add(gh_user["login"])
        if gh_user.get("email"):
            emails_found.add(gh_user["email"])
        if gh_user.get("avatar_url"):
            avatars.append({"source": "GitHub", "url": gh_user["avatar_url"]})
        if gh_user.get("created_at"):
            timeline_events.append({
                "source": "GitHub",
                "event": f"@{gh_user.get('login','')} hesabı oluşturuldu",
                "date": gh_user["created_at"][:10],
            })

    # GitHub deep
    gh_deep = results.get("github_deep", {})
    if gh_deep.get("found"):
        p = gh_deep.get("profile", {})
        if p.get("email"):
            emails_found.add(p["email"])
        if p.get("twitter_username"):
            usernames.add(p["twitter_username"])
        for lang in gh_deep.get("languages", {}):
            langs.add(lang)
        for org in gh_deep.get("orgs", []):
            if org.get("login"):
                orgs.add(org["login"])

    # Reddit
    reddit = results.get("reddit", {})
    if reddit.get("found"):
        platforms.add("Reddit")
        rp = reddit.get("profile", {})
        if rp.get("username"):
            usernames.add(rp["username"])
        if rp.get("icon_img"):
            avatars.append({"source": "Reddit", "url": rp["icon_img"]})
        if rp.get("created_utc"):
            timeline_events.append({
                "source": "Reddit",
                "event": f"Reddit u/{rp.get('username','')} hesabı oluşturuldu",
                "date": rp["created_utc"],
            })
        for sub in reddit.get("subreddits", [])[:10]:
            if sub:
                platforms.add(f"r/{sub}")

    # HackerNews
    hn = results.get("hackernews", {})
    if hn.get("found"):
        platforms.add("HackerNews")
        hp = hn.get("profile", {})
        if hp.get("username"):
            usernames.add(hp["username"])
        if hp.get("created"):
            timeline_events.append({
                "source": "HackerNews",
                "event": f"HN hesabı oluşturuldu",
                "date": hp["created"],
            })

    # Social media (simple check)
    social = results.get("social", {})
    for found_p in social.get("found", []):
        platforms.add(found_p["platform"])

    # Username OSINT
    un_osint = results.get("username_osint", {})
    for found_p in un_osint.get("found", []):
        platforms.add(found_p["platform"])

    # DNS/WHOIS
    dns = results.get("dns_analysis", {})
    whois = dns.get("whois", {}) if dns else {}
    if whois:
        if whois.get("org"):
            orgs.add(whois["org"])
        if whois.get("registrant_name"):
            names.add(whois["registrant_name"])
        for e in (whois.get("emails") or []):
            emails_found.add(e)
        if whois.get("country"):
            locations.add(f"Country: {whois['country']}")

    # crt.sh
    crt = results.get("crt_search", {})
    if crt:
        for entry in crt.get("email_results", {}).get("entries", [])[:5]:
            n = entry.get("name", "")
            if n and not n.startswith("*"):
                domains.add(n)

    # Username generator
    ug = results.get("username_gen", {})
    if ug.get("local_part"):
        usernames.add(ug["local_part"])

    # ─── CONNECTIONS (çapraz ilişkiler) ───
    connections = []

    # Aynı isim birden fazla kaynakta mı?
    for name in names:
        sources = []
        if gh_user.get("name") == name: sources.append("GitHub")
        if gr.get("display_name") == name: sources.append("Gravatar")
        if whois.get("registrant_name") == name: sources.append("WHOIS")
        if len(sources) > 1:
            connections.append({
                "type": "name_match",
                "value": name,
                "sources": sources,
                "confidence": 85,
                "description": f"'{name}' ismi {', '.join(sources)}'da eşleşti",
            })

    # Aynı username birden fazla yerde mi?
    for u in usernames:
        found_in = []
        if gh_user.get("login") == u: found_in.append("GitHub")
        if reddit.get("profile", {}).get("username") == u: found_in.append("Reddit")
        if hn.get("profile", {}).get("username") == u: found_in.append("HackerNews")
        for p in social.get("found", []):
            if u.lower() in p.get("url", "").lower(): found_in.append(p["platform"])
        for p in un_osint.get("found", []):
            if u.lower() in p.get("url", "").lower(): found_in.append(p["platform"])
        if len(found_in) > 1:
            found_in = list(set(found_in))
            connections.append({
                "type": "username_match",
                "value": u,
                "sources": found_in,
                "confidence": 90,
                "description": f"'{u}' kullanıcı adı {len(found_in)} platformda bulundu: {', '.join(found_in[:5])}",
            })

    # ─── TİMLİNE SİRALA ───
    def parse_date(d):
        if not d: return datetime(1900, 1, 1)
        try:
            return datetime.fromisoformat(d.replace("Z", "+00:00"))
        except Exception:
            try:
                return datetime.strptime(d[:10], "%Y-%m-%d")
            except Exception:
                return datetime(1900, 1, 1)

    timeline_events.sort(key=lambda x: parse_date(x.get("date")))

    # ─── ÖZET METIN ───
    parts = []
    if names:
        parts.append(f"Tespit edilen isim(ler): {', '.join(list(names)[:3])}")
    if usernames:
        parts.append(f"Kullanıcı adları: {', '.join(list(usernames)[:5])}")
    if locations:
        parts.append(f"Konum: {', '.join(list(locations)[:3])}")
    if orgs:
        parts.append(f"Organizasyon: {', '.join(list(orgs)[:3])}")
    if platforms:
        parts.append(f"{len(platforms)} platformda varlık tespit edildi")
    if len(emails_found) > 1:
        parts.append(f"Bağlantılı email: {', '.join(list(emails_found - {ep.get('email','')})[:3])}")

    corr["summary"] = " | ".join(parts) if parts else "Birleşik profil oluşturulamadı — yeterli veri bulunamadı."
    corr["identified_names"] = sorted(list(names))
    corr["identified_locations"] = sorted(list(locations))
    corr["identified_languages"] = sorted(list(langs))
    corr["identified_platforms"] = sorted(list(platforms))
    corr["identified_usernames"] = sorted(list(usernames))
    corr["identified_domains"] = sorted(list(domains))
    corr["identified_emails"] = sorted(list(emails_found))
    corr["identified_orgs"] = sorted(list(orgs))
    corr["avatar_urls"] = avatars
    corr["timeline"] = timeline_events
    corr["connections"] = connections

    # Güven skorları
    corr["confidence"] = {
        "name":     min(100, len(names) * 30 + len(connections) * 10),
        "location": min(100, len(locations) * 40),
        "platform": min(100, len(platforms) * 5),
        "username": min(100, len(usernames) * 20 + len(connections) * 15),
    }

    # Network graph verisi (D3.js için)
    nodes = []
    edges = []
    seen_nodes = set()

    def add_node(id_, label, group, url=None):
        if id_ not in seen_nodes:
            seen_nodes.add(id_)
            nodes.append({"id": id_, "label": label, "group": group, "url": url})

    # Merkez node: email veya username
    center_id = ep.get("email") or list(usernames)[0] if usernames else "target"
    add_node(center_id, center_id, "center")

    for name in list(names)[:5]:
        add_node(f"name_{name}", name, "name")
        edges.append({"source": center_id, "target": f"name_{name}", "label": "name"})

    for plat in list(platforms)[:15]:
        add_node(f"plat_{plat}", plat, "platform")
        edges.append({"source": center_id, "target": f"plat_{plat}", "label": "active_on"})

    for u in list(usernames)[:5]:
        if u != center_id:
            add_node(f"user_{u}", u, "username")
            edges.append({"source": center_id, "target": f"user_{u}", "label": "alias"})

    for loc in list(locations)[:3]:
        add_node(f"loc_{loc}", loc, "location")
        edges.append({"source": center_id, "target": f"loc_{loc}", "label": "located"})

    for org in list(orgs)[:3]:
        add_node(f"org_{org}", org, "org")
        edges.append({"source": center_id, "target": f"org_{org}", "label": "affiliated"})

    corr["graph"] = {"nodes": nodes, "edges": edges}

    return corr
