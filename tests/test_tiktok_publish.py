"""Tests non-réseau du chemin de publication TikTok."""
from __future__ import annotations

import base64

from tiktok_publish import _cookies_from_env_or_file


def test_sessionid_is_converted_to_cookie_list(monkeypatch) -> None:
    monkeypatch.setenv("TIKTOK_SESSIONID", "secret-session")
    monkeypatch.delenv("TIKTOK_COOKIES_B64", raising=False)
    path, cookies, temporary = _cookies_from_env_or_file(None)
    assert path is None
    assert temporary is None
    assert cookies[0]["name"] == "sessionid"
    assert cookies[0]["value"] == "secret-session"


def test_base64_cookies_are_written_to_temporary_file(monkeypatch) -> None:
    payload = b"# Netscape HTTP Cookie File\n"
    monkeypatch.setenv("TIKTOK_COOKIES_B64", base64.b64encode(payload).decode())
    monkeypatch.delenv("TIKTOK_SESSIONID", raising=False)
    path, cookies, temporary = _cookies_from_env_or_file(None)
    try:
        assert path is not None
        assert cookies is None
        assert temporary is not None
        assert temporary.read_bytes() == payload
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
