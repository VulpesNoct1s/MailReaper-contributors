"""
MailReaper - EXIF & Metadata Analyzer
Profil fotoğraflarını indirir ve metadata/EXIF bilgisi çıkartır.
Ayrıca resim üzerinden tersine arama linkleri üretir.
"""

import requests
import hashlib
import io
import struct
from urllib.parse import quote

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def _read_exif_basic(data: bytes) -> dict:
    """
    Pillow gerektirmeden temel EXIF okur.
    JPEG APPx segmentlerini manuel parse eder.
    """
    exif = {}
    if len(data) < 4:
        return exif

    # JPEG kontrolü
    if data[:2] != b'\xff\xd8':
        return exif

    i = 2
    while i < len(data) - 1:
        if data[i] != 0xff:
            break
        marker = data[i + 1]
        i += 2

        if marker == 0xd9:  # EOI
            break
        if marker in (0xd0, 0xd1, 0xd2, 0xd3, 0xd4, 0xd5, 0xd6, 0xd7, 0xda):
            # Standalone markers
            if marker == 0xda:  # SOS - stop here
                break
            continue

        if i + 2 > len(data):
            break

        length = struct.unpack('>H', data[i:i+2])[0]
        segment_data = data[i+2:i+length]
        i += length

        # APP1 — EXIF/XMP
        if marker == 0xe1:
            if segment_data[:6] == b'Exif\x00\x00':
                exif["has_exif"] = True
                exif["exif_segment_size"] = len(segment_data)
                # Temel TIFF header parse
                tiff = segment_data[6:]
                if len(tiff) >= 8:
                    byte_order = tiff[:2]
                    if byte_order == b'II':
                        exif["byte_order"] = "Little-Endian (Intel)"
                    elif byte_order == b'MM':
                        exif["byte_order"] = "Big-Endian (Motorola)"
            elif segment_data[:29] == b'http://ns.adobe.com/xap/1.0/\x00':
                exif["has_xmp"] = True
                xmp_data = segment_data[29:].decode("utf-8", errors="ignore")
                # XMP'den bazı alanları çıkart
                import re
                creator = re.search(r'<dc:creator[^>]*>(.*?)</dc:creator>', xmp_data, re.DOTALL)
                if creator:
                    exif["xmp_creator"] = creator.group(1).strip()
                software = re.search(r'<xmp:CreatorTool>(.*?)</xmp:CreatorTool>', xmp_data)
                if software:
                    exif["xmp_software"] = software.group(1)
                create_date = re.search(r'<xmp:CreateDate>(.*?)</xmp:CreateDate>', xmp_data)
                if create_date:
                    exif["xmp_create_date"] = create_date.group(1)
                mod_date = re.search(r'<xmp:ModifyDate>(.*?)</xmp:ModifyDate>', xmp_data)
                if mod_date:
                    exif["xmp_modify_date"] = mod_date.group(1)

        # APP0 — JFIF
        elif marker == 0xe0:
            if segment_data[:5] == b'JFIF\x00':
                version_major = segment_data[5]
                version_minor = segment_data[6]
                exif["format"] = "JPEG/JFIF"
                exif["jfif_version"] = f"{version_major}.{version_minor:02d}"

        # COM — Comment
        elif marker == 0xfe:
            comment = segment_data.decode("utf-8", errors="ignore").strip()
            if comment:
                exif["comment"] = comment

    return exif


def _get_image_info(data: bytes) -> dict:
    """Görüntü boyutu ve format bilgisi çıkarır."""
    info = {}
    if not data:
        return info

    info["file_size_bytes"] = len(data)
    info["file_size_kb"] = round(len(data) / 1024, 1)
    info["md5"] = hashlib.md5(data).hexdigest()
    info["sha1"] = hashlib.sha1(data).hexdigest()

    # JPEG
    if data[:2] == b'\xff\xd8':
        info["format"] = "JPEG"
        # Boyut için SOF marker ara
        i = 2
        while i < len(data) - 1:
            if data[i] != 0xff:
                break
            marker = data[i + 1]
            i += 2
            if marker in (0xc0, 0xc1, 0xc2):  # SOF
                if i + 7 <= len(data):
                    length = struct.unpack('>H', data[i:i+2])[0]
                    precision = data[i+2]
                    height = struct.unpack('>H', data[i+3:i+5])[0]
                    width = struct.unpack('>H', data[i+5:i+7])[0]
                    info["width"] = width
                    info["height"] = height
                    info["bit_depth"] = precision
                break
            if i + 2 > len(data):
                break
            length = struct.unpack('>H', data[i:i+2])[0]
            i += length

    # PNG
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        info["format"] = "PNG"
        if len(data) >= 24:
            width = struct.unpack('>I', data[16:20])[0]
            height = struct.unpack('>I', data[20:24])[0]
            info["width"] = width
            info["height"] = height

    # GIF
    elif data[:6] in (b'GIF87a', b'GIF89a'):
        info["format"] = "GIF"
        if len(data) >= 10:
            width = struct.unpack('<H', data[6:8])[0]
            height = struct.unpack('<H', data[8:10])[0]
            info["width"] = width
            info["height"] = height

    # WebP
    elif data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        info["format"] = "WebP"

    return info


def analyze_image_url(image_url: str) -> dict:
    """
    Bir URL'deki görseli indirir ve metadata analizi yapar.
    """
    result = {
        "url": image_url,
        "downloaded": False,
        "image_info": {},
        "exif": {},
        "reverse_search_urls": [],
        "error": None,
    }

    if not image_url:
        result["error"] = "URL boş"
        return result

    try:
        resp = requests.get(image_url, headers=HEADERS, timeout=12, stream=True)
        # Sadece ilk 2MB indir
        content = b""
        for chunk in resp.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > 2 * 1024 * 1024:
                break

        if resp.status_code != 200 or not content:
            result["error"] = f"İndirme başarısız: HTTP {resp.status_code}"
            return result

        result["downloaded"] = True
        result["image_info"] = _get_image_info(content)

        # EXIF analizi
        if content[:2] == b'\xff\xd8':  # JPEG
            result["exif"] = _read_exif_basic(content)

    except Exception as e:
        result["error"] = str(e)
        return result

    # Tersine görüntü arama linkleri
    result["reverse_search_urls"] = [
        {"name": "Google Lens",   "url": f"https://lens.google.com/uploadbyurl?url={quote(image_url)}"},
        {"name": "TinEye",        "url": f"https://www.tineye.com/search/?url={quote(image_url)}"},
        {"name": "Yandex Images", "url": f"https://yandex.com/images/search?rpt=imageview&url={quote(image_url)}"},
        {"name": "Bing Visual",   "url": f"https://www.bing.com/images/search?q=imgurl:{quote(image_url)}&view=detailv2"},
        {"name": "Baidu",         "url": f"https://image.baidu.com/search/index?tn=baiduimage&word={quote(image_url)}"},
    ]

    return result


def analyze_multiple_images(image_urls: list) -> list:
    """Birden fazla görseli analiz eder."""
    results = []
    for url in image_urls:
        if url:
            r = analyze_image_url(url)
            results.append(r)
    return results
