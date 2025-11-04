import os
import io
import time
import json
import httpx
import imageio
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text

from models import Base, engine, get_db, Slot

# ---------------------------------------------------------------------------
# FastAPI app setup
# ---------------------------------------------------------------------------
app = FastAPI(title="Slot Manager Backend")

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GIFS_DIR = os.path.join(os.path.dirname(__file__), "assets", "gifs")
os.makedirs(GIFS_DIR, exist_ok=True)
DEFAULT_GIF_NAME = "default.gif"

# ---------------------------------------------------------------------------
# Database Initialization
# ---------------------------------------------------------------------------
print("Initializing database...")

Base.metadata.create_all(bind=engine)

def _ensure_columns():
    """Safely adds missing columns without destroying data."""
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE slots ADD COLUMN discord_message_id VARCHAR"))
        except Exception:
            pass
        try:
            conn.execute(text("ALTER TABLE slots ADD COLUMN discord_channel_id VARCHAR"))
        except Exception:
            pass

_ensure_columns()
print("Database ready.")

# ---------------------------------------------------------------------------
# Helper: single DB session
# ---------------------------------------------------------------------------
def _db():
    return next(get_db())

# ---------------------------------------------------------------------------
# Helper: GIF frame iterator
# ---------------------------------------------------------------------------
def _iter_gif_frames(path: str):
    reader = imageio.get_reader(path, format="GIF")
    meta = reader.get_meta_data()
    duration = (meta.get("duration", 80) or 80) / 1000.0
    for frame in reader:
        yield Image.fromarray(frame).convert("RGBA"), duration

# ---------------------------------------------------------------------------
# Helper: text rendering (left-aligned)
# ---------------------------------------------------------------------------
def _draw_text_with_glow(base_img: Image.Image, text: str, font_family: str,
                         font_size: int, font_color: str, y_pos: int | None,
                         align="left", margin_left=24):
    upscale = 2
    large = base_img.resize((base_img.width * upscale, base_img.height * upscale),
                            Image.Resampling.LANCZOS)
    text_layer = Image.new("RGBA", large.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(text_layer)

    font_path = os.path.join("fonts", font_family or "arial.ttf")
    try:
        font = ImageFont.truetype(font_path, font_size * upscale)
    except Exception:
        font = ImageFont.load_default()

    bbox = d.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    if align == "left":
        x = margin_left * upscale
    else:
        x = (large.width - tw) // 2

    y = y_pos * upscale if y_pos is not None else (large.height - th) // 2

    # shadow / glow
    glow = Image.new("RGBA", large.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            gd.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 180))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=3))

    d.text((x, y), text, font=font, fill=font_color or "#FFFFFF")
    combined = Image.alpha_composite(large, glow)
    combined = Image.alpha_composite(combined, text_layer)
    final = combined.resize(base_img.size, Image.Resampling.LANCZOS)
    return final

# ---------------------------------------------------------------------------
# Discord utilities
# ---------------------------------------------------------------------------
def _build_payload_json(filename: str):
    return json.dumps({"attachments": [{"id": "0", "filename": filename}]})

def _discord_send_file(channel_id: str, filename: str, file_bytes: bytes, token: str):
    headers = {"Authorization": f"Bot {token}"}
    files = {
        "files[0]": (filename, file_bytes,
                     "image/gif" if filename.endswith(".gif") else "image/png"),
        "payload_json": (None, _build_payload_json(filename), "application/json"),
    }
    return httpx.post(f"https://discord.com/api/v10/channels/{channel_id}/messages",
                      headers=headers, files=files, timeout=60.0)

def _discord_edit_file(channel_id: str, message_id: str,
                       filename: str, file_bytes: bytes, token: str):
    headers = {"Authorization": f"Bot {token}"}
    files = {
        "files[0]": (filename, file_bytes,
                     "image/gif" if filename.endswith(".gif") else "image/png"),
        "payload_json": (None, _build_payload_json(filename), "application/json"),
    }
    return httpx.patch(
        f"https://discord.com/api/v10/channels/{channel_id}/messages/{message_id}",
        headers=headers, files=files, timeout=60.0
    )

# ---------------------------------------------------------------------------
# Models for API requests
# ---------------------------------------------------------------------------
class SendSlotsBody(BaseModel):
    channel_id: str
    gif_name: Optional[str] = None

