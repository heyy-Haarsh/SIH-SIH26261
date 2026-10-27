"""Officer-note speech-to-text via Sarvam.

REST is a fallback for short WAV clips. Live dictation uses the realtime WebSocket
proxy in the scrutiny routes. The subscription key never leaves the server.
"""

from __future__ import annotations

import httpx

from app.core.config import get_settings
from app.core.errors import ServiceUnavailableError, UnprocessableError

MAX_AUDIO_BYTES = 2_500_000
ALLOWED_SUFFIX = (".webm", ".wav", ".mp3", ".ogg", ".m4a", ".mp4", ".aac", ".flac", ".opus")


def _sarvam_error_detail(res: httpx.Response) -> str:
    try:
        payload = res.json()
    except Exception:
        return (res.text or "")[:240]
    if isinstance(payload, dict):
        err = payload.get("error") or payload.get("detail") or payload
        if isinstance(err, dict):
            return str(err.get("message") or err)[:240]
        return str(err)[:240]
    return str(payload)[:240]


def transcribe_audio(content: bytes, filename: str, content_type: str | None = None) -> dict:
    settings = get_settings()
    key = (settings.sarvam_api_key or "").strip()
    if not key:
        raise ServiceUnavailableError(
            "Speech to text is not configured. Set SARVAM_API_KEY in backend/.env and restart the API.",
            code="stt_not_configured",
        )
    if not content or len(content) < 200:
        raise UnprocessableError("The recording was empty. Hold Speak, talk, then stop.", code="empty_audio")
    if len(content) > MAX_AUDIO_BYTES:
        raise UnprocessableError("Recording is too long. Keep it under about 30 seconds.", code="audio_too_large")

    name = filename or "note.wav"
    if not name.lower().endswith(ALLOWED_SUFFIX):
        name = "note.wav"
    mime = content_type or "application/octet-stream"
    # Browser MediaRecorder WebM often fails on REST; prefer WAV from the realtime path.
    if "webm" in (mime.lower() + name.lower()):
        raise UnprocessableError(
            "Use Speak for live transcription. WebM clips are not reliable on Sarvam REST.",
            code="unsupported_audio",
        )

    try:
        with httpx.Client(timeout=45.0) as client:
            res = client.post(
                settings.sarvam_stt_url,
                headers={"api-subscription-key": key},
                files={"file": (name, content, mime)},
                data={
                    "model": settings.sarvam_stt_model,
                    "language_code": "en-IN",
                },
            )
    except httpx.TimeoutException as exc:
        raise ServiceUnavailableError(
            "Sarvam did not respond in time. Type the note, or try again.",
            code="stt_timeout",
        ) from exc
    except httpx.TransportError as exc:
        raise ServiceUnavailableError(
            "Could not reach Sarvam. Check the network, then try again.",
            code="stt_unreachable",
        ) from exc

    if res.status_code == 403:
        raise ServiceUnavailableError(
            "Sarvam rejected the API key. Check SARVAM_API_KEY in backend/.env.",
            code="stt_auth_failed",
        )
    if res.status_code >= 400:
        raise ServiceUnavailableError(
            f"Sarvam could not transcribe that clip ({res.status_code}): {_sarvam_error_detail(res)}",
            code="stt_failed",
        )

    payload = res.json() if res.content else {}
    text = (
        payload.get("transcript")
        or payload.get("text")
        or payload.get("request_text")
        or ""
    )
    if isinstance(text, dict):
        text = text.get("transcript") or text.get("text") or ""
    text = str(text).strip()
    if not text:
        raise UnprocessableError(
            "No words were recognised. Speak closer to the mic and try again.",
            code="empty_transcript",
        )
    return {
        "transcript": text,
        "language": payload.get("language_code") or payload.get("language"),
        "provider": "sarvam",
    }


def realtime_ws_url() -> str:
    settings = get_settings()
    base = (settings.sarvam_realtime_ws_url or "wss://api.sarvam.ai/speech-to-text-realtime/ws").rstrip("?")
    # mode=translate: final utterances become English; partials stay live as spoken.
    q = (
        "language_code=auto"
        f"&model={settings.sarvam_realtime_model}"
        "&stream_type=fast"
        "&mode=translate"
        "&endpointing=vad"
        "&encoding=linear16"
        "&sample_rate=16000"
        "&silence_duration_ms=600"
    )
    return f"{base}?{q}"
