import os
import io
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import requests
from typing import Tuple

# Cache emoji bitmaps for speed
_EMOJI_CACHE = {}

def load_font(font_family: str, font_size: int):
    try:
        return ImageFont.truetype(font_family, font_size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except Exception:
            return ImageFont.load_default()

def fetch_emoji_bitmap(emoji_value: str, target_height: int = 64) -> Image.Image | None:
    """
    Converts a Discord emoji code (<:name:id> or <a:name:id>) or CDN URL
    into a transparent PIL image.
    """
    if not emoji_value:
        return None

    # Handle Discord emoji CDN URL directly
    if emoji_value.startswith("http"):
        url = emoji_value
    elif emoji_value.startswith("<") and emoji_value.endswith(">"):
        parts = emoji_value.strip("<>").split(":")
        if len(parts) >= 2:
            animated = parts[0] == "a"
            emoji_id = parts[-1]
            ext = "gif" if animated else "png"
            url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{ext}?quality=lossless"
        else:
            return None
    else:
        # Standard Unicode emoji — draw as text
        return None

    if url in _EMOJI_CACHE:
        return _EMOJI_CACHE[url]

    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        ratio = target_height / img.height
        img = img.resize((int(img.width * ratio), target_height), Image.Resampling.LANCZOS)
        _EMOJI_CACHE[url] = img
        return img
    except Exception as e:
        print("⚠️ Failed to fetch emoji:", e)
        return None

def draw_slot_on_image(pil_img: Image.Image, meta: dict) -> Image.Image:
    draw = ImageDraw.Draw(pil_img)
    w, h = pil_img.size

    font_size = int(meta.get("font_size", 48))
    font = load_font(meta.get("font_family", "DejaVuSans.ttf"), font_size)
    color = meta.get("font_color", "#FFFFFF")
    padding_top = int(meta.get("padding_top", 0))
    padding_bottom = int(meta.get("padding_bottom", 0))

    usable_top = padding_top
    usable_bottom = max(0, h - padding_bottom)
    usable_height = max(1, usable_bottom - usable_top)

    teamname = meta.get("teamname", "") or ""
    teamtag = meta.get("teamtag", "") or ""
    main_text = f"{teamname} - {teamtag}" if (teamname and teamtag) else teamname or teamtag

    slot_text = str(meta.get("slot_number", ""))
    emoji_value = meta.get("emoji", "")

    # Measure text
    slot_w, slot_h = draw.textsize(slot_text, font=font)
    main_w, main_h = draw.textsize(main_text, font=font)
    y_center = usable_top + (usable_height - main_h) / 2

    padding_x = 20
    left_x = padding_x
    center_x = (w - main_w) / 2

    # Draw left (slot number)
    draw.text((left_x, y_center), slot_text, font=font, fill=color)

    # Draw center (team name/tag)
    draw.text((center_x, y_center), main_text, font=font, fill=color)

    # Draw right (emoji)
    emoji_x = w - padding_x
    emoji_img = fetch_emoji_bitmap(emoji_value, target_height=font_size)

    if emoji_img:
        emoji_x -= emoji_img.width
        emoji_y = usable_top + (usable_height - emoji_img.height) / 2
        pil_img.paste(emoji_img, (int(emoji_x), int(emoji_y)), emoji_img)
    elif emoji_value:
        # fallback: draw as Unicode
        emoji_w, emoji_h = draw.textsize(emoji_value, font=font)
        emoji_x -= emoji_w
        emoji_y = y_center
        draw.text((emoji_x, emoji_y), emoji_value, font=font, fill=color)

    return pil_img

def fetch_image_bytes(url: str) -> Tuple[bytes, str]:
    r = requests.get(url, stream=True, timeout=20)
    r.raise_for_status()
    content_type = r.headers.get("content-type", "application/octet-stream")
    return r.content, content_type

def generate_from_url_bytes(bg_bytes: bytes, content_type: str, meta: dict) -> Tuple[bytes, str]:
    with io.BytesIO(bg_bytes) as buf:
        buf.seek(0)
        if "gif" in content_type.lower():
            im = Image.open(buf)
            frames = []
            duration = im.info.get("duration", 100)
            for frame in ImageSequence.Iterator(im):
                frame = frame.convert("RGBA")
                composed = draw_slot_on_image(frame.copy(), meta)
                frames.append(composed)
            out_buf = io.BytesIO()
            frames[0].save(out_buf, format="GIF", save_all=True, append_images=frames[1:], loop=0, duration=duration)
            out_buf.seek(0)
            return out_buf.read(), "image/gif"
        else:
            im = Image.open(buf).convert("RGBA")
            composed = draw_slot_on_image(im, meta)
            out_buf = io.BytesIO()
            composed.save(out_buf, format="PNG")
            out_buf.seek(0)
            return out_buf.read(), "image/png"
