"""Validate small audio uploads in memory; never persist recordings."""

import base64
import binascii
import wave
from decimal import Decimal
from io import BytesIO

from app.errors import ApiError, ErrorCode

# Leave headroom for base64 JSON and the Lambda invocation envelope.
MAX_AUDIO_BYTES = 3 * 1024 * 1024


def validate_audio(media_type: str, encoded: str) -> bytes:
    def invalid(message: str) -> ApiError:
        return ApiError(ErrorCode.VALIDATION, message, {"field": "audio_base64"})

    if len(encoded) > 4 * ((MAX_AUDIO_BYTES + 2) // 3):
        raise invalid("Audio exceeds the 3 MiB upload limit; use a shorter recording")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise invalid("audio_base64 must contain audio bytes without a data URL") from None
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise invalid("Audio must contain between 1 byte and 3 MiB")
    # Check container signatures, not full codec decoding or recording duration.
    # The speech provider performs decoding; malformed streams still fail there.
    matches = {
        "audio/wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        "audio/x-wav": data.startswith(b"RIFF") and data[8:12] == b"WAVE",
        "audio/mpeg": data.startswith(b"ID3")
        or (len(data) > 1 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0),
        "audio/webm": data.startswith(b"\x1aE\xdf\xa3"),
        "audio/ogg": data.startswith(b"OggS"),
        "audio/mp4": data[4:8] == b"ftyp",
        "audio/flac": data.startswith(b"fLaC"),
    }
    if len(data) < 12 or not matches.get(media_type):
        raise invalid("Audio content does not match the declared media_type")
    return data


def wav_duration_seconds(data: bytes, media_type: str) -> Decimal | None:
    """Measure a complete PCM WAV, without trusting client-provided duration."""
    if media_type not in {"audio/wav", "audio/x-wav"}:
        return None
    try:
        with wave.open(BytesIO(data), "rb") as audio:
            frames, sample_rate = audio.getnframes(), audio.getframerate()
            if frames <= 0 or sample_rate <= 0:
                return None
            expected_bytes = frames * audio.getnchannels() * audio.getsampwidth()
            if len(audio.readframes(frames)) != expected_bytes:
                return None
            return Decimal(frames) / Decimal(sample_rate)
    except (wave.Error, EOFError, OSError, ValueError):
        return None
