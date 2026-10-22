"""
MailReaper - Phone Number OSINT
Telefon numarası analizi: ülke, operatör, format, dorklar
Tamamen yerel — API key gerektirmez
"""
import re
from urllib.parse import quote

# Uluslararası telefon prefix veritabanı (prefix → {country, iso2, carriers})
PHONE_PREFIXES = {
    "+1":   {"country": "USA/Canada", "iso2": "US/CA", "carriers": ["AT&T","Verizon","T-Mobile","Rogers","Bell"]},
    "+7":   {"country": "Russia/Kazakhstan", "iso2": "RU/KZ", "carriers": ["MTS","Beeline","MegaFon","Tele2"]},
    "+20":  {"country": "Egypt", "iso2": "EG", "carriers": ["Vodafone Egypt","Orange Egypt","Etisalat Egypt"]},
    "+27":  {"country": "South Africa", "iso2": "ZA", "carriers": ["Vodacom","MTN","Cell C","Telkom"]},
    "+30":  {"country": "Greece", "iso2": "GR", "carriers": ["Cosmote","Vodafone GR","Wind Hellas"]},
    "+31":  {"country": "Netherlands", "iso2": "NL", "carriers": ["KPN","Vodafone NL","T-Mobile NL"]},
    "+32":  {"country": "Belgium", "iso2": "BE", "carriers": ["Proximus","Orange BE","Base"]},
    "+33":  {"country": "France", "iso2": "FR", "carriers": ["Orange","SFR","Free Mobile","Bouygues"]},
    "+34":  {"country": "Spain", "iso2": "ES", "carriers": ["Movistar","Vodafone ES","Orange ES","MásMóvil"]},
    "+36":  {"country": "Hungary", "iso2": "HU", "carriers": ["Magyar Telekom","Vodafone HU","Telenor HU"]},
    "+39":  {"country": "Italy", "iso2": "IT", "carriers": ["TIM","Vodafone IT","Wind Tre","Iliad IT"]},
    "+40":  {"country": "Romania", "iso2": "RO", "carriers": ["Orange RO","Vodafone RO","Telekom RO"]},
    "+41":  {"country": "Switzerland", "iso2": "CH", "carriers": ["Swisscom","Sunrise","Salt"]},
    "+43":  {"country": "Austria", "iso2": "AT", "carriers": ["A1 Telekom","Magenta AT","Drei"]},
    "+44":  {"country": "United Kingdom", "iso2": "GB", "carriers": ["EE","O2","Vodafone UK","Three UK"]},
    "+45":  {"country": "Denmark", "iso2": "DK", "carriers": ["TDC","Telenor DK","Telia DK","3 DK"]},
    "+46":  {"country": "Sweden", "iso2": "SE", "carriers": ["Telia SE","Tele2 SE","Telenor SE","3 SE"]},
    "+47":  {"country": "Norway", "iso2": "NO", "carriers": ["Telenor NO","Telia NO","Ice"]},
    "+48":  {"country": "Poland", "iso2": "PL", "carriers": ["Orange PL","Play","T-Mobile PL","Plus"]},
    "+49":  {"country": "Germany", "iso2": "DE", "carriers": ["Deutsche Telekom","Vodafone DE","O2 DE","Drillisch"]},
    "+51":  {"country": "Peru", "iso2": "PE", "carriers": ["Movistar PE","Claro PE","Entel PE"]},
    "+52":  {"country": "Mexico", "iso2": "MX", "carriers": ["Telcel","Movistar MX","AT&T MX"]},
    "+54":  {"country": "Argentina", "iso2": "AR", "carriers": ["Claro AR","Movistar AR","Personal"]},
    "+55":  {"country": "Brazil", "iso2": "BR", "carriers": ["Vivo","Claro BR","TIM BR","Oi"]},
    "+56":  {"country": "Chile", "iso2": "CL", "carriers": ["Entel CL","Claro CL","Movistar CL"]},
    "+57":  {"country": "Colombia", "iso2": "CO", "carriers": ["Claro CO","Movistar CO","Tigo CO"]},
    "+58":  {"country": "Venezuela", "iso2": "VE", "carriers": ["Movistar VE","Digitel","Movilnet"]},
    "+60":  {"country": "Malaysia", "iso2": "MY", "carriers": ["Celcom","Digi","Maxis","U Mobile"]},
    "+61":  {"country": "Australia", "iso2": "AU", "carriers": ["Telstra","Optus","Vodafone AU"]},
    "+62":  {"country": "Indonesia", "iso2": "ID", "carriers": ["Telkomsel","Indosat","XL Axiata","Tri ID"]},
    "+63":  {"country": "Philippines", "iso2": "PH", "carriers": ["Globe","Smart","DITO"]},
    "+64":  {"country": "New Zealand", "iso2": "NZ", "carriers": ["Spark NZ","One NZ","2degrees"]},
    "+65":  {"country": "Singapore", "iso2": "SG", "carriers": ["Singtel","StarHub","M1"]},
    "+66":  {"country": "Thailand", "iso2": "TH", "carriers": ["AIS","DTAC","True Move"]},
    "+81":  {"country": "Japan", "iso2": "JP", "carriers": ["NTT Docomo","SoftBank","au KDDI"]},
    "+82":  {"country": "South Korea", "iso2": "KR", "carriers": ["SK Telecom","KT","LG Uplus"]},
    "+84":  {"country": "Vietnam", "iso2": "VN", "carriers": ["Viettel","Mobifone","Vinaphone"]},
    "+86":  {"country": "China", "iso2": "CN", "carriers": ["China Mobile","China Unicom","China Telecom"]},
    "+90":  {"country": "Turkey", "iso2": "TR", "carriers": ["Turkcell","Vodafone TR","Türk Telekom"]},
    "+91":  {"country": "India", "iso2": "IN", "carriers": ["Jio","Airtel","Vi (Vodafone-Idea)","BSNL"]},
    "+92":  {"country": "Pakistan", "iso2": "PK", "carriers": ["Jazz","Telenor PK","Ufone","Zong"]},
    "+93":  {"country": "Afghanistan", "iso2": "AF", "carriers": ["Afghan Telecom","Roshan","Etisalat AF"]},
    "+94":  {"country": "Sri Lanka", "iso2": "LK", "carriers": ["Dialog","Mobitel","Hutch LK"]},
    "+95":  {"country": "Myanmar", "iso2": "MM", "carriers": ["Mytel","MPT","Ooredoo MM","Telenor MM"]},
    "+98":  {"country": "Iran", "iso2": "IR", "carriers": ["Hamrahe Avval","Irancell","RighTel"]},
    "+212": {"country": "Morocco", "iso2": "MA", "carriers": ["Maroc Telecom","Orange MA","Inwi"]},
    "+213": {"country": "Algeria", "iso2": "DZ", "carriers": ["Mobilis","Djezzy","Ooredoo DZ"]},
    "+216": {"country": "Tunisia", "iso2": "TN", "carriers": ["Tunisie Telecom","Ooredoo TN","Orange TN"]},
    "+218": {"country": "Libya", "iso2": "LY", "carriers": ["Libyana","Al-Madar"]},
    "+220": {"country": "Gambia", "iso2": "GM", "carriers": ["Africell GM","Gamcel","QCell"]},
    "+234": {"country": "Nigeria", "iso2": "NG", "carriers": ["MTN NG","Glo Mobile","Airtel NG","9mobile"]},
    "+254": {"country": "Kenya", "iso2": "KE", "carriers": ["Safaricom","Airtel KE","Telkom KE"]},
    "+966": {"country": "Saudi Arabia", "iso2": "SA", "carriers": ["STC","Mobily","Zain SA"]},
    "+971": {"country": "UAE", "iso2": "AE", "carriers": ["du","Etisalat AE"]},
    "+972": {"country": "Israel", "iso2": "IL", "carriers": ["Cellcom","Partner","Hot Mobile","Golan Telecom"]},
    "+974": {"country": "Qatar", "iso2": "QA", "carriers": ["Ooredoo QA","Vodafone QA"]},
    "+380": {"country": "Ukraine", "iso2": "UA", "carriers": ["Kyivstar","Vodafone UA","lifecell"]},
    "+381": {"country": "Serbia", "iso2": "RS", "carriers": ["Telekom Srbija","Telenor RS","vip RS"]},
    "+385": {"country": "Croatia", "iso2": "HR", "carriers": ["HT","A1 HR","Tele2 HR"]},
    "+420": {"country": "Czech Republic", "iso2": "CZ", "carriers": ["T-Mobile CZ","Vodafone CZ","O2 CZ"]},
    "+421": {"country": "Slovakia", "iso2": "SK", "carriers": ["Slovak Telekom","Orange SK","O2 SK"]},
    "+886": {"country": "Taiwan", "iso2": "TW", "carriers": ["Chunghwa Telecom","FarEasTone","Taiwan Mobile"]},
}


