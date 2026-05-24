"""Generate pixel art UI assets via RouterAI image models."""
import base64
import json
import sys
import urllib.request
from pathlib import Path

from promptgate.keystore import get_key

UI_DIR = Path(__file__).parent.parent / "promptgate" / "ui" / "img"
UI_DIR.mkdir(parents=True, exist_ok=True)

PROFILE = "routerai"
MODEL = "google/gemini-2.5-flash-image"
API_BASE = "https://routerai.ru/api/v1"

# Shared style suffix injected into every prompt for visual consistency
_STYLE = (
    "pixel art, 8-bit retro game style, warm beige and oak wood palette, "
    "clean pixel edges, no anti-aliasing, flat colors, no gradients"
)

ASSETS = [
    # ── backgrounds / textures ───────────────────────────────────────────────
    {
        "name": "wood_header",
        "file": "wood_header.png",
        "prompt": (
            f"seamless tileable wooden plank floor texture, light oak grain, "
            f"horizontal plank lines, warm amber honey tones, "
            f"top-down view, no text, no objects. {_STYLE}"
        ),
        "size": "1024x512",
    },
    {
        "name": "paper_bg",
        "file": "paper_bg.png",
        "prompt": (
            f"seamless tileable aged parchment paper texture, cream beige, "
            f"faint horizontal ruled lines, slightly yellowed, "
            f"old letter paper, no text, no objects. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "linen_bg",
        "file": "linen_bg.png",
        "prompt": (
            f"seamless tileable natural linen fabric texture, woven cloth, "
            f"warm ecru beige, subtle thread crosshatch pattern, "
            f"top-down flat view, no text. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "paper_card",
        "file": "paper_card.png",
        "prompt": (
            f"aged parchment letter card, worn cream paper, "
            f"single round wax seal top-left corner in dark red, "
            f"faint ruled lines, torn edges, old envelope style. {_STYLE}"
        ),
        "size": "512x512",
    },
    # ── button texture (no text) ─────────────────────────────────────────────
    {
        "name": "wood_btn",
        "file": "wood_btn.png",
        "prompt": (
            f"wooden button UI element, light oak plank texture, "
            f"beveled raised edges with dark brown shadow below and right, "
            f"bright highlight top-left corner, no text, no label. {_STYLE}"
        ),
        "size": "1024x256",
    },
    {
        "name": "wood_btn_hover",
        "file": "wood_btn_hover.png",
        "prompt": (
            f"wooden button UI element HOVER STATE, lighter oak color, "
            f"deeper bevel shadow below, glowing top edge highlight, "
            f"no text, no label. {_STYLE}"
        ),
        "size": "1024x256",
    },
    # ── icons 64x64 (requested 512x512, displayed tiny with pixelated render) ──
    {
        "name": "icon_scroll",
        "file": "icon_scroll.png",
        "prompt": (
            f"single centered pixel art icon: rolled parchment scroll, "
            f"cream paper rolled at both ends, small wax seal, "
            f"warm beige colors, transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "icon_chain",
        "file": "icon_chain.png",
        "prompt": (
            f"single centered pixel art icon: chain links, "
            f"two interlocked oval rings, warm golden-brown metal, "
            f"transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "icon_quill",
        "file": "icon_quill.png",
        "prompt": (
            f"single centered pixel art icon: feather quill pen writing, "
            f"white and beige feather, dark ink tip, ink drop, "
            f"transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "icon_run",
        "file": "icon_run.png",
        "prompt": (
            f"single centered pixel art icon: play triangle arrow right, "
            f"solid warm amber brown triangle pointing right, "
            f"transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "icon_search",
        "file": "icon_search.png",
        "prompt": (
            f"single centered pixel art icon: magnifying glass, "
            f"round lens with dark brown handle at bottom-right, "
            f"warm wood brown colors, transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "icon_trash",
        "file": "icon_trash.png",
        "prompt": (
            f"single centered pixel art icon: small waste basket trash bin, "
            f"dark red-brown with lid on top, vertical lines on body, "
            f"transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "icon_save",
        "file": "icon_save.png",
        "prompt": (
            f"single centered pixel art icon: floppy disk save icon, "
            f"warm wood-brown square with metal slider, "
            f"retro 3.5 inch floppy disk, transparent or white background, "
            f"large centered object filling 80% of frame. {_STYLE}"
        ),
        "size": "512x512",
    },
    # ── decorative elements ──────────────────────────────────────────────────
    {
        "name": "divider_wood",
        "file": "divider_wood.png",
        "prompt": (
            f"horizontal wooden plank divider bar, thin strip of oak wood grain, "
            f"dark notch marks at regular intervals like a ruler, "
            f"wide panoramic format, no text. {_STYLE}"
        ),
        "size": "1024x128",
    },
    {
        "name": "corner_ornament",
        "file": "corner_ornament.png",
        "prompt": (
            f"decorative corner ornament for a wooden frame, "
            f"top-left corner piece, oak wood carved scroll design, "
            f"L-shape border intersection, warm brown tones, white background. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "wax_seal",
        "file": "wax_seal.png",
        "prompt": (
            f"pixel art wax seal stamp, round dark red burgundy wax circle, "
            f"embossed letter P in center, melted wax texture, "
            f"white or transparent background. {_STYLE}"
        ),
        "size": "512x512",
    },
    {
        "name": "empty_state",
        "file": "empty_state.png",
        "prompt": (
            f"pixel art illustration: empty wooden desk with blank parchment paper, "
            f"quill pen resting on paper, inkwell beside it, "
            f"warm candlelit ambiance, top-down view, "
            f"centered composition, white background. {_STYLE}"
        ),
        "size": "512x512",
    },
]


def generate(prompt: str, key: str) -> bytes:
    """Call RouterAI chat/completions with Gemini image model, return PNG bytes."""
    payload = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        f"{API_BASE}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())

    images = data["choices"][0]["message"].get("images", [])
    if not images:
        raise ValueError("no images in response")

    data_uri = images[0]["image_url"]["url"]
    b64 = data_uri.split(",", 1)[1]
    return base64.b64decode(b64)


def main():
    key = get_key(PROFILE)
    if not key:
        print(f"ERROR: no key for '{PROFILE}'. Run: pgate keys set {PROFILE} <key>")
        sys.exit(1)

    targets = sys.argv[1:] or [a["name"] for a in ASSETS]
    total = sum(1 for a in ASSETS if a["name"] in targets)
    done = 0

    for asset in ASSETS:
        if asset["name"] not in targets:
            continue
        out = UI_DIR / asset["file"]
        done += 1
        print(f"[{done}/{total}] {asset['name']}…", end=" ", flush=True)
        try:
            png = generate(asset["prompt"], key)
            out.write_bytes(png)
            print(f"✓  {round(len(png)/1024)}KB")
        except Exception as e:
            print(f"✗  {e}")

    print(f"\ndone. assets at {UI_DIR}")


if __name__ == "__main__":
    main()
