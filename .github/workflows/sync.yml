"""
fix_bundle_ids.py

Drop-in helper for the tubevault-sidestore GitHub Actions sync script.

Problem:
    repo.json (mirrored from https://repo.ballermc.com/repo.json) declares a
    top-level "bundleIdentifier" per app, e.g. "com.google.ios.youtube".
    The actual IPA binary for modded variants often has a different
    CFBundleIdentifier baked into Info.plist, e.g.
    "com.google.ios.youtube.ytplus...".

    SideStore's local signer reads the *real* CFBundleIdentifier out of the
    IPA and compares it against what the source manifest claims. A mismatch
    throws VerificationError 1 and blocks install.

Fix:
    Don't trust the upstream JSON's bundleIdentifier. Open each mirrored IPA,
    read the real CFBundleIdentifier out of Payload/*.app/Info.plist, and use
    that value (and only that value) when writing bundleIdentifier (and any
    per-version bundleIdentifier field) into your generated repo.json.

Usage (integrate into your existing sync workflow):

    from fix_bundle_ids import get_bundle_id_from_ipa, reconcile_app_entry

    for app in repo_data["apps"]:
        ipa_path = download_ipa(app)  # however your script already does this
        real_id = get_bundle_id_from_ipa(ipa_path)
        reconcile_app_entry(app, real_id)
"""

from __future__ import annotations

import plistlib
import zipfile
import logging
from pathlib import Path
from typing import Optional

log = logging.getLogger("fix_bundle_ids")


class BundleIdExtractionError(RuntimeError):
    pass


def get_bundle_id_from_ipa(ipa_path: str | Path) -> str:
    """
    Open an .ipa (which is just a zip) and return the CFBundleIdentifier
    declared in the main app's Info.plist. This is the value SideStore's
    signer will actually check against, so it's the only value worth trusting.
    """
    ipa_path = Path(ipa_path)
    if not ipa_path.exists():
        raise FileNotFoundError(f"IPA not found: {ipa_path}")

    with zipfile.ZipFile(ipa_path) as zf:
        # The main app bundle's Info.plist lives at
        # Payload/<AppName>.app/Info.plist — find it without assuming the name.
        candidates = [
            n
            for n in zf.namelist()
            if n.startswith("Payload/")
            and n.count("/") == 2
            and n.endswith(".app/Info.plist")
        ]
        if not candidates:
            raise BundleIdExtractionError(
                f"No Info.plist found at Payload/*.app/Info.plist in {ipa_path.name}"
            )
        # If there are multiple (rare, e.g. app extensions nested oddly),
        # prefer the shortest path, which is almost always the main app.
        candidates.sort(key=len)
        info_plist_path = candidates[0]

        with zf.open(info_plist_path) as f:
            try:
                plist_data = plistlib.load(f)
            except Exception as e:
                raise BundleIdExtractionError(
                    f"Failed to parse {info_plist_path} in {ipa_path.name}: {e}"
                ) from e

    bundle_id = plist_data.get("CFBundleIdentifier")
    if not bundle_id:
        raise BundleIdExtractionError(
            f"CFBundleIdentifier missing from {info_plist_path} in {ipa_path.name}"
        )
    return bundle_id


def reconcile_app_entry(app_entry: dict, real_bundle_id: str, *, log_mismatches: bool = True) -> dict:
    """
    Mutate (and return) a single app's dict from repo.json so its declared
    bundleIdentifier matches the real one baked into the IPA. Also walks any
    per-version entries (AltStore/SideStore schemas commonly carry a
    "versions" array, each of which can independently specify a
    bundleIdentifier override) and corrects those too.
    """
    declared = app_entry.get("bundleIdentifier")
    if declared != real_bundle_id:
        if log_mismatches:
            log.warning(
                "bundleIdentifier mismatch for %r: upstream declared %r, "
                "IPA actually contains %r -> correcting to match IPA",
                app_entry.get("name", "<unknown>"),
                declared,
                real_bundle_id,
            )
        app_entry["bundleIdentifier"] = real_bundle_id

    for version in app_entry.get("versions", []) or []:
        if "bundleIdentifier" in version and version["bundleIdentifier"] != real_bundle_id:
            version["bundleIdentifier"] = real_bundle_id

    return app_entry


def reconcile_repo(repo_data: dict, ipa_lookup) -> dict:
    """
    Convenience wrapper for a full sync pass.

    ipa_lookup: callable(app_entry: dict) -> Path | str
        Given one app's dict from repo.json, return the local filesystem
        path to the IPA your workflow already downloaded/mirrored for it.
        (Your existing sync script presumably already does this download —
        just point this function at that same file.)
    """
    failures = []
    for app in repo_data.get("apps", []):
        try:
            ipa_path = ipa_lookup(app)
            real_id = get_bundle_id_from_ipa(ipa_path)
            reconcile_app_entry(app, real_id)
        except (BundleIdExtractionError, FileNotFoundError) as e:
            # Don't let one bad IPA kill the whole sync run — log it and
            # keep the upstream-declared value for that one entry so the
            # rest of the catalog still publishes.
            log.error("Could not reconcile %r: %s", app.get("name", "<unknown>"), e)
            failures.append((app.get("name", "<unknown>"), str(e)))

    if failures:
        log.warning("%d app(s) could not be verified/reconciled: %s", len(failures), failures)

    return repo_data


if __name__ == "__main__":
    import argparse
    import json

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    parser = argparse.ArgumentParser(
        description="Check or fix bundleIdentifier fields in repo.json against real IPA contents."
    )
    parser.add_argument("repo_json", help="Path to repo.json to check/fix")
    parser.add_argument(
        "--ipa-dir",
        required=True,
        help="Directory containing downloaded IPAs, named <bundle-slug>.ipa or matching app['downloadURL'] basename",
    )
    parser.add_argument("--write", action="store_true", help="Write corrected repo.json back to disk")
    args = parser.parse_args()

    repo_path = Path(args.repo_json)
    ipa_dir = Path(args.ipa_dir)

    with open(repo_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    def lookup(app_entry: dict) -> Path:
        # Adjust this to however your workflow actually names mirrored files.
        url = app_entry.get("downloadURL", "")
        filename = url.rsplit("/", 1)[-1] if url else f"{app_entry.get('bundleIdentifier','unknown')}.ipa"
        return ipa_dir / filename

    reconcile_repo(data, lookup)

    if args.write:
        with open(repo_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        log.info("Wrote corrected %s", repo_path)
    else:
        print(json.dumps(data, indent=2))
