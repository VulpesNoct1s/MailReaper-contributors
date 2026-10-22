"""
MailReaper - Username Generator Module
Email adresinden 50+ olası kullanıcı adı üretir
"""

import re


def generate_usernames(email: str) -> dict:
    """
    Email adresinden olası kullanıcı adı permütasyonları üretir.
    API gerektirmez — tamamen yerel hesaplama.
    """
    email = email.strip().lower()
    local = email.split("@")[0] if "@" in email else email

    usernames = set()

    # Temel ekle
    usernames.add(local)

    # Nokta/alt çizgi/tire temizle
    no_dots = local.replace(".", "")
    no_underscores = local.replace("_", "")
    no_hyphens = local.replace("-", "")
    no_special = re.sub(r'[._\-]', '', local)

    usernames.update([no_dots, no_underscores, no_hyphens, no_special])

    # Parçalara böl
    parts = re.split(r'[._\-]', local)
    parts = [p for p in parts if p]  # boşları temizle

    if len(parts) >= 2:
        first = parts[0]
        last = parts[-1]
        mid = parts[1] if len(parts) > 2 else ""

        usernames.update([
            first,
            last,
            f"{first}{last}",
            f"{last}{first}",
            f"{first}.{last}",
            f"{last}.{first}",
            f"{first}_{last}",
            f"{last}_{first}",
            f"{first[0]}{last}" if first else "",
            f"{first}{last[0]}" if last else "",
            f"{first[0]}.{last}" if first else "",
        ])

        if mid:
            usernames.update([
                f"{first}{mid}{last}",
                f"{first[0]}{mid[0]}{last}" if first and mid else "",
            ])

    # Sayı ayıklama
    numbers = re.sub(r'[^0-9]', '', local)
    alpha_only = re.sub(r'[0-9]', '', no_special)

    if numbers:
        usernames.add(alpha_only)
        usernames.add(alpha_only + numbers)

    # Büyük/küçük harf varyasyonları
    usernames.add(local.upper())
    usernames.add(local.capitalize())
    if len(parts) >= 2:
        usernames.add(parts[0].capitalize() + parts[-1].capitalize())
        usernames.add(parts[0].capitalize() + parts[-1])

    # Yaygın prefix'ler
    prefixes = ["the", "real", "im", "its", "i_am", "iamthe", "official",
                "mr", "ms", "dr", "x", "hey", "hi", "yo", "iam"]
    for prefix in prefixes:
        usernames.add(f"{prefix}{local}")
        usernames.add(f"{prefix}_{local}")
        if parts:
            usernames.add(f"{prefix}{parts[0]}")

    # Yaygın suffix'ler
    suffixes = ["1", "2", "3", "01", "99", "123", "2023", "2024", "2025",
                "x", "xx", "_", "__", "_real", "_official", "_the",
                "hq", "pro", "dev", "io"]
    for suffix in suffixes:
        usernames.add(f"{local}{suffix}")
        if parts:
            usernames.add(f"{parts[0]}{suffix}")

    # Yıl permütasyonları
    for year in ["2020", "2021", "2022", "2023", "2024", "2025"]:
        usernames.add(f"{local}{year}")
        usernames.add(f"{local}_{year}")

    # Ters çevrilmiş
    usernames.add(local[::-1])
    usernames.add(no_special[::-1])

    # Kısaltmalar
    if len(local) > 6:
        usernames.add(local[:3])
        usernames.add(local[:4])
        usernames.add(local[:5])
        usernames.add(local[-3:])
        usernames.add(local[:3] + local[-3:])

    # camelCase/PascalCase
    if len(parts) >= 2:
        camel = parts[0] + "".join(p.capitalize() for p in parts[1:])
        pascal = "".join(p.capitalize() for p in parts)
        usernames.update([camel, pascal])

    # Temizlik: boş, çok kısa, sadece rakam olanları kaldır
    cleaned = set()
    for u in usernames:
        u = u.strip()
        if u and len(u) >= 2 and not u.isdigit() and len(u) <= 30:
            cleaned.add(u)

    return {
        "email": email,
        "local_part": local,
        "usernames": sorted(list(cleaned)),
    }
