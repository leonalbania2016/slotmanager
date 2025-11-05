import os
import io
import time
import json
import httpx
import imageio
import numpy as np
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pydantic import BaseModel
from sqlalchemy import text

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from models import Base, engine, get_db, Slot

# =============================================================================
# App & CORS (must be first)
# =============================================================================
app = FastAPI(title="Slot Manager Backend")

FRONTEND_URL = os.getenv("FRONTEND_URL", "https://slotmanager-frontend.onrender.com")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://slotmanager-backend.onrender.com/auth/callback")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Files / Paths
# =============================================================================
BASE_DIR = os.path.dirname(__file__)
GIFS_DIR = os.path.join(BASE_DIR, "assets", "gifs")
os.makedirs(GIFS_DIR, exist_ok=True)
DEFAULT_GIF_NAME = "default.gif"  # drop a default into assets/gifs/default.gif

# =============================================================================
# DB bootstrap
# =============================================================================
print("Initializing database...")
Base.metadata.create_all(bind=engine)

def _ensure_columns():
    """Safely adds missing columns without destroying data."""
    with engine.begin() as conn:
        # Use IF NOT EXISTS where possible; otherwise ignore failures
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

# =============================================================================
# Helpers
# =============================================================================
def _db():
    """Return a single Session from get_db() generator."""
    return next(get_db())

def _iter_gif_frames(path: str):
    """Yield (PIL.Image, seconds_per_frame) for a GIF on disk."""
    reader = imageio.get_reader(path, format="GIF")
    meta = reader.get_meta_data()
    duration = (meta.get("duration", 80) or 80) / 1000.0
    for frame in reader:
        yield Image.fromarray(frame).convert("RGBA"), duration

def _draw_text_with_glow(
    base_img: Image.Image,
    text: str,
    font_family: str,
    font_size: int,
    font_color: str,
    y_pos: Optional[int],
    align: str = "left",
    margin_left: int = 24,
):
    """Render crisp left-aligned text with soft glow on an image."""
    upscale = 2
    large = base_img.resize(
        (base_img.width * upscale, base_img.height * upscale),
        Image.Resampling.LANCZOS,
    )

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

    # soft shadow/glow layer
    glow = Image.new("RGBA", large.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            gd.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0, 180))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=3))

    # text on its own layer
    d.text((x, y), text, font=font, fill=font_color or "#FFFFFF")

    combined = Image.alpha_composite(large, glow)
    combined = Image.alpha_composite(combined, text_layer)
    final = combined.resize(base_img.size, Image.Resampling.LANCZOS)
    return final

def _build_payload_json(filename: str):
    return json.dumps({"attachments": [{"id": "0", "filename": filename}]})

def _discord_send_file(channel_id: str, filename: str, file_bytes: bytes, token: str):
    headers = {"Authorization": f"Bot {token}"}
    files = {
        "files[0]": (filename, file_bytes,
                     "image/gif" if filename.endswith(".gif") else "image/png"),
        "payload_json": (None, _build_payload_json(filename), "application/json"),
    }
    return httpx.post(
        f"https://discord.com/api/v10/channels/{channel_id}/messages",
        headers=headers,
        files=files,
        timeout=60.0,
    )

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
        headers=headers,
        files=files,
        timeout=60.0,
    )

# =============================================================================
# Schemas
# =============================================================================
class SendSlotsBody(BaseModel):
    channel_id: str
    gif_name: Optional[str] = None

# =============================================================================
# Routes
# =============================================================================

@app.get("/")
def root():
    return {"ok": True, "service": "slotmanager-backend"}

@app.get("/api/gifs")
def list_gifs():
    """Return list of available files in assets/gifs/."""
    if not os.path.exists(GIFS_DIR):
        raise HTTPException(status_code=404, detail="GIF directory not found")
    files = [
        f for f in os.listdir(GIFS_DIR)
        if f.lower().endswith((".gif", ".png", ".jpg", ".jpeg", ".webp"))
    ]
    return {"gifs": files}

@app.get("/api/guilds/{guild_id}/channels")
def list_channels(guild_id: str):
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    url = f"https://discord.com/api/v10/guilds/{guild_id}/channels"
    r = httpx.get(url, headers=headers, timeout=15.0)

    if r.status_code == 403:
        raise HTTPException(status_code=403, detail="Bot lacks permission to view channels")
    elif r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)

    channels = [
        {"id": c["id"], "name": c["name"]}
        for c in r.json()
        if c.get("type") == 0
    ]
    return {"channels": channels}


@app.get("/api/guilds/{guild_id}/slots")
def list_slots(guild_id: str):
    """
    Return slots for a guild; on first access, initialize #2..#25.
    """
    db = _db()
    slots = (
        db.query(Slot)
        .filter(Slot.guild_id == guild_id)
        .order_by(Slot.slot_number)
        .all()
    )
    if not slots:
        # initialize #2..#25
        for n in range(2, 26):
            db.add(Slot(guild_id=guild_id, slot_number=n))
        db.commit()
        slots = (
            db.query(Slot)
            .filter(Slot.guild_id == guild_id)
            .order_by(Slot.slot_number)
            .all()
        )

    return [
        {
            "slot_number": s.slot_number,
            "teamname": s.teamname,
            "teamtag": s.teamtag,
            "emoji": s.emoji,
            "background_url": s.background_url,  # reused as "background_name" client-side if you want
            "is_gif": bool(s.is_gif),
            "font_family": s.font_family,
            "font_size": s.font_size,
            "font_color": s.font_color,
            "padding_top": s.padding_top,
            "padding_bottom": s.padding_bottom,
        }
        for s in slots
    ]

