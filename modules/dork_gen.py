"""
MailReaper - Google Dork Generator
Hedef hakkında yapılandırılmış arama sorguları üretir.
Tamamen yerel hesaplama, API yok.
"""

from urllib.parse import quote


def generate_dorks(email: str = None, username: str = None, name: str = None, domain: str = None) -> dict:
    """
    Verilen bilgilere göre hazır dork sorguları üretir.
    Google, Bing, GitHub, Shodan ve daha fazlası için.
    """
    result = {
        "google": [],
        "bing": [],
        "github": [],
        "shodan": [],
        "paste_dorks": [],
        "dark_dorks": [],
        "specialized": [],
        "all_queries": [],
    }

    # ─── GOOGLE DORKS ───
    google = []

    if email:
        google += [
            {"label": "Email direkt arama",        "query": f'"{email}"'},
            {"label": "Email + şifre leak",         "query": f'"{email}" "password" OR "passwd" OR "pwd"'},
            {"label": "Email + telefon",            "query": f'"{email}" "phone" OR "tel" OR "mobile"'},
            {"label": "Email paste siteleri",       "query": f'site:pastebin.com OR site:paste.ee OR site:ghostbin.co "{email}"'},
            {"label": "Email PDF/DOC'larda",        "query": f'"{email}" filetype:pdf OR filetype:doc OR filetype:xls'},
            {"label": "Email forum postları",       "query": f'"{email}" site:reddit.com OR site:forum OR site:community'},
            {"label": "Email LinkedIn",             "query": f'site:linkedin.com "{email}"'},
            {"label": "Email GitHub",               "query": f'site:github.com "{email}"'},
            {"label": "Email CV/özgeçmiş",          "query": f'"{email}" "resume" OR "cv" OR "özgeçmiş" filetype:pdf'},
            {"label": "Email sosyal medya",         "query": f'"{email}" site:twitter.com OR site:instagram.com OR site:facebook.com'},
        ]

    if username:
        google += [
            {"label": "Username direkt arama",      "query": f'"{username}"'},
            {"label": "Username sosyal medya",      "query": f'"{username}" site:twitter.com OR site:instagram.com OR site:reddit.com OR site:github.com'},
            {"label": "Username profil sayfaları",  "query": f'inurl:"{username}" profile OR user OR about'},
            {"label": "Username paste/leak",        "query": f'"{username}" site:pastebin.com OR site:paste.ee'},
            {"label": "Username + email ilişkisi",  "query": f'"{username}" "@gmail.com" OR "@yahoo.com" OR "@hotmail.com"'},
            {"label": "Username forum",             "query": f'"{username}" inurl:forum OR inurl:community OR inurl:thread'},
            {"label": "Username Discord",           "query": f'"{username}#" site:discord.com OR "discord.gg"'},
            {"label": "Username Steam/gaming",      "query": f'"{username}" site:steamcommunity.com OR site:faceit.com OR site:op.gg'},
        ]

    if name:
        google += [
            {"label": "İsim direkt",               "query": f'"{name}"'},
            {"label": "İsim + LinkedIn",            "query": f'site:linkedin.com/in "{name}"'},
            {"label": "İsim + sosyal medya",        "query": f'"{name}" site:twitter.com OR site:instagram.com OR site:facebook.com'},
            {"label": "İsim + email",               "query": f'"{name}" "@gmail.com" OR "@yahoo.com" OR "@outlook.com"'},
            {"label": "İsim + konum",               "query": f'"{name}" "Turkey" OR "Türkiye" OR "Istanbul" OR "Ankara"'},
            {"label": "İsim + özgeçmiş/CV",         "query": f'"{name}" filetype:pdf "resume" OR "cv"'},
            {"label": "İsim + telefon",             "query": f'"{name}" "+90" OR "0212" OR "0532" OR "0546"'},
        ]

    if domain:
        google += [
            {"label": "Domain çalışanları",         "query": f'site:linkedin.com "@{domain}"'},
            {"label": "Domain email pattern",       "query": f'"@{domain}" filetype:pdf OR filetype:xls OR filetype:csv'},
            {"label": "Domain admin/login",         "query": f'site:{domain} inurl:admin OR inurl:login OR inurl:dashboard'},
            {"label": "Domain yapılandırma",        "query": f'site:{domain} ext:env OR ext:config OR ext:xml OR ext:yml'},
            {"label": "Domain açık dizinler",       "query": f'site:{domain} intitle:"index of"'},
            {"label": "Domain GitHub kod",          "query": f'site:github.com "{domain}"'},
            {"label": "Domain paste leak",          "query": f'site:pastebin.com "{domain}"'},
            {"label": "Domain subdomainler",        "query": f'site:*.{domain}'},
            {"label": "Domain eski sürümler",       "query": f'site:web.archive.org "{domain}"'},
            {"label": "Domain çalışan isimleri",    "query": f'"@{domain}" "name:" OR "contact:" OR "from:"'},
        ]

    result["google"] = google

    # ─── GITHUB DORKS ───
    github = []
    if email:
        github += [
            {"label": "Email commit geçmişi",  "query": f"https://github.com/search?q={quote(email)}&type=commits"},
            {"label": "Email kod içinde",      "query": f'https://github.com/search?q="{quote(email)}"&type=code'},
            {"label": "Email issue/PR",        "query": f'https://github.com/search?q="{quote(email)}"&type=issues'},
        ]
    if username:
        github += [
            {"label": "Username profili",      "query": f"https://github.com/{username}"},
            {"label": "Username kod içinde",   "query": f'https://github.com/search?q="{quote(username)}"&type=code'},
        ]
    if domain:
        github += [
            {"label": "Domain kod içinde",     "query": f'https://github.com/search?q="{quote(domain)}"&type=code'},
            {"label": "Domain API key leak",   "query": f'https://github.com/search?q="{quote(domain)}" AND "api_key" OR "secret" OR "password"&type=code'},
        ]
    result["github"] = github

    # ─── PASTE DORKS ───
    paste = []
    targets = []
    if email: targets.append(email)
    if username: targets.append(username)

    for t in targets:
        paste += [
            {"label": f"psbdmp (Pastebin index)",  "url": f"https://psbdmp.ws/api/v3/search/{quote(t)}"},
            {"label": "IntelX",                    "url": f"https://intelx.io/?s={quote(t)}"},
            {"label": "paste.ee",                  "url": f"https://paste.ee/search?q={quote(t)}"},
            {"label": "Pastebin Google",           "url": f'https://www.google.com/search?q=site:pastebin.com+"{quote(t)}"'},
            {"label": "Riseup pad",                "url": f'https://www.google.com/search?q=site:pad.riseup.net+"{quote(t)}"'},
        ]
    result["paste_dorks"] = paste

    # ─── SHODAN ───
    shodan = []
    if domain:
        shodan += [
            {"label": "Domain Shodan",     "url": f"https://www.shodan.io/search?query={quote(domain)}"},
            {"label": "Domain Census",     "url": f"https://search.censys.io/search?resource=hosts&q={quote(domain)}"},
            {"label": "FOFA Search",       "url": f"https://fofa.info/result?qbase64={quote(domain)}"},
        ]
        if email:
            shodan.append({"label": "Email Shodan", "url": f"https://www.shodan.io/search?query={quote(email)}"})
    result["shodan"] = shodan

    # ─── SPECİALİZED ───
    specialized = []
    for t in targets:
        specialized += [
            {"label": "Dehashed",          "url": f"https://dehashed.com/search?query={quote(t)}"},
            {"label": "Leakcheck",         "url": f"https://leakcheck.io/search?query={quote(t)}"},
            {"label": "SnusBase",          "url": f"https://snusbase.com/"},
            {"label": "Spycloud",          "url": f"https://spycloud.com/"},
            {"label": "IntelX Files",      "url": f"https://intelx.io/tools?tab=document&s={quote(t)}"},
            {"label": "Google Cache",      "url": f'https://webcache.googleusercontent.com/search?q=cache:"{quote(t)}"'},
            {"label": "Bing",              "url": f'https://www.bing.com/search?q="{quote(t)}"'},
            {"label": "DuckDuckGo",        "url": f'https://duckduckgo.com/?q="{quote(t)}"'},
            {"label": "Yandex",            "url": f'https://yandex.com/search/?text="{quote(t)}"'},
        ]
    result["specialized"] = specialized

    # ─── BING DORKS ───
    bing = []
    if email:
        bing += [
            {"label": "Email Bing",        "query": f'"{email}"'},
            {"label": "Email + leak",      "query": f'"{email}" password'},
        ]
    if username:
        bing += [
            {"label": "Username Bing",     "query": f'"{username}"'},
        ]
    result["bing"] = bing

    # Tüm sorguları birleştir
    all_q = []
    for category, items in result.items():
        if category == "all_queries": continue
        for item in items:
            if isinstance(item, dict):
                if "query" in item:
                    all_q.append({
                        "category": category,
                        "label": item.get("label", ""),
                        "query": item.get("query", ""),
                        "google_url": f"https://www.google.com/search?q={quote(item.get('query',''))}",
                    })
                elif "url" in item:
                    all_q.append({
                        "category": category,
                        "label": item.get("label", ""),
                        "url": item.get("url", ""),
                    })
    result["all_queries"] = all_q

    return result
