"""Platzhalter-Icons für FPX Timetracker generieren.
Erzeugt assets/app.ico und assets/tray.ico mit dem Accent-Blau und einem ⏱-Symbol.
Später durch richtige Icons ersetzen – Dateinamen beibehalten.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

ACCENT = (71, 156, 197, 255)   # #479CC5
TEXT   = (240, 237, 232, 255)  # #F0EDE8

USER_ICON_NAMES = ["fpx_icon", "icon", "logo", "app_icon"]
USER_ICON_EXTS  = [".ico", ".png", ".jpg", ".jpeg"]


def find_user_icon() -> Path | None:
    """Sucht im Repo-Root nach einem vom User abgelegten Icon (fpx_icon.png etc.)."""
    for name in USER_ICON_NAMES:
        for ext in USER_ICON_EXTS:
            p = ROOT / f"{name}{ext}"
            if p.exists():
                return p
    return None


def _render_from_user(src: Path, size: int) -> Image.Image:
    img = Image.open(src).convert("RGBA")
    img.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - img.width) // 2
    y = (size - img.height) // 2
    canvas.paste(img, (x, y), img)
    return canvas


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("seguisym.ttf", "segoeui.ttf", "arial.ttf",
                 "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _render(size: int, glyph: str = "F") -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 16)
    d.ellipse([pad, pad, size - pad, size - pad], fill=ACCENT)
    font = _find_font(int(size * 0.58))
    bbox = d.textbbox((0, 0), glyph, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    d.text((x, y), glyph, fill=TEXT, font=font)
    return img


def make_ico(path: Path, sizes: list[int], glyph: str = "F"):
    sorted_sizes = sorted(sizes)
    user = find_user_icon()
    if user:
        images = [_render_from_user(user, sz) for sz in sorted_sizes]
        src_note = f"user-icon: {user.name}"
    else:
        base = _render(max(sizes), glyph)
        images = [base.resize((sz, sz), Image.LANCZOS) for sz in sorted_sizes]
        src_note = "placeholder"
    images[0].save(path, format="ICO",
                   sizes=[(sz, sz) for sz in sorted_sizes],
                   append_images=images[1:])
    print(f"wrote {path}  ({', '.join(str(sz) for sz in sorted_sizes)})  [{src_note}]")


if __name__ == "__main__":
    u = find_user_icon()
    if u:
        print(f"found user icon: {u}")
    else:
        print("no user icon found – using placeholder (put fpx_icon.png/ico in repo root to override)")
    make_ico(ASSETS / "app.ico",  [16, 32, 48, 64, 128, 256], glyph="F")
    make_ico(ASSETS / "tray.ico", [16, 24, 32, 48],          glyph="F")