@app.post("/api/guilds/{guild_id}/send_slots")
def send_slots(guild_id: str, body: SendSlotsBody):
    """
    Send or update each slot image/GIF to a Discord channel (persistent message IDs).
    Uses a local file from assets/gifs (gif_name), defaulting to DEFAULT_GIF_NAME.
    """
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")

    channel_id = body.channel_id
    chosen_gif = body.gif_name or DEFAULT_GIF_NAME
    gif_path = os.path.join(GIFS_DIR, chosen_gif)
    if not os.path.isfile(gif_path):
        raise HTTPException(status_code=404, detail=f"GIF not found: {chosen_gif}")

    db = _db()
    slots = (
        db.query(Slot)
        .filter(Slot.guild_id == guild_id)
        .order_by(Slot.slot_number)
        .all()
    )
    if not slots:
        raise HTTPException(status_code=404, detail="No slots found for this guild")

    is_gif = gif_path.lower().endswith(".gif")

    for s in slots:
        # Render text (left aligned), remove "#" and parentheses, and "FreeSlot" for empties
        team = (s.teamname or "FreeSlot").strip()
        tag = (s.teamtag or "").strip()
        text = f"{s.slot_number}: {team} {tag}".strip()

        font_family = s.font_family or "arial.ttf"
        font_size = s.font_size or 64
        font_color = s.font_color or "#FFFFFF"
        y_pos = s.padding_top if s.padding_top is not None else None

        if is_gif:
            frames, durations = [], []
            for frame_img, dur in _iter_gif_frames(gif_path):
                rendered = _draw_text_with_glow(
                    frame_img, text, font_family, font_size, font_color, y_pos,
                    align="left", margin_left=24
                )
                frames.append(rendered)
                durations.append(dur)

            out = io.BytesIO()
            pal = [
                f.convert("P", palette=Image.ADAPTIVE, dither=Image.Dither.NONE)
                for f in frames
            ]
            pal[0].save(
                out,
                format="GIF",
                save_all=True,
                append_images=pal[1:],
                duration=[int(d * 1000) for d in durations],
                loop=0,
                optimize=False,
                disposal=2,
            )
            out.seek(0)
            filename, file_bytes = f"slot_{s.slot_number}.gif", out.getvalue()
        else:
            base = Image.open(gif_path).convert("RGBA")
            final = _draw_text_with_glow(
                base, text, font_family, font_size, font_color, y_pos,
                align="left", margin_left=24
            )
            out = io.BytesIO()
            final.save(out, format="PNG")
            out.seek(0)
            filename, file_bytes = f"slot_{s.slot_number}.png", out.getvalue()

        # Send new or edit previous message
        if s.discord_message_id and s.discord_channel_id == channel_id:
            resp = _discord_edit_file(channel_id, s.discord_message_id,
                                      filename, file_bytes, DISCORD_BOT_TOKEN)
        else:
            resp = _discord_send_file(channel_id, filename, file_bytes, DISCORD_BOT_TOKEN)
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

        # keep it fairly quick but safe
        time.sleep(0.4)

    return {"status": "sent"}

# =============================================================================
# OAuth callback – redirects to your frontend dashboard
# =============================================================================
@app.get("/auth/callback")
def auth_callback(code: str):
    if not all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, REDIRECT_URI]):
        raise HTTPException(status_code=500, detail="OAuth not configured")

    # 1) token
    token_url = "https://discord.com/api/oauth2/token"
    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    token_response = httpx.post(token_url, data=data, headers=headers, timeout=20.0)
    if token_response.status_code != 200:
        print("Token error:", token_response.text)
        raise HTTPException(status_code=400, detail="Failed to get access token")

    access_token = token_response.json().get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token")

    # 2) user
    user_data = httpx.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    ).json()

    user_id = user_data.get("id")
    username = user_data.get("username")

    # 3) guilds
    guilds_resp = httpx.get(
        "https://discord.com/api/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    )
    if guilds_resp.status_code != 200:
        print("Guilds error:", guilds_resp.text)
        raise HTTPException(status_code=400, detail="Failed to fetch guilds")

    guilds = guilds_resp.json()
    if not guilds:
        raise HTTPException(status_code=400, detail="No accessible guilds found")

    # Pick first guild (you can filter to ADMIN (0x8) if you want)
    guild_id = guilds[0]["id"]

    # 4) redirect to frontend
    redirect_url = f"{FRONTEND_URL}/dashboard/{guild_id}?user_id={user_id}&username={username}"
    return RedirectResponse(url=redirect_url)
