#!/usr/bin/env python3
"""
TubeVault -> static site, so people stop hunting through Reddit for links.

Reads BallerMC's repo.json, groups builds by app, writes index.html. Every
build gets its own install button using altstore://, because TubeVault's
fake bundle IDs (com.google.ios.youtube.ytplus.cracked....) make SideStore
refuse to touch them.

Doesn't host, sign, or modify anything. Just shuffles metadata around.

Not a dev, just got tired of things being broken.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SRC = Path("repo.json")
OUT_HTML = Path("index.html")

# --------------------------------------------------------------------------
# tune these
# --------------------------------------------------------------------------
REPO_NAME     = "TubeVault for SideStore (Unofficial)"
REPO_SUBTITLE = "BallerMC's TubeVault builds, reorganised for SideStore."
REPO_TINT     = "#848ef9"
REPO_ICON     = "https://repo.ballermc.com/TubeVault%20Icon.png"
KOFI_URL = "https://ko-fi.com/ravier1"

# each row here = one card on the page. add more if BallerMC ever ships
# something new that needs its own section.
#
# logo URLs are from simple-icons on jsDelivr. if you want to self-host,
# drop youtube.svg / youtubemusic.svg / spotify.svg into an icons/ folder
# and point at https://<yourname>.github.io/tubevault-sidestore/icons/*.svg
# instead. either works, the CDN one just means less to maintain.
BASE_APPS = [
    # YT Music first, so "YouTube Music" never falls into the plain YouTube
    # bucket. Its real bundle ID is com.google.ios.youtube.music (or .ytmusic
    # on some builds), so we match that prefix too.
    {
        "key": "youtube_music",
        "display": "YouTube Music (Tweaked Builds)",
        "id_prefixes": [
            "com.google.ios.youtube.music",
            "com.google.ios.youtubemusic",
            "com.google.ios.ytmusic",
        ],
        "name_re": re.compile(r"\b(?:YouTube\s*Music|YTM(?:usic)?)\b", re.IGNORECASE),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/6/6a/Youtube_Music_icon.svg?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original",
        "tint": "#FF0000",
    },
    # Plain YouTube next. The negative lookahead stops it from grabbing
    # "YouTube Music" if that string ever slips past the rule above.
    {
        "key": "youtube",
        "display": "YouTube (Tweaked Builds)",
        "id_prefixes": ["com.google.ios.youtube"],
        "name_re": re.compile(r"\bYouTube\b(?!\s*Music)", re.IGNORECASE),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/0/09/YouTube_full-color_icon_%282017%29.svg?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original",
        "tint": "#FF0000",
    },
    {
        "key": "spotify",
        "display": "Spotify (Tweaked Builds)",
        "id_prefixes": ["com.spotify.client", "com.spotify"],
        "name_re": re.compile(r"\bSpotify\b", re.IGNORECASE),
        "logo": "https://upload.wikimedia.org/wikipedia/commons/8/84/Spotify_icon.svg?utm_source=commons.wikimedia.org&utm_campaign=index&utm_content=original",
        "tint": "#1DB954",
    },
]
# anything that doesn't match the above lands here so it doesn't vanish
FALLBACK = {
    "key": "other",
    "display": "Other Tweaked Apps",
    "logo": REPO_ICON,
    "tint": REPO_TINT,
}


def detect_base(app):
    """Match on bundle ID first (more reliable than names), then fall back
    to the name regex. Order in BASE_APPS matters: YT Music before YouTube
    so com.google.ios.youtube.music doesn't get caught by the plain prefix."""
    bid = (app.get("bundleIdentifier") or "").lower()
    for spec in BASE_APPS:
        if any(bid.startswith(p) for p in spec["id_prefixes"]):
            return spec
    name = app.get("name") or ""
    for spec in BASE_APPS:
        if spec["name_re"].search(name):
            return spec
    return FALLBACK


