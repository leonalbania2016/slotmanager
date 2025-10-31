import os
import io
from PIL import Image, ImageDraw, ImageFont, ImageSequence
import requests
from typing import Tuple

def load_font(font_family: str, font_size: int):
    try:
        return ImageFont.truetype(font_family, font_size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except Exception:
            return ImageFont.load_default()

def draw_slot_on_image(pil_img: Image.Image, meta: dict) -> Image.Image:
    """
    Draw a one-line slot layout on pil_img using meta:
    - slot_number, teamname, teamtag, emoji
    - font_family, font_size, font_color
    - padding_top, padding_bottom (pixels)
    The text baseline is vertically positioned between padding_top and (height - padding_bottom),
    centered within that remaining band.
    """
    draw = ImageDraw.Draw(pil_img)
    w, h = pil_img.size

    font_size = int(meta.get("font_size", 48))
    font = load_font(meta.get("font_family", "DejaVuSans.ttf"), font_size)
    color = meta.get("font_color", "#FFFFFF")
    padding_top = int(meta.get("padding_top", 0))
    padding_bottom = int(meta.get("padding_bottom", 0))

    # compute usable vertical band
    usable_top = padding_top
    usable_bottom = max(0, h - padding_bottom)
    usable_height = max(1, usable_bottom - usable_top)

    # vertical center for text within usable band
    # measure text height roughly and center it
    teamname = meta.get("teamname", "") or ""
    teamtag = meta.get("teamtag", "") or ""
    if teamname and teamtag:
        main_text = f"{teamname} - {teamtag}"
    else:
        main_text = teamname or teamtag

    slot_text = str(meta.get("slot_number", ""))
    emoji_text = meta.get("emoji", "")

    # For layout, we'll measure texts
    slot_w, slot_h = draw.textsize(slot_text, font=font)
    main_w, main_h = draw.textsize(main_text, font=font)
    emoji_w, emoji_h = draw.textsize(emoji_text, font=font)

    total_text_width = slot_w + 20 + main_w + 20 + emoji_w  # small gaps
    # positions
    padding_x = 20
    left_x = padding_x
    # center block start
    center_start = (w - main_w) / 2
    # emoji right
    emoji_x = w - emoji_w - padding_x

    # vertical y
    y_center = usable_top + (usable_height - main_h) / 2

    # draw slot number on the left (align left)
    draw.text((left_x, y_center), slot_text, font=font, fill=color)

    # draw main text centered horizontally
    draw.text((center_start, y_center), main_text, font=font, fill=color)

    # draw emoji at right
    draw.text((emoji_x, y_center), emoji_text, font=font, fill=color)

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
                f2 = frame.copy()
                f2 = draw_slot_on_image(f2, meta)
                frames.append(f2)
            out_buf = io.BytesIO()
            frames[0].save(out_buf, format="GIF", save_all=True, append_images=frames[1:], loop=0, duration=duration)
            out_buf.seek(0)
            return out_buf.read(), "image/gif"
        else:
            im = Image.open(buf).convert("RGBA")
            im = draw_slot_on_image(im, meta)
            out_buf = io.BytesIO()
            im.save(out_buf, format="PNG")
            out_buf.seek(0)
            return out_buf.read(), "image/png"
