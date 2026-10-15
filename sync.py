"""
sync.py

Pulls the upstream AltStore/SideStore repo manifest, downloads each app's
IPA, verifies/corrects the bundleIdentifier against what's actually baked
into the binary (fixes SideStore's VerificationError 1), and writes the
corrected manifest to docs/repo.json for GitHub Pages to serve.

Run manually:
    python sync.py

Environment variables (all optional, have sane defaults):
    UPSTREAM_URL      default: https://repo.ballermc.com/repo.json
    OUTPUT_DIR        default: docs
    IPA_CACHE_DIR     default: .ipa_cache   (not committed, see .gitignore)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

from fix_bundle_ids import (
    BundleIdExtractionError,
    get_bundle_id_from_ipa,
    reconcile_app_entry,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("sync")

UPSTREAM_URL = os.environ.get("UPSTREAM_URL", "https://repo.ballermc.com/repo.json")
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "docs"))
IPA_CACHE_DIR = Path(os.environ.get("IPA_CACHE_DIR", ".ipa_cache"))

REQUEST_TIMEOUT = 60  # seconds, per HTTP request
MAX_IPA_BYTES = 2 * 1024 * 1024 * 1024  # 2 GB safety cap per file


def fetch_upstream_manifest(url: str) -> dict:
    log.info("Fetching upstream manifest: %s", url)
    resp = requests.get(url, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def filename_for(url: str, fallback: str) -> str:
    name = Path(urlparse(url).path).name
    return name if name.endswith(".ipa") else f"{fallback}.ipa"


def download_ipa(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log.info("Using cached IPA: %s", dest.name)
        return dest

    log.info("Downloading %s", url)
    with requests.get(url, stream=True, timeout=REQUEST_TIMEOUT) as resp:
        resp.raise_for_status()
        total = 0
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                total += len(chunk)
                if total > MAX_IPA_BYTES:
                    raise RuntimeError(f"{url} exceeded {MAX_IPA_BYTES} byte safety cap")
                f.write(chunk)
    return dest


def process_app(app: dict) -> None:
    """
    Reconcile the top-level app entry (using its primary/newest IPA) and
    every entry in its "versions" array (each version can ship a different
    binary with its own actual bundle id).
    """
    name = app.get("name", "<unknown>")

    # Primary download, if the schema has one at the top level.
    primary_url = app.get("downloadURL")
    if primary_url:
        dest = IPA_CACHE_DIR / filename_for(primary_url, app.get("bundleIdentifier", name))
        try:
            ipa_path = download_ipa(primary_url, dest)
            real_id = get_bundle_id_from_ipa(ipa_path)
            reconcile_app_entry(app, real_id)
        except (requests.RequestException, BundleIdExtractionError, RuntimeError) as e:
            log.error("Failed to process %r (top-level): %s", name, e)

    # Per-version downloads.
    for version in app.get("versions", []) or []:
        v_url = version.get("downloadURL")
        if not v_url:
            continue
        dest = IPA_CACHE_DIR / filename_for(v_url, f"{app.get('bundleIdentifier', name)}-{version.get('version','v')}")
        try:
            ipa_path = download_ipa(v_url, dest)
            real_id = get_bundle_id_from_ipa(ipa_path)
            if version.get("bundleIdentifier") and version["bundleIdentifier"] != real_id:
                log.warning(
                    "%r version %s: declared %r but IPA has %r -> correcting",
                    name, version.get("version"), version.get("bundleIdentifier"), real_id,
                )
                version["bundleIdentifier"] = real_id
        except (requests.RequestException, BundleIdExtractionError, RuntimeError) as e:
            log.error("Failed to process %r version %s: %s", name, version.get("version"), e)


def main() -> int:
    try:
        manifest = fetch_upstream_manifest(UPSTREAM_URL)
    except Exception as e:
        log.error("Could not fetch upstream manifest: %s", e)
        return 1

    apps = manifest.get("apps", [])
    log.info("Processing %d app(s)", len(apps))

    IPA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for app in apps:
        process_app(app)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "repo.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    log.info("Wrote corrected manifest to %s", out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
