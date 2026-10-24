"""Validate uploaded images in memory, before sending anything to the provider."""

import base64
import binascii
import warnings
from io import BytesIO

from PIL import Image, UnidentifiedImageError

from app.errors import ApiError, ErrorCode

# Conservative headroom for base64 JSON and the API Gateway/Lambda event envelope.
MAX_IMAGE_BYTES = 3 * 1024 * 1024
MAX_IMAGE_EDGE = 8192
MAX_IMAGE_PIXELS = 16_000_000
_FORMATS = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}


def _invalid(message: str) -> ApiError:
    return ApiError(ErrorCode.VALIDATION, message, {"field": "image_base64"})


def validate_image(media_type: str, encoded: str) -> None:
    if len(encoded) > 4 * ((MAX_IMAGE_BYTES + 2) // 3):
        raise _invalid("Image exceeds the 3 MiB upload limit; compress it first")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise _invalid("image_base64 must contain base64 image bytes without a data URL") from None
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise _invalid("Image must contain between 1 byte and 3 MiB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != _FORMATS.get(media_type):
                    raise _invalid("Image content does not match the declared media_type")
                width, height = image.size
                if max(width, height) > MAX_IMAGE_EDGE or width * height > MAX_IMAGE_PIXELS:
                    raise _invalid("Image dimensions are too large; resize it first")
                if getattr(image, "n_frames", 1) != 1:
                    raise _invalid("Upload one still image, not an animated image")
                image.verify()
            # verify() alone does not decode every format, including JPEG pixels.
            with Image.open(BytesIO(data)) as image:
                image.load()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise _invalid("Image bytes are invalid, corrupt or incomplete") from None
