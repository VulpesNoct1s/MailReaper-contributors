"""MailReaper temel testleri — ağ erişimi gerektirmez."""
import os
import sys
import tempfile

import pytest

# Testler gerçek geçmiş veritabanına dokunmasın
_tmp = tempfile.mkdtemp(prefix="mailreaper_test_")
os.environ["MAILREAPER_DB"] = os.path.join(_tmp, "test.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app as mr  # noqa: E402
from modules.web_recon import _murmur3_32  # noqa: E402
from modules.username_osint import SITES  # noqa: E402


@pytest.fixture()
def client():
    mr.app.config["TESTING"] = True
    mr.init_db()
    return mr.app.test_client()


# ── girdi temizleme / doğrulama ──
@pytest.mark.parametrize("raw,expected", [
    ("Example.COM", "example.com"),
    ("https://www.example.com/path?q=1", "example.com"),
    ("http://sub.example.org:8080/x", "sub.example.org"),
    ("", ""),
])
def test_clean_domain(raw, expected):
    assert mr.clean_domain(raw) == expected


def test_clean_username():
    assert mr.clean_username("@kullanici") == "kullanici"
    assert mr.clean_username("u/kullanici") == "kullanici"
    assert mr.clean_username("  abc ") == "abc"


def test_validate_inputs():
    assert mr.validate_inputs("a@b.com", "user_1", "example.com") is None
    assert mr.validate_inputs("bozuk", "", "") is not None
    assert mr.validate_inputs("", "", "bad_domain") is not None
    assert mr.validate_inputs("", "a b", "") is not None
    assert mr.validate_inputs("", "x" * 65, "") is not None


# ── favicon hash (Shodan uyumlu MurmurHash3) ──
def test_murmur3_known_values():
    assert _murmur3_32(b"") == 0
    assert _murmur3_32(b"foo") == -156908512


# ── Sherlock site listesi ──
def test_sites_are_unique_and_templated():
    names = [s["name"].lower() for s in SITES]
    assert len(names) == len(set(names))
    assert all("{u}" in s["url"] for s in SITES)


# ── API ──
def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200 and r.get_json()["status"] == "ok"


def test_index_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"board.js" in r.data and b"theme.js" in r.data


def test_analyze_rejects_bad_input(client):
    assert client.get("/api/analyze").status_code == 400
    assert client.get("/api/analyze?domain=bad_domain").status_code == 400
    assert client.get("/api/analyze?email=bozuk").status_code == 400


def test_history_empty_and_missing(client):
    assert client.get("/api/history").get_json() == []
    assert client.get("/api/history/999").status_code == 404


def test_case_crud(client):
    created = client.post("/api/cases", json={"name": "Test dosyası"})
    assert created.status_code == 201
    cid = created.get_json()["id"]

    board = {"nodes": [{"id": "n1", "type": "person", "label": "A", "x": 0, "y": 0}],
             "edges": [], "view": {"x": 0, "y": 0, "z": 1}}
    assert client.put(f"/api/cases/{cid}", json={"board": board}).status_code == 200
    assert client.put(f"/api/cases/{cid}", json={"name": "Yeni ad"}).status_code == 200

    listed = [c for c in client.get("/api/cases").get_json() if c["id"] == cid][0]
    assert listed["name"] == "Yeni ad"
    assert listed["board"]["nodes"][0]["label"] == "A"

    assert client.put(f"/api/cases/{cid}", json={}).status_code == 400
    assert client.put(f"/api/cases/{cid}", json={"board": "metin"}).status_code == 400
    assert client.put("/api/cases/99999", json={"name": "x"}).status_code == 404

    assert client.delete(f"/api/cases/{cid}").status_code == 200
    assert all(c["id"] != cid for c in client.get("/api/cases").get_json())


def test_export_filename_is_sanitized(tmp_path):
    from modules import exporter
    path = exporter.export_json("../../etc/passwd@x.com", {"a": 1}, output_dir=str(tmp_path))
    assert os.path.dirname(os.path.abspath(path)) == str(tmp_path)
