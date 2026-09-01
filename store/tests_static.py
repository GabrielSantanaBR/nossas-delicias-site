import json
import re
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.storage import staticfiles_storage
from django.test import SimpleTestCase


STATIC_TAG_RE = re.compile(r"{%\s*static\s+['\"]([^'\"]+)['\"]\s*%}")
CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", re.IGNORECASE)


class StaticReferenceAuditTests(SimpleTestCase):
    """Keep source static references honest before WhiteNoise builds the manifest."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_root = Path(settings.BASE_DIR) / "static"
        cls.template_root = Path(settings.BASE_DIR) / "templates"

    def _template_static_assets(self):
        for template_path in self.template_root.rglob("*.html"):
            content = template_path.read_text(encoding="utf-8")
            for asset in STATIC_TAG_RE.findall(content):
                if not asset.startswith(("http://", "https://", "data:")):
                    yield template_path, asset

    def test_every_template_static_tag_points_to_a_real_source_file(self):
        missing = []
        for template_path, asset in self._template_static_assets():
            source = self.static_root / asset
            if not source.is_file():
                missing.append(f"{template_path.relative_to(settings.BASE_DIR)} -> {asset}")

        self.assertFalse(missing, "Missing {% static %} sources:\n" + "\n".join(sorted(missing)))

    def test_manifest_storage_resolves_every_template_static_tag(self):
        missing = []
        for template_path, asset in self._template_static_assets():
            try:
                staticfiles_storage.url(asset)
            except ValueError as exc:
                missing.append(f"{template_path.relative_to(settings.BASE_DIR)} -> {asset}: {exc}")

        self.assertFalse(
            missing,
            "Staticfiles manifest could not resolve template assets:\n" + "\n".join(sorted(missing)),
        )

    def test_every_local_css_url_points_to_a_real_source_file(self):
        missing = []
        for css_path in self.static_root.rglob("*.css"):
            content = css_path.read_text(encoding="utf-8")
            for raw_url in CSS_URL_RE.findall(content):
                raw_url = raw_url.strip()
                if not raw_url or raw_url.startswith(("http://", "https://", "//", "data:", "#")):
                    continue

                path = urlsplit(raw_url).path
                if path.startswith("/static/"):
                    source = self.static_root / path.removeprefix("/static/")
                else:
                    source = css_path.parent / path

                if not source.is_file():
                    missing.append(f"{css_path.relative_to(settings.BASE_DIR)} -> {raw_url}")

        self.assertFalse(missing, "Missing local CSS url() assets:\n" + "\n".join(sorted(missing)))

    def test_webmanifest_local_icons_point_to_existing_files(self):
        missing = []
        manifests = list(Path(settings.BASE_DIR).rglob("*.webmanifest"))
        for manifest_path in manifests:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
            for icon in data.get("icons", []):
                raw_src = str(icon.get("src", "")).strip()
                if not raw_src or raw_src.startswith(("http://", "https://", "data:")):
                    continue

                path = urlsplit(raw_src).path
                if path.startswith("/static/"):
                    source = self.static_root / path.removeprefix("/static/")
                elif path.startswith("/"):
                    source = Path(settings.BASE_DIR) / path.removeprefix("/")
                else:
                    source = manifest_path.parent / path

                if not source.is_file():
                    missing.append(f"{manifest_path.relative_to(settings.BASE_DIR)} -> {raw_src}")

        self.assertFalse(missing, "Missing webmanifest icon assets:\n" + "\n".join(sorted(missing)))

    def test_all_template_static_assets_are_discoverable_by_django(self):
        missing = []
        for template_path, asset in self._template_static_assets():
            if finders.find(asset) is None:
                missing.append(f"{template_path.relative_to(settings.BASE_DIR)} -> {asset}")

        self.assertFalse(missing, "Django staticfiles finders could not resolve:\n" + "\n".join(sorted(missing)))
