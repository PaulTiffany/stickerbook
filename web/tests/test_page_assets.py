"""Tests for canonical page art sizing and OpenRouter request construction."""

from __future__ import annotations

import base64
import unittest

import image_gateway
import page_assets
import page_image_runtime


class PageAssetSpecificationTests(unittest.TestCase):

    def test_canonical_page_dimensions_are_exact(self):
        self.assertEqual(
            (page_assets.LANDSCAPE_WIDTH, page_assets.LANDSCAPE_HEIGHT),
            (1916, 717))
        self.assertEqual(
            (page_assets.PORTRAIT_WIDTH, page_assets.PORTRAIT_HEIGHT),
            (941, 1574))

    def test_prompts_pin_the_expected_canvas_sizes_and_edit_semantics(self):
        self.assertIn("exactly 1916 × 717", page_assets.LANDSCAPE_PROMPT)
        self.assertIn("exactly 941 × 1574", page_assets.PORTRAIT_PROMPT)
        for prompt in (
                page_assets.LANDSCAPE_PROMPT,
                page_assets.PORTRAIT_PROMPT):
            self.assertIn("Do not create a new scene", prompt)
            self.assertIn("Do not reinterpret the content", prompt)
            self.assertIn("reframe / extend / outpaint", prompt)
            self.assertIn("rather than stretching or distorting", prompt)

    def test_generation_plan_uses_horizontal_and_vertical_naming(self):
        plan = page_assets.generation_plan("My Garden.jpeg")
        self.assertEqual(plan["landscape"]["stem"], "My-Garden")
        self.assertEqual(plan["portrait"]["stem"], "My-Garden-vertical")
        self.assertEqual(
            page_assets.variant_filename(
                "My Garden.jpeg", "landscape", "png"),
            "My-Garden.png")
        self.assertEqual(
            page_assets.variant_filename(
                "My Garden.jpeg", "portrait", "webp"),
            "My-Garden-vertical.webp")

    def test_supported_page_formats_are_data_only_images(self):
        for filename, content_type in (
                ("page.svg", "image/svg+xml"),
                ("page.png", "image/png"),
                ("page.jpg", "image/jpeg"),
                ("page.jpeg", "image/jpeg"),
                ("page.webp", "image/webp")):
            self.assertTrue(
                page_assets.supported_upload(filename, content_type),
                (filename, content_type))
        self.assertFalse(
            page_assets.supported_upload("page.html", "text/html"))
        self.assertFalse(
            page_assets.supported_upload("page.exe", "image/png"))


class PageImageRuntimeBoundaryTests(unittest.TestCase):

    def test_gateway_client_is_loopback_only(self):
        with self.assertRaises(ValueError):
            page_image_runtime.GatewayPageImageRuntime(
                "https://example.com")
        with self.assertRaises(ValueError):
            page_image_runtime.GatewayPageImageRuntime(
                "http://user:pass@127.0.0.1:8757")

        runtime = page_image_runtime.GatewayPageImageRuntime(
            "http://127.0.0.1:8757")
        self.assertTrue(runtime.available())


class OpenRouterImageRequestTests(unittest.TestCase):

    def test_generated_dimensions_are_read_mechanically(self):
        png = (
            b"\x89PNG\r\n\x1a\n"
            + b"\x00\x00\x00\x0dIHDR"
            + (1916).to_bytes(4, "big")
            + (717).to_bytes(4, "big")
        )
        self.assertEqual(
            image_gateway.image_dimensions(png, "image/png"),
            (1916, 717),
        )

        svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg" '
            b'width="941" height="1574" viewBox="0 0 941 1574"/>'
        )
        self.assertEqual(
            image_gateway.image_dimensions(svg, "image/svg+xml"),
            (941, 1574),
        )

    def test_reference_image_and_exact_target_prompt_are_sent_to_openrouter(self):
        raw = b"sample-image-bytes"
        payload = image_gateway.build_openrouter_payload(
            model="example/image-model",
            image_bytes=raw,
            content_type="image/png",
            prompt=page_assets.LANDSCAPE_PROMPT,
            width=1916,
            height=717,
        )

        self.assertEqual(payload["model"], "example/image-model")
        self.assertEqual(payload["prompt"], page_assets.LANDSCAPE_PROMPT)
        self.assertNotIn("size", payload)
        self.assertIn("exactly 1916 × 717", payload["prompt"])
        self.assertEqual(payload["n"], 1)

        reference = payload["input_references"][0]
        self.assertEqual(reference["type"], "image_url")
        url = reference["image_url"]["url"]
        self.assertTrue(url.startswith("data:image/png;base64,"))
        encoded = url.split(",", 1)[1]
        self.assertEqual(base64.b64decode(encoded), raw)


if __name__ == "__main__":
    unittest.main()
