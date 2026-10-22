"""
MailReaper - Risk Scorer Module
Tüm OSINT bulgularına göre 0-100 risk skoru hesaplar
"""

from typing import Optional


def calculate_risk_score(results: dict) -> dict:
    """
    Tüm modül çıktılarından risk skoru hesaplar.
    
    Risk kategorileri:
    - Identity Exposure (0-30): Sosyal medya, GitHub, Gravatar
    - Email Validity (0-20): Disposable, SMTP, MX
    - Infrastructure Risk (0-20): DNS, SPF, DMARC eksiklikleri
    - Leak/Breach Risk (0-30): Paste sites, stealer logs, breach data
    
    Returns:
        {
            'total': int (0-100),
            'grade': str (A-F),
            'category_scores': dict,
            'risk_factors': list,
            'recommendations': list
        }
    """
    score = 0
    risk_factors = []
    recommendations = []
    category_scores = {
        "identity_exposure": 0,
        "email_validity": 0,
        "infrastructure_risk": 0,
        "leak_breach_risk": 0,
    }

    # ─── EMAIL VALİDİTY ───
    validator = results.get("email_validator", {})
    if validator.get("is_disposable"):
        score += 15
        category_scores["email_validity"] += 15
        risk_factors.append("⚠️ Disposable/geçici email adresi kullanılmış")
    if validator and not validator.get("has_mx"):
        score += 5
        category_scores["email_validity"] += 5
        risk_factors.append("❌ Domain'de MX kaydı yok — email alınamıyor")
        recommendations.append("Email geçersiz olabilir, domain mail sunucusu barındırmıyor.")
    if validator and not validator.get("valid_syntax"):
        score += 5
        category_scores["email_validity"] += 5
        risk_factors.append("❌ Email formatı geçersiz")

    # SMTP
    smtp = results.get("smtp_probe", {})
    if smtp.get("catch_all"):
        score += 5
        category_scores["email_validity"] += 5
        risk_factors.append("⚠️ Catch-all sunucu — email varlığı doğrulanamıyor")

    # ─── INFRASTRUCTURE RİSK ───
    dns = results.get("dns_analysis", {})
    spf = dns.get("spf", {})
    dmarc = dns.get("dmarc", {})

    if not spf.get("exists"):
        score += 5
        category_scores["infrastructure_risk"] += 5
        risk_factors.append("⚠️ SPF kaydı yok — email spoofing riski")
        recommendations.append("Domain sahibi SPF kaydı eklemelidir.")
    else:
        if "+all" in (spf.get("record") or ""):
            score += 8
            category_scores["infrastructure_risk"] += 8
            risk_factors.append("🔴 SPF '+all' direktifi — herkes bu domain adına mail gönderebilir!")
            recommendations.append("SPF kaydındaki '+all' direktifi ciddi güvenlik açığıdır.")

    if not dmarc.get("exists"):
        score += 5
        category_scores["infrastructure_risk"] += 5
        risk_factors.append("⚠️ DMARC kaydı yok — phishing riski artmış")
        recommendations.append("Domain için DMARC politikası tanımlanmalıdır.")
    else:
        dmarc_policy = (dmarc.get("policy") or "").lower()
        if dmarc_policy == "none":
            score += 3
            category_scores["infrastructure_risk"] += 3
            risk_factors.append("⚠️ DMARC policy 'none' — monitörleme var ama aksiyon yok")

    ssl = dns.get("ssl", {})
    if ssl:
        if ssl.get("expired"):
            score += 7
            category_scores["infrastructure_risk"] += 7
            risk_factors.append("🔴 SSL sertifikası süresi dolmuş!")
        elif ssl.get("days_remaining", 999) < 30:
            score += 3
            category_scores["infrastructure_risk"] += 3
            risk_factors.append(f"⚠️ SSL sertifikası {ssl.get('days_remaining')} gün içinde sona erecek")

    # ─── IDENTİTY EXPOSURE ───
    social = results.get("social", {})
    found_count = social.get("total_found", 0)
    if found_count >= 10:
        score += 15
        category_scores["identity_exposure"] += 15
        risk_factors.append(f"🔴 {found_count} platformda aktif profil tespit edildi — yüksek dijital iz")
    elif found_count >= 5:
        score += 10
        category_scores["identity_exposure"] += 10
        risk_factors.append(f"⚠️ {found_count} platformda profil bulundu")
    elif found_count > 0:
        score += 5
        category_scores["identity_exposure"] += 5
        risk_factors.append(f"ℹ️ {found_count} platformda profil bulundu")

    gravatar = results.get("gravatar", {})
    if gravatar.get("has_gravatar"):
        score += 5
        category_scores["identity_exposure"] += 5
        risk_factors.append("ℹ️ Gravatar profili mevcut — avatar ve profil bilgileri açık")

    github = results.get("github_search", {})
    if github.get("github_user"):
        score += 5
        category_scores["identity_exposure"] += 5
        risk_factors.append("ℹ️ GitHub hesabı bulundu — kod geçmişi incelenebilir")
    if github.get("commits_found"):
        score += 8
        category_scores["identity_exposure"] += 8
        risk_factors.append(f"⚠️ GitHub'da {len(github.get('commits_found', []))} commit'te email görünür durumda")
        recommendations.append("Git commit geçmişinde email gizlemek için GitHub'ın privacy ayarlarını kullanın.")

    # ─── LEAK / BREACH RİSK ───
    paste = results.get("pastebin", {})
    paste_count = paste.get("total_found", 0)
    if paste_count > 0:
        stealer_count = sum(1 for f in paste.get("findings", []) if "Stealer" in f.get("source", ""))
        if stealer_count > 0:
            score += 30
            category_scores["leak_breach_risk"] += 30
            risk_factors.append(f"🔴 STEALER LOG BULUNDU — {stealer_count} kayıt! Kimlik bilgileri tehlikede!")
            recommendations.append("ACIL: Şifrelerinizi değiştirin, 2FA aktifleştirin, hesaplarınızı kontrol edin!")
        else:
            score += 15
            category_scores["leak_breach_risk"] += 15
            risk_factors.append(f"🔴 {paste_count} paste/sızıntı kaydında email bulundu")
            recommendations.append("Şifrelerinizi değiştirmeniz ve 2FA kullanmanız önerilir.")

    # Skoru 100 ile sınırla
    score = min(score, 100)

    # Grade hesapla
    if score <= 20:
        grade = "A"
        grade_text = "Düşük Risk"
        grade_color = "#00ff88"
    elif score <= 40:
        grade = "B"
        grade_text = "Orta-Düşük Risk"
        grade_color = "#88ff00"
    elif score <= 60:
        grade = "C"
        grade_text = "Orta Risk"
        grade_color = "#ffcc00"
    elif score <= 80:
        grade = "D"
        grade_text = "Yüksek Risk"
        grade_color = "#ff8800"
    else:
        grade = "F"
        grade_text = "Kritik Risk"
        grade_color = "#ff0044"

    return {
        "total": score,
        "grade": grade,
        "grade_text": grade_text,
        "grade_color": grade_color,
        "category_scores": category_scores,
        "risk_factors": risk_factors,
        "recommendations": recommendations,
        "summary": f"Risk skoru: {score}/100 ({grade_text})"
    }