def human_name(raw):
    """Strip 'Cracked' and clean up double spaces. 'YTPlus/YTLite Cracked
    (6.0 Beta 2)' -> 'YTPlus/YTLite (6.0 Beta 2)'."""
    n = re.sub(r"\bCracked\b", "", raw, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", n).strip(" -+")


def base_version(app):
    """The YouTube/Spotify version this build is based on. '?' if missing."""
    try:
        return str(app["versions"][0]["version"]).strip()
    except Exception:
        return "?"


def make_version(app):
    v = app["versions"][0]
    parts = []
    if base_version(app) != "?":
        parts.append(f"Based on version {base_version(app)}.")
    if app.get("subtitle"):
        parts.append(app["subtitle"].strip())
    if v.get("localizedDescription"):
        parts.append(v["localizedDescription"].strip())
    parts.append("Credit: BallerMC / TubeVault.")
    return {
        "version": human_name(app["name"]),
        "date": v.get("date") or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "localizedDescription": "\n\n".join(parts).strip(),
        "downloadURL": v["downloadURL"],
        "size": v["size"],
    }


def dedupe(versions):
    # BallerMC occasionally ships two entries pointing at the same IPA.
    # Same downloadURL = same build, keep the first one we see.
    # "Do not be sorry. Be better." — the dedupe logic, every single time.
    seen, out = set(), []
    for v in versions:
        if v["downloadURL"] in seen:
            continue
        seen.add(v["downloadURL"])
        out.append(v)
    return out


def make_app_entry(spec, versions):
    versions = sorted(dedupe(versions), key=lambda v: v.get("date", ""), reverse=True)
    base_name = spec["display"].split(" (")[0]
    return {
        "name": spec["display"],
        "key": spec["key"],
        "logo": spec["logo"],
        "tint": spec["tint"],
        "subtitle": f"Modified builds of {base_name} — install one at a time.",
        "versions": versions,
    }


def build_site_html(apps, generated_at):
    import json as _json
    payload = {"apps": apps}
    data_json = _json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    timestamp = generated_at.strftime("%Y-%m-%d %H:%M UTC")
    tint = REPO_TINT

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#0f1115">
<title>{REPO_NAME}</title>
<style>
:root {{
  --bg:#0f1115; --card:#1a1d24; --border:#2a2e38;
  --text:#e7e9ee; --muted:#8b90a0;
  --accent:{tint}; --accent-hover:#6b78e8;
}}
* {{ box-sizing:border-box; -webkit-tap-highlight-color:transparent; }}
body {{
  margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:var(--bg); color:var(--text); line-height:1.5; min-height:100vh;
}}
header {{
  padding:20px 18px 14px; border-bottom:1px solid var(--border);
  position:sticky; top:0; background:var(--bg); z-index:10;
}}
header h1 {{ margin:0 0 4px; font-size:19px; }}
.subtitle {{ margin:0 0 6px; color:var(--muted); font-size:13px; }}
.updated {{ margin:0; color:var(--muted); font-size:11px; }}
.search {{
  margin:14px 0 0; padding:10px 14px; width:100%;
  background:var(--card); border:1px solid var(--border);
  border-radius:10px; color:var(--text); font-size:15px;
  -webkit-appearance:none;
}}
.search:focus {{ outline:none; border-color:var(--accent); }}
.count {{ margin:8px 0 0; color:var(--muted); font-size:12px; }}
main {{ padding:14px 18px 60px; max-width:820px; margin:0 auto; }}
.app {{
  background:var(--card); border:1px solid var(--border);
  border-radius:14px; margin:14px 0; overflow:hidden;
}}
.app-header {{
  display:flex; align-items:center; gap:12px; width:100%;
  padding:14px 16px; background:none; border:none; cursor:pointer;
  text-align:left; color:inherit; font:inherit;
}}
.app-header:focus {{ outline:none; }}
.app-header:active {{ background:rgba(255,255,255,0.03); }}
.app-logo {{
  width:34px; height:34px; flex-shrink:0; object-fit:contain;
  border-radius:8px; background:rgba(255,255,255,0.05); padding:4px;
}}
.app-titles {{ flex:1; min-width:0; }}
.app-header h2 {{ margin:0 0 2px; font-size:16px; font-weight:600; }}
.app-header p {{ margin:0; font-size:12px; color:var(--muted); }}
.app-chevron {{
  color:var(--muted); font-size:18px; transition:transform 0.2s;
  user-select:none;
}}
.app.collapsed .app-chevron {{ transform:rotate(-90deg); }}
.app.collapsed .app-body {{ display:none; }}
.app-note {{
  padding:10px 16px; font-size:12px; color:var(--muted);
  background:rgba(255,255,255,0.02); border-top:1px solid var(--border);
  border-bottom:1px solid var(--border);
}}
.version {{ padding:14px 16px; border-bottom:1px solid var(--border); }}
.version:last-child {{ border-bottom:none; }}
.version-head {{
  display:flex; justify-content:space-between; align-items:flex-start;
  gap:10px; margin-bottom:6px;
}}
.version-name {{ font-weight:600; font-size:14px; flex:1; word-break:break-word; }}
.version-date {{ color:var(--muted); font-size:11px; white-space:nowrap; padding-top:2px; }}
.version-desc {{
  margin:0 0 10px; color:var(--muted); font-size:13px;
  white-space:pre-wrap; word-break:break-word;
  max-height:4.5em; overflow:hidden; position:relative;
  transition:max-height 0.2s;
}}
.version-desc.expanded {{ max-height:none; }}
.version-desc:not(.expanded)::after {{
  content:''; position:absolute; bottom:0; left:0; right:0; height:1.5em;
  background:linear-gradient(transparent, var(--card)); pointer-events:none;
}}
.actions {{ display:flex; gap:8px; flex-wrap:wrap; }}
.btn {{
  padding:9px 16px; border-radius:10px; font-size:13px; font-weight:500;
  text-decoration:none; border:none; cursor:pointer; display:inline-block;
  -webkit-appearance:none;
}}
.btn-primary {{ background:var(--accent); color:#fff; }}
.btn-primary:active {{ background:var(--accent-hover); }}
.btn-secondary {{
  background:transparent; color:var(--text); border:1px solid var(--border);
}}
.expand-btn {{
  background:none; border:none; color:var(--accent);
  font-size:12px; cursor:pointer; padding:0; margin-top:6px;
}}
.empty {{ text-align:center; color:var(--muted); padding:40px 20px; }}
.credit {{ text-align:center; color:var(--muted); font-size:11px; margin-top:30px; padding:0 18px; }}
.credit a {{ color:var(--accent); }}
</style>
</head>
<body>
<header>
  <h1>{REPO_NAME}</h1>
  <p class="subtitle">{REPO_SUBTITLE}</p>
  <p class="updated">Last updated: {timestamp}</p>
  <p class="updated"><a href="{KOFI_URL}" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:none;">☕ Buy me a coffee</a></p>
  <input type="search" class="search" id="search" placeholder="Search builds…" autocomplete="off">
  <p class="count" id="count"></p>
</header>
<main id="main"></main>
<div class="credit">
  Unofficial index · credit to <a href="https://github.com/ballermc" target="_blank" rel="noopener">BallerMC / TubeVault</a>
</div>

<script id="data" type="application/json">{data_json}</script>
<script>
console.log('%cBOY.', 'color:#e33;font-size:28px;font-weight:bold;');
console.log('%c"Don\\'t be sorry. Be better." — Kratos, God of War (2018)', 'color:#888;font-style:italic;');
console.log('%c↑ you found the easter egg. nice. now go install a build.', 'color:#666;');

const DATA = JSON.parse(document.getElementById('data').textContent);
const main = document.getElementById('main');
const search = document.getElementById('search');
const countEl = document.getElementById('count');
const expandedDesc = new Set();
const collapsedCats = new Set(
  JSON.parse(localStorage.getItem('tubevault.collapsed') || '[]')
);

function saveCollapsed() {{
  localStorage.setItem('tubevault.collapsed', JSON.stringify([...collapsedCats]));
}}

function esc(s) {{
  return String(s).replace(/[&<>"']/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
}}

function render() {{
  const q = search.value.trim().toLowerCase();
  main.innerHTML = '';
  let total = 0;

  for (const app of DATA.apps) {{
    const matches = q
      ? app.versions.filter(v =>
          v.version.toLowerCase().includes(q) ||
          (v.localizedDescription || '').toLowerCase().includes(q))
      : app.versions;
    if (matches.length === 0) continue;
    total += matches.length;

    const catKey = app.key;
    const isCollapsed = collapsedCats.has(catKey);

    const appEl = document.createElement('div');
    appEl.className = 'app' + (isCollapsed ? ' collapsed' : '');

    const logoSrc = app.logo || '';
    const header = document.createElement('button');
    header.className = 'app-header';
    header.setAttribute('aria-expanded', String(!isCollapsed));
    header.innerHTML =
      (logoSrc ? '<img class="app-logo" src="' + esc(logoSrc) + '" alt="" loading="lazy">' : '') +
      '<div class="app-titles">' +
        '<h2>' + esc(app.name) + '</h2>' +
        '<p>' + esc(app.subtitle || '') + '</p>' +
      '</div>' +
      '<span class="app-chevron">▾</span>';
    header.addEventListener('click', () => {{
      if (collapsedCats.has(catKey)) collapsedCats.delete(catKey);
      else collapsedCats.add(catKey);
      saveCollapsed();
      render();
    }});
    appEl.appendChild(header);

    const body = document.createElement('div');
    body.className = 'app-body';

    const note = document.createElement('div');
    note.className = 'app-note';
    note.textContent = 'All builds share the same bundle ID — installing one replaces any other.';
    body.appendChild(note);

    for (const v of matches) {{
      const vEl = document.createElement('div');
      vEl.className = 'version';
      const date = (v.date || '').slice(0, 10);
      const key = app.key + '|' + v.downloadURL;
      const isExp = expandedDesc.has(key);
      const encoded = encodeURIComponent(v.downloadURL);
      const sideUrl = 'sidestore://install?url=' + encoded;
      const altUrl  = 'altstore://install?url=' + encoded;

      vEl.innerHTML =
        '<div class="version-head">' +
          '<div class="version-name">' + esc(v.version) + '</div>' +
          '<div class="version-date">' + esc(date) + '</div>' +
        '</div>' +
        '<div class="version-desc' + (isExp ? ' expanded' : '') + '">' +
          esc(v.localizedDescription) +
        '</div>' +
        '<div class="actions">' +
          '<a class="btn btn-primary" href="' + esc(sideUrl) + '">Install in SideStore</a>' +
          '<a class="btn btn-primary" href="' + esc(altUrl) + '">Install in AltStore</a>' +
          '<a class="btn btn-secondary" href="' + esc(v.downloadURL) + '" target="_blank" rel="noopener">Download IPA</a>' +
        '</div>' +
        '<button class="expand-btn" data-key="' + esc(key) + '">' +
          (isExp ? 'Show less' : 'Show more') +
        '</button>';
      body.appendChild(vEl);
    }}

    appEl.appendChild(body);
    main.appendChild(appEl);
  }}

  countEl.textContent = total + ' build' + (total === 1 ? '' : 's');
  if (total === 0) {{
    main.innerHTML = '<div class="empty">No builds match your search.</div>';
  }}

  main.querySelectorAll('.expand-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const k = btn.dataset.key;
      if (expandedDesc.has(k)) expandedDesc.delete(k);
      else expandedDesc.add(k);
      render();
    }});
  }});
}}

search.addEventListener('input', render);
render();
</script>

<!--
  "Don't be sorry. Be better."
     — Kratos, God of War (2018)

  You're reading source of a page that lists modded YouTube builds.
  That's the easter egg. There's also a console message. Now go outside.
-->
</body>
</html>"""


def main():
    if not SRC.exists():
        print(f"ERROR: {SRC} not found. Run from the repo root.", file=sys.stderr)
        sys.exit(1)

    src = json.loads(SRC.read_text(encoding="utf-8"))

    buckets = {}
    for app in src.get("apps", []):
        spec = detect_base(app)
        buckets.setdefault(spec["key"], {"spec": spec, "versions": []})
        buckets[spec["key"]]["versions"].append(make_version(app))

    apps_out = []
    for key in ("youtube", "youtube_music", "spotify", "other"):
        if key not in buckets:
            continue
        b = buckets[key]
        apps_out.append(make_app_entry(b["spec"], b["versions"]))

    now = datetime.now(timezone.utc)
    OUT_HTML.write_text(build_site_html(apps_out, now), encoding="utf-8")

    summary = ", ".join(f"{a['name']}={len(a['versions'])}" for a in apps_out)
    print(f"Wrote {OUT_HTML} — {len(apps_out)} categories: {summary}")


if __name__ == "__main__":
    main()