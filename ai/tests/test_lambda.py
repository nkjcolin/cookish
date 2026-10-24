import json
from types import SimpleNamespace

import pytest

from app.lambda_handler import handler
from scripts.test_lambda import gateway_event


@pytest.mark.parametrize(
    "path,payload,key",
    [
        ("/ai/parse-items", {"text": "food", "source": "typed"}, "items"),
        ("/ai/parse-items", {"text": "food", "source": "voice"}, "items"),
        ("/ai/interpret", {"text": "quicker"}, "adjust"),
    ],
)
def test_api_gateway_events_through_mangum(path, payload, key):
    result = handler(
        gateway_event(path, payload), SimpleNamespace(get_remaining_time_in_millis=lambda: 29000)
    )
    assert result["statusCode"] == 200
    assert key in json.loads(result["body"])


@pytest.mark.parametrize("kind", ["receipt", "photo"])
def test_lambda_image_event(image_payload, kind):
    result = handler(
        gateway_event("/ai/parse-image", {**image_payload, "kind": kind}),
        SimpleNamespace(get_remaining_time_in_millis=lambda: 29000),
    )
    assert result["statusCode"] == 200


def test_lambda_invalid_image_is_a_controlled_error():
    result = handler(
        gateway_event(
            "/ai/parse-image",
            {"kind": "receipt", "media_type": "image/jpeg", "image_base64": "bad"},
        ),
        SimpleNamespace(get_remaining_time_in_millis=lambda: 29000),
    )
    assert result["statusCode"] == 422
