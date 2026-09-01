"""Rahasia harus datang dari environment, dan gagal-tertutup di produksi.

Modul config dievaluasi SAAT IMPOR, jadi tiap kasus menjalankan subprocess
dengan environment berbeda. Itu lebih lambat daripada memanggil fungsi, tapi
ia menguji hal yang sebenarnya penting: apa yang terjadi saat proses start
di lingkungan tertentu — bukan perilaku fungsi yang dipanggil belakangan.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

LAB = Path(__file__).resolve().parent.parent
CEK = "from ragcore import config; print('OK', config.PG_URL_APP.rsplit('@',1)[-1])"


def _impor(env_tambahan: dict) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(LAB / "src")}
    # bersihkan agar tiap kasus berangkat dari keadaan yang sama. Termasuk akun
    # Oracle turunan (OPERATOR, AUTH): tanpa dibersihkan, nilainya bisa BOCOR
    # dari environment induk dan membuat kasus produksi lulus semu.
    for k in ("RAG_ENV", "PG_URL", "PG_URL_DIRECT", "PG_URL_APP",
              "ORACLE_CONNECTION", "ORACLE_CONNECTION_OPERATOR",
              "ORACLE_CONNECTION_AUTH"):
        env.pop(k, None)
    env.update(env_tambahan)
    return subprocess.run([sys.executable, "-c", CEK], cwd=LAB, env=env,
                          capture_output=True, text=True, timeout=60)


def test_lab_jalan_tanpa_setup():
    """Zero-setup adalah janji README — harus tetap ditepati."""
    r = _impor({})
    assert r.returncode == 0, r.stderr[-400:]
    assert "OK" in r.stdout


def test_produksi_tanpa_env_gagal_saat_impor():
    r = _impor({"RAG_ENV": "production"})
    assert r.returncode != 0, "produksi tanpa kredensial seharusnya gagal"
    assert "RAG_ENV=production" in r.stderr
    assert "PG_URL" in r.stderr


def test_produksi_dengan_env_jalan():
    real = "postgresql+psycopg://u:S3cr3t@db.prod:5432/x"
    r = _impor({
        "RAG_ENV": "production",
        "PG_URL": real, "PG_URL_DIRECT": "postgresql://u:S3cr3t@db.prod:5432/x",
        "PG_URL_APP": real, "ORACLE_CONNECTION": "u/S3cr3t@ora.prod:1521/X",
        # Akun Oracle turunan juga wajib di produksi (default diabaikan).
        "ORACLE_CONNECTION_OPERATOR": "op/S3cr3t@ora.prod:1521/X",
        "ORACLE_CONNECTION_AUTH": "au/S3cr3t@ora.prod:1521/X",
        # Produksi mewajibkan rahasia penanda-tangan sesi juga - default lab
        # yang diketahui umum bisa dipakai memalsukan sesi.
        "SESSION_SECRET": "prod-session-secret-abc123",
    })
    assert r.returncode == 0, r.stderr[-400:]
    assert "db.prod" in r.stdout


def test_produksi_tanpa_session_secret_gagal():
    """DB lengkap tapi SESSION_SECRET kosong -> tetap gagal di produksi.

    Rahasia penanda-tangan sesi adalah kredensial juga: tanpa itu, token sesi
    ditandatangani dengan default yang ada di kode -> sesi bisa dipalsukan.
    """
    real = "postgresql+psycopg://u:S3cr3t@db.prod:5432/x"
    r = _impor({
        "RAG_ENV": "production",
        "PG_URL": real, "PG_URL_DIRECT": "postgresql://u:S3cr3t@db.prod:5432/x",
        "PG_URL_APP": real, "ORACLE_CONNECTION": "u/S3cr3t@ora.prod:1521/X",
        # Semua kredensial lain ADA - jadi satu-satunya yang kurang adalah
        # SESSION_SECRET, dan galatnya harus menyebut itu.
        "ORACLE_CONNECTION_OPERATOR": "op/S3cr3t@ora.prod:1521/X",
        "ORACLE_CONNECTION_AUTH": "au/S3cr3t@ora.prod:1521/X",
    })
    assert r.returncode != 0, "produksi tanpa SESSION_SECRET seharusnya gagal"
    assert "SESSION_SECRET" in r.stderr


@pytest.mark.parametrize("url", [
    "postgresql+psycopg://rag_app:rahasia_app@db.internal:5432/korpus",
    "postgresql+psycopg://rag_app:rahasia_app@10.20.30.40:5432/korpus",
])
def test_sandi_demo_di_host_non_lokal_ditolak(url):
    """Berlaku di SEMUA mode: sandi contoh + host sungguhan = kebocoran."""
    r = _impor({"PG_URL_APP": url})
    assert r.returncode != 0, f"'{url}' seharusnya ditolak"
    assert "non-lokal" in r.stderr


def test_host_lokal_dengan_sandi_demo_diterima():
    """localhost dan nama layanan compose bukan kebocoran."""
    for host in ("localhost", "127.0.0.1", "db", "postgres"):
        url = f"postgresql+psycopg://rag_app:rahasia_app@{host}:5432/korpus"
        r = _impor({"PG_URL_APP": url})
        assert r.returncode == 0, f"host lokal '{host}' seharusnya diterima: {r.stderr[-300:]}"


# ----------------------------------------------------- OpenBao (secret manager)

def test_openbao_tanpa_konfigurasi_kosong(monkeypatch):
    """Tanpa OPENBAO_ADDR/TOKEN -> {} (jatuh ke env/default). App tetap jalan
    tanpa OpenBao - itu yang menjaga janji zero-setup lab."""
    from ragcore.settings import security

    monkeypatch.setattr(security, "_bao_cache", None)     # reset cache
    monkeypatch.delenv("OPENBAO_ADDR", raising=False)
    monkeypatch.delenv("OPENBAO_TOKEN", raising=False)
    assert security._openbao_secrets() == {}


def test_env_menang_atas_openbao(monkeypatch):
    """Urutan sumber: env menimpa OpenBao (untuk uji/darurat)."""
    from ragcore.settings import security

    monkeypatch.setattr(security, "_bao_cache", {"SESSION_SECRET": "dari-bao"})
    monkeypatch.setenv("SESSION_SECRET", "dari-env")
    assert security._sourced("SESSION_SECRET") == "dari-env"


def test_openbao_dipakai_saat_env_kosong(monkeypatch):
    """Env kosong -> rahasia diambil dari OpenBao, bukan default lab."""
    from ragcore.settings import security

    monkeypatch.setattr(security, "_bao_cache", {"SESSION_SECRET": "rahasia-bao"})
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    assert security.signing_secret("SESSION_SECRET", "default-lab") == "rahasia-bao"


def test_openbao_kosong_jatuh_ke_default_lab(monkeypatch):
    """OpenBao tak menyediakan & bukan produksi -> default lab (zero-setup)."""
    from ragcore.settings import security

    monkeypatch.setattr(security, "_bao_cache", {})
    monkeypatch.setattr(security, "IS_PRODUCTION", False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    assert security.signing_secret("SESSION_SECRET", "default-lab") == "default-lab"


# ----------------------------------------------- kredensial DB dinamis (opt-in)

_URL = "postgresql+psycopg://rag_app:statik@pg-txai12:5432/korpus"


def test_dynamic_db_nonaktif_url_tak_berubah(monkeypatch):
    """Tanpa OPENBAO_DB_ROLE, URL statis dikembalikan apa adanya."""
    from ragcore.settings import security

    monkeypatch.delenv("OPENBAO_DB_ROLE", raising=False)
    assert security.maybe_dynamic_db(_URL) == _URL


def test_dynamic_db_mengganti_userinfo(monkeypatch):
    """Dengan role diset & kredensial tersedia: HANYA user/sandi yang diganti,
    host/port/nama-db tetap."""
    from ragcore.settings import security

    monkeypatch.setenv("OPENBAO_DB_ROLE", "rag_app_dyn")
    monkeypatch.setattr(security, "_dynamic_db_creds",
                        lambda role: ("v-efemeral-123", "sandi-efemeral"))
    out = security.maybe_dynamic_db(_URL)
    assert "v-efemeral-123:sandi-efemeral@pg-txai12:5432/korpus" in out
    assert out.startswith("postgresql+psycopg://")
    assert "statik" not in out


def test_dynamic_db_gagal_ambil_fail_safe(monkeypatch):
    """Bila pengambilan kredensial gagal (None), URL statis dipertahankan -
    tak mematikan app."""
    from ragcore.settings import security

    monkeypatch.setenv("OPENBAO_DB_ROLE", "rag_app_dyn")
    monkeypatch.setattr(security, "_dynamic_db_creds", lambda role: None)
    assert security.maybe_dynamic_db(_URL) == _URL
