from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.conftest import auth_headers

OFFICER = auth_headers("officer")
APPLICANT = auth_headers("applicant")

CLIP = b"RIFF" + b"\x00" * 400


def test_applicant_cannot_transcribe(client):
    res = client.post(
        "/api/v1/scrutiny/transcribe",
        headers=APPLICANT,
        files={"file": ("note.wav", CLIP, "audio/wav")},
    )
    assert res.status_code == 403


def test_transcribe_requires_configured_key(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "sarvam_api_key", "")
    res = client.post(
        "/api/v1/scrutiny/transcribe",
        headers=OFFICER,
        files={"file": ("note.wav", CLIP, "audio/wav")},
    )
    assert res.status_code == 503
    assert res.json()["code"] == "stt_not_configured"


def test_webm_is_rejected_on_rest(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "sarvam_api_key", "test-sarvam-key")
    res = client.post(
        "/api/v1/scrutiny/transcribe",
        headers=OFFICER,
        files={"file": ("note.webm", CLIP, "audio/webm")},
    )
    assert res.status_code == 422
    assert res.json()["code"] == "unsupported_audio"


def test_transcribe_returns_sarvam_text(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "sarvam_api_key", "test-sarvam-key")
    fake = MagicMock()
    fake.status_code = 200
    fake.content = b"{}"
    fake.json.return_value = {"transcript": "Checked the original fire NOC.", "language_code": "en-IN"}

    with patch("app.services.speech_to_text_service.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.post.return_value = fake
        res = client.post(
            "/api/v1/scrutiny/transcribe",
            headers=OFFICER,
            files={"file": ("note.wav", CLIP, "audio/wav")},
        )

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["transcript"] == "Checked the original fire NOC."
    assert body["provider"] == "sarvam"