def _normalize_phone(phone: str) -> str:
    """Telefon numarasını normalize eder."""
    # Sadece +, rakamlar
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    # Başında 00 varsa + yap
    if cleaned.startswith("00"):
        cleaned = "+" + cleaned[2:]
    # Başında + yoksa ve 10-12 rakam varsa, olduğu gibi bırak
    return cleaned


def _find_prefix(phone_normalized: str) -> tuple[str, dict] | tuple[None, None]:
    """Uluslararası prefix'i tespit eder."""
    if not phone_normalized.startswith("+"):
        return None, None
    # En uzun prefix eşleşmesini bul (4, 3, 2, 1 basamak)
    for length in (4, 3, 2, 1):
        prefix = phone_normalized[:length+1]  # +90 → length=2, prefix="+90"
        prefix = "+" + phone_normalized[1:length+1]
        if prefix in PHONE_PREFIXES:
            return prefix, PHONE_PREFIXES[prefix]
    return None, None


def analyze_phone(phone: str) -> dict:
    """
    Telefon numarasını analiz eder.
    Ülke, operatör tahmini, format varyasyonları ve dorklar üretir.
    """
    original = phone.strip()
    normalized = _normalize_phone(original)

    result = {
        "original": original,
        "normalized": normalized,
        "country": None,
        "iso2": None,
        "possible_carriers": [],
        "is_mobile": None,
        "formats": {},
        "dork_links": [],
        "search_links": [],
        "valid_format": False,
        "error": None,
    }

    # Temel doğrulama
    digits_only = re.sub(r"\D", "", normalized)
    if len(digits_only) < 7 or len(digits_only) > 15:
        result["error"] = "Geçersiz uzunluk (7-15 rakam olmalı)"
        return result

    result["valid_format"] = True

    # Prefix tespiti
    prefix, prefix_info = _find_prefix(normalized)
    if prefix_info:
        result["country"]           = prefix_info["country"]
        result["iso2"]              = prefix_info["iso2"]
        result["possible_carriers"] = prefix_info["carriers"]

        # TR için mobile prefix
        if prefix == "+90":
            local = normalized[3:]  # 5XX...
            if local.startswith("5"):
                result["is_mobile"] = True
                carrier_map = {
                    "530": "Turkcell", "531": "Turkcell", "532": "Turkcell",
                    "533": "Turkcell", "534": "Turkcell", "535": "Turkcell",
                    "536": "Turkcell", "537": "Turkcell", "538": "Turkcell",
                    "539": "Turkcell", "505": "Vodafone TR", "506": "Vodafone TR",
                    "507": "Vodafone TR", "541": "Vodafone TR", "542": "Vodafone TR",
                    "543": "Vodafone TR", "544": "Vodafone TR", "545": "Vodafone TR",
                    "546": "Vodafone TR", "547": "Vodafone TR", "548": "Vodafone TR",
                    "549": "Vodafone TR", "551": "Türk Telekom", "552": "Türk Telekom",
                    "553": "Türk Telekom", "554": "Türk Telekom", "555": "Türk Telekom",
                    "559": "Türk Telekom",
                }
                prefix3 = local[:3]
                if prefix3 in carrier_map:
                    result["possible_carriers"] = [carrier_map[prefix3]]
            else:
                result["is_mobile"] = False

    # Format varyasyonları
    digits = re.sub(r"\D", "", normalized)
    result["formats"] = {
        "international":    normalized,
        "national":         digits[-10:] if len(digits) >= 10 else digits,
        "no_plus":          digits,
        "dashed":           re.sub(r"(\d{3})(\d{3})(\d{4})$", r"\1-\2-\3", digits),
        "spaced":           re.sub(r"(\d{3})(\d{3})(\d{4})$", r"\1 \2 \3", digits),
        "with_parens":      re.sub(r"(\d{3})(\d{3})(\d{4})$", r"(\1) \2-\3", digits),
    }

    # Dork sorguları
    q_variants = [
        normalized,
        result["formats"]["national"],
        result["formats"]["dashed"],
        result["formats"]["no_plus"],
    ]

    result["dork_links"] = []
    for q in q_variants[:2]:
        result["dork_links"] += [
            {"label": f"Google: '{q}'",          "url": f'https://www.google.com/search?q="{quote(q)}"'},
            {"label": f"Bing: '{q}'",             "url": f'https://www.bing.com/search?q="{quote(q)}"'},
            {"label": f"Twitter/X: '{q}'",        "url": f'https://twitter.com/search?q="{quote(q)}"'},
            {"label": f"Telegram grubu: '{q}'",   "url": f'https://t.me/s/search?q={quote(q)}'},
        ]

    result["search_links"] = [
        {"label": "Truecaller",      "url": f"https://www.truecaller.com/search/tr/{quote(digits[-10:])}"},
        {"label": "Google Maps",     "url": f'https://www.google.com/maps/search/{quote(normalized)}'},
        {"label": "WhatsApp check",  "url": f"https://wa.me/{digits}"},
        {"label": "Telegram check",  "url": f"https://t.me/+{digits}"},
        {"label": "NumLookup",       "url": f"https://www.numlookup.com/?number={quote(normalized)}"},
        {"label": "PhoneValidator",  "url": f"https://www.phonevalidator.com/index.aspx?phone={quote(normalized)}"},
        {"label": "Pastebin dork",   "url": f'https://www.google.com/search?q=site:pastebin.com+"{quote(normalized)}"'},
    ]

    return result
