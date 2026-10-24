"""Offline checks for the optional LAAS experiment: python ai/scripts/test_laas.py."""

import base64
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

AI_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(AI_ROOT))

import laas  # noqa: E402
from app.schemas import DraftResult  # noqa: E402


class ReceiptPromptTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix=".laas-test-", dir=AI_ROOT)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.image = self.root / "sample.jpeg"
        self.image.write_bytes(b"image-bytes-for-transport-test")
        self.draft = DraftResult.model_validate(
            {
                "items": [
                    {
                        "raw_text": "FOOD",
                        "display_name": "Food",
                        "count": None,
                        "unit": None,
                        "storage": None,
                        "confidence": 0.8,
                    }
                ]
            }
        )
        self.client = MagicMock()
        self.message = SimpleNamespace(refusal=None, parsed=self.draft)
        self.client.chat.completions.parse.return_value = SimpleNamespace(
            choices=[SimpleNamespace(message=self.message)]
        )

    def test_loads_shared_prompt_verbatim(self):
        self.assertEqual(
            laas.load_receipt_prompt(),
            (AI_ROOT / "app/prompts/receipt.md").read_text(encoding="utf-8"),
        )

    def test_load_prompt_accepts_file_names_and_stems(self):
        for filename in ("photo.md", "receipt.md", "items.md", "interpret.md"):
            with self.subTest(filename=filename):
                expected = (AI_ROOT / "app/prompts" / filename).read_text(encoding="utf-8")
                self.assertEqual(laas.load_prompt(filename), expected)
                self.assertEqual(laas.load_prompt(Path(filename).stem), expected)

    def test_load_prompt_does_not_depend_on_terminal_folder(self):
        previous = Path.cwd()
        try:
            os.chdir(self.root)
            self.assertEqual(
                laas.load_prompt("photo"),
                (AI_ROOT / "app/prompts/photo.md").read_text(encoding="utf-8"),
            )
        finally:
            os.chdir(previous)

    def test_missing_empty_or_outside_prompt_is_rejected(self):
        for name in ("", "../outside.md", "../../.env"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                laas.load_prompt(name)
        with self.assertRaisesRegex(FileNotFoundError, "Available prompts"):
            laas.load_prompt("nonexistent-test-prompt")
        (self.root / "empty.md").write_text("   ")
        with patch.object(laas, "PROMPT_DIR", self.root), self.assertRaises(ValueError):
            laas.load_prompt("empty")

    def test_default_extraction_sends_prompt_image_and_current_schema(self):
        result = laas.extract_receipt(self.image, self.client, "test-model")
        payload = self.client.chat.completions.parse.call_args.kwargs
        self.assertEqual(
            payload["messages"][0], {"role": "system", "content": laas.load_receipt_prompt()}
        )
        self.assertEqual(payload["response_format"], laas.ExtractionResult)
        self.assertEqual(payload["model"], "test-model")
        image_url = payload["messages"][1]["content"][1]["image_url"]["url"]
        self.assertEqual(
            image_url,
            "data:image/jpeg;base64," + base64.b64encode(self.image.read_bytes()).decode(),
        )
        self.assertNotIn("ingredient_id", result.model_dump()["items"][0])
        self.assertNotIn("price", result.model_dump()["items"][0])

    def test_explicit_prompt_is_preserved(self):
        laas.extract_receipt(self.image, self.client, "test-model", "custom instructions")
        payload = self.client.chat.completions.parse.call_args.kwargs
        self.assertEqual(payload["messages"][0]["content"], "custom instructions")

    def test_structured_receipt_multiplies_extracted_factors_in_python(self):
        for factors, unit, expected in [([2, 225], "g", 450), ([2, 0.5], "kg", 1)]:
            with self.subTest(unit=unit):
                data = self.draft.model_dump()
                data["items"][0].update(
                    count=550, unit=unit, quantity={"factors": factors, "unit": unit}
                )
                self.message.parsed = laas.ExtractionResult.model_validate(data)
                result = laas.extract_receipt(self.image, self.client, "test-model")
                self.assertEqual((result.items[0].count, result.items[0].unit), (expected, unit))
                self.assertNotIn("quantity", result.model_dump()["items"][0])

    def test_printed_unit_is_preserved_without_purchase_count(self):
        self.message.parsed = DraftResult(
            items=[
                self.draft.items[0].model_copy(
                    update={"raw_text": "FOOD 250ML", "count": None, "unit": "ml"}
                )
            ]
        )
        result = laas.extract_receipt(self.image, self.client, "test-model")
        self.assertIsNone(result.items[0].count)
        self.assertEqual(result.items[0].unit, "ml")

    def test_receipt_unit_fallback_only_replaces_null(self):
        for unit in (None, "g", "kg", "ml", "l", "pack", "bottle", "oz", "", "   "):
            with self.subTest(unit=unit):
                self.message.parsed = DraftResult(
                    items=[self.draft.items[0].model_copy(update={"count": 2, "unit": unit})]
                )
                result = laas.extract_receipt(self.image, self.client, "test-model")
                normalized_unit = (unit or "").strip() or "pcs"
                self.assertEqual(
                    result.items[0].unit,
                    normalized_unit,
                )
                self.assertEqual(result.items[0].count, 2)
                self.assertEqual(self.message.parsed.items[0].unit, unit)

    def test_refusal_is_reported(self):
        self.message.refusal = "refused"
        with self.assertRaisesRegex(RuntimeError, "refused"):
            laas.extract_receipt(self.image, self.client, "test-model")

    def test_layout_based_counts_and_supporting_lines_are_preserved(self):
        # Mocked transport checks only: live OCR/layout accuracy is not tested here.
        for raw in ("3 FOOD", "FOOD 3", "3\nFOOD", "FOOD\n3", "FOOD\nQty 3"):
            with self.subTest(raw=raw):
                self.message.parsed = DraftResult(
                    items=[
                        self.draft.items[0].model_copy(
                            update={"raw_text": raw, "count": 3, "unit": None}
                        )
                    ]
                )
                result = laas.extract_receipt(self.image, self.client, "test-model")
                self.assertEqual(result.items[0].count, 3)
                self.assertEqual(result.items[0].raw_text, raw)

    def test_missing_parsed_answer_is_reported(self):
        self.message.parsed = None
        with self.assertRaisesRegex(RuntimeError, "structured receipt"):
            laas.extract_receipt(self.image, self.client, "test-model")

    def test_both_batch_modes_use_receipt_prompt(self):
        environment = {
            "SOCLAAS_BASE_URL": "https://school.example/v1",
            "SOCLAAS_API_KEY": "test-only-key",
            "SOCLAAS_MODEL": "test-model",
        }
        with patch.dict(os.environ, environment), patch.object(laas, "OpenAI") as sdk:
            sdk.return_value.__enter__.return_value = self.client
            with redirect_stdout(StringIO()):
                paths = laas.process_receipts(self.root, self.root / "per-image")
                combined = self.root / "combined.json"
                laas.process_receipts_with_prompt(self.root, combined)
        self.assertEqual(len(paths), 1)
        expected = laas.finalize_receipt_quantities(self.draft).model_dump(mode="json")
        self.assertEqual(json.loads(paths[0].read_text()), expected)
        self.assertEqual(json.loads(combined.read_text()), {self.image.name: expected})
        for call in self.client.chat.completions.parse.call_args_list:
            self.assertEqual(call.kwargs["messages"][0]["content"], laas.load_receipt_prompt())


class CustomImageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix=".laas-test-", dir=AI_ROOT)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.image = self.root / "my image.jpeg"
        self.image.write_bytes(b"image-bytes-for-transport-test")
        environment = patch.dict(
            os.environ,
            {
                "SOCLAAS_BASE_URL": "https://school.example/v1",
                "SOCLAAS_API_KEY": "test-only-key",
                "SOCLAAS_MODEL": "vision-model",
            },
            clear=True,
        )
        environment.start()
        self.addCleanup(environment.stop)
        sdk = patch.object(laas, "OpenAI")
        self.sdk = sdk.start()
        self.addCleanup(sdk.stop)
        self.client = self.sdk.return_value.__enter__.return_value
        self.message = SimpleNamespace(refusal=None, content="My custom answer")
        self.choice = SimpleNamespace(message=self.message, finish_reason="stop")
        self.client.chat.completions.create.return_value = SimpleNamespace(choices=[self.choice])

    def test_custom_image_prompt_is_not_forced_into_receipt_schema(self):
        answer = laas.ask_image(self.image, "Describe the colours, not food.")
        self.assertEqual(answer, "My custom answer")
        payload = self.client.chat.completions.create.call_args.kwargs
        self.assertNotIn("response_format", payload)
        self.assertEqual(len(payload["messages"]), 1)
        self.assertEqual(
            payload["messages"][0]["content"][0]["text"], "Describe the colours, not food."
        )
        self.assertEqual(payload["model"], "vision-model")
        self.client.chat.completions.parse.assert_not_called()
        self.assertEqual(self.sdk.call_args.kwargs["max_retries"], 0)

    def test_model_and_timeout_can_be_overridden(self):
        laas.ask_image(self.image, "Describe this.", model="other-model", timeout=45)
        self.assertEqual(
            self.client.chat.completions.create.call_args.kwargs["model"], "other-model"
        )
        self.assertEqual(self.sdk.call_args.kwargs["timeout"], 45)

    def test_image_model_setting_is_used_when_present(self):
        with patch.dict(os.environ, {"SOCLAAS_IMAGE_MODEL": "image-model"}):
            laas.ask_image(self.image, "Describe this.")
        self.assertEqual(
            self.client.chat.completions.create.call_args.kwargs["model"], "image-model"
        )

    def test_named_prompt_is_forwarded_without_receipt_schema(self):
        with patch.object(laas, "ask_image", return_value="Feature result") as ask:
            self.assertEqual(
                laas.ask_image_with_prompt_file(
                    self.image, "photo", model="another-model", timeout=45
                ),
                "Feature result",
            )
        ask.assert_called_once_with(
            self.image, laas.load_prompt("photo.md"), model="another-model", timeout=45
        )

    def test_new_feature_prompt_files_need_no_code_changes(self):
        prompt_file = self.root / "new-feature.md"
        prompt_file.write_text("My new feature instructions.\n", encoding="utf-8")
        with patch.object(laas, "PROMPT_DIR", self.root):
            self.assertEqual(
                laas.ask_image_with_prompt_file(self.image, "new-feature.md"), "My custom answer"
            )
        payload = self.client.chat.completions.create.call_args.kwargs
        self.assertEqual(
            payload["messages"][0]["content"][0]["text"], "My new feature instructions.\n"
        )
        self.assertNotIn("response_format", payload)

    def test_bad_prompt_does_not_start_an_api_request(self):
        with self.assertRaises(FileNotFoundError):
            laas.ask_image_with_prompt_file(self.image, "nonexistent-test-prompt")
        self.sdk.assert_not_called()

    def test_bad_inputs_do_not_create_a_client(self):
        with self.assertRaises(ValueError):
            laas.ask_image(self.image, "   ")
        with self.assertRaises(FileNotFoundError):
            laas.ask_image(self.root / "missing.jpeg", "Describe this.")
        text_file = self.root / "not-an-image.txt"
        text_file.write_text("not an image")
        with self.assertRaises(ValueError):
            laas.ask_image(text_file, "Describe this.")
        for timeout in (0, -1, float("inf"), float("nan")):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                laas.ask_image(self.image, "Describe this.", timeout=timeout)
        self.sdk.assert_not_called()

    def test_missing_school_settings_never_use_a_default_provider(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            self.assertRaisesRegex(RuntimeError, "Missing school API settings"),
        ):
            laas.ask_image(self.image, "Describe this.")
        self.sdk.assert_not_called()

    def test_empty_refused_or_incomplete_answers_are_reported(self):
        for refusal, content, reason in (
            ("refused", None, "stop"),
            (None, "", "stop"),
            (None, None, "stop"),
            (None, "partial", "length"),
            (None, "filtered", "content_filter"),
        ):
            with self.subTest(reason=reason, content=content):
                self.message.refusal, self.message.content = refusal, content
                self.choice.finish_reason = reason
                with self.assertRaises(RuntimeError):
                    laas.ask_image(self.image, "Describe this.")
        self.client.chat.completions.create.return_value = SimpleNamespace(choices=[])
        with self.assertRaises(RuntimeError):
            laas.ask_image(self.image, "Describe this.")

    def test_main_editable_modes_are_mocked_for_offline_checks(self):
        output = StringIO()
        with (
            patch.object(laas, "ask_image") as ask,
            patch.object(laas, "ask_image_with_prompt_file", return_value="Answer"),
            patch.object(laas, "process_receipts_with_prompt") as receipt_test,
        ):
            with redirect_stdout(output):
                self.assertIsNone(laas.main())
        ask.assert_not_called()
        receipt_test.assert_not_called()
        self.assertEqual(output.getvalue(), "Answer\n")

    def test_real_sdk_request_uses_school_chat_completions_with_mock_transport(self):
        from importlib import import_module
        from inspect import signature

        from openai import OpenAI

        # Use the transport bundled with the installed SDK (httpx2 in newer SDKs).
        httpx = import_module("httpx2" if "httpx2." in str(signature(OpenAI)) else "httpx")
        requests = []

        def respond(request):
            requests.append(request)
            return httpx.Response(
                200,
                json={
                    "id": "chatcmpl-test",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "vision-model",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": "A custom answer"},
                            "finish_reason": "stop",
                        }
                    ],
                },
            )

        self.sdk.return_value = OpenAI(
            api_key="test-only-key",
            base_url="https://school.example/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(respond)),
        )
        self.assertEqual(laas.ask_image(self.image, "My custom question"), "A custom answer")
        payload = json.loads(requests[0].content)
        self.assertEqual(str(requests[0].url), "https://school.example/v1/chat/completions")
        self.assertEqual(requests[0].headers["Authorization"], "Bearer test-only-key")
        self.assertEqual(payload["messages"][0]["content"][0]["text"], "My custom question")
        self.assertEqual(
            payload["messages"][0]["content"][1]["image_url"]["url"],
            "data:image/jpeg;base64," + base64.b64encode(self.image.read_bytes()).decode(),
        )
        self.assertNotIn("response_format", payload)


if __name__ == "__main__":
    unittest.main()