# ---------------------------------------------------------------------------
# Send Slots Endpoint (persistent)
# ---------------------------------------------------------------------------
@app.post("/api/guilds/{guild_id}/send_slots")
def send_slots(guild_id: str, body: SendSlotsBody):
    """Send or update each slot as a Discord message with persistent IDs."""
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")

    channel_id = body.channel_id
    chosen_gif = body.gif_name or DEFAULT_GIF_NAME
    gif_path = os.path.join(GIFS_DIR, chosen_gif)
    if not os.path.isfile(gif_path):
        raise HTTPException(status_code=404, detail=f"GIF not found: {chosen_gif}")

    db = _db()
    slots = (db.query(Slot)
             .filter(Slot.guild_id == guild_id)
             .order_by(Slot.slot_number)
             .all())
    if not slots:
        raise HTTPException(status_code=404, detail="No slots found for this guild")

    is_gif = gif_path.lower().endswith(".gif")

    for s in slots:
        team = (s.teamname or "FreeSlot").strip()
        tag = (s.teamtag or "").strip()
        text = f"{s.slot_number}: {team} {tag}".strip()

        font_family = s.font_family or "arial.ttf"
        font_size = s.font_size or 64
        font_color = s.font_color or "#FFFFFF"
        y_pos = s.padding_top if s.padding_top is not None else None

        # Render image or GIF
        if is_gif:
            frames, durations = [], []
            for frame_img, dur in _iter_gif_frames(gif_path):
                rendered = _draw_text_with_glow(
                    frame_img, text, font_family, font_size, font_color, y_pos,
                    align="left", margin_left=24
                )
                frames.append(rendered)
                durations.append(dur)

            out_gif = io.BytesIO()
            pal_frames = [f.convert("P", palette=Image.ADAPTIVE,
                                    dither=Image.Dither.NONE) for f in frames]
            pal_frames[0].save(out_gif, format="GIF", save_all=True,
                               append_images=pal_frames[1:],
                               duration=[int(d * 1000) for d in durations],
                               loop=0, optimize=False, disposal=2)
            out_gif.seek(0)
            filename, file_bytes = f"slot_{s.slot_number}.gif", out_gif.getvalue()
        else:
            base = Image.open(gif_path).convert("RGBA")
            final = _draw_text_with_glow(
                base, text, font_family, font_size, font_color, y_pos,
                align="left", margin_left=24
            )
            out_img = io.BytesIO()
            final.save(out_img, format="PNG")
            out_img.seek(0)
            filename, file_bytes = f"slot_{s.slot_number}.png", out_img.getvalue()

        # Send or edit existing message
        if s.discord_message_id and s.discord_channel_id == channel_id:
            resp = _discord_edit_file(channel_id, s.discord_message_id,
                                      filename, file_bytes, DISCORD_BOT_TOKEN)
        else:
            resp = _discord_send_file(channel_id, filename,
                                      file_bytes, DISCORD_BOT_TOKEN)
            if resp.is_success:
                data = resp.json()
                s.discord_message_id = data.get("id")
                s.discord_channel_id = channel_id
                db.add(s)
                db.commit()

        if resp.status_code == 429:
            retry_after = resp.json().get("retry_after", 1)
            time.sleep(float(retry_after) + 0.3)
            continue

        # Pace — slightly faster (0.4s)
        time.sleep(0.4)

    return {"status": "sent"}
from fastapi.responses import RedirectResponse
import requests
import os

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_REDIRECT_URI = os.getenv(
    "DISCORD_REDIRECT_URI", "https://slotmanager-backend.onrender.com/auth/callback"
)
FRONTEND_URL = "https://slotmanager-frontend.onrender.com"  # Change this if your React app uses a different domain


@app.get("/auth/callback")
def auth_callback(code: str):
    """
    Handles Discord OAuth2 callback and redirects user back to frontend.
    """

    # Exchange the code for an access token
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI,
    }

    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    token_resp = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)

    if token_resp.status_code != 200:
        print("OAuth token exchange failed:", token_resp.text)
        return RedirectResponse(url=f"{FRONTEND_URL}/error?reason=token_exchange_failed")

    tokens = token_resp.json()
    access_token = tokens.get("access_token")

    # Fetch user info
    user_resp = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    if user_resp.status_code != 200:
        print("Failed to fetch user info:", user_resp.text)
        return RedirectResponse(url=f"{FRONTEND_URL}/error?reason=user_info_failed")

    user = user_resp.json()
    username = user.get("username")
    user_id = user.get("id")

    print(f"✅ Logged in: {username} ({user_id})")

    # Redirect user to frontend dashboard
    redirect_url = f"{FRONTEND_URL}/dashboard?user_id={user_id}&username={username}"
    return RedirectResponse(url=redirect_url)
# ---------------------------------------------------------------------------
# Root Endpoint
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "slotmanager-backend"}
