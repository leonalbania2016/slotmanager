import os
import io
import time
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List

import httpx
import numpy as np
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body, Depends
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# --- Your DB bits -------------------------------------------------------------
# Assumes you already have models.py with Slot + get_db
# If your get_db import path is different, adjust this import.
from models import Slot, get_db

# --- Env & Config -------------------------------------------------------------
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://slotmanager-frontend.onrender.com")

# Where your local GIFs live
GIFS_DIR = os.path.join(os.path.dirname(__file__), "assets", "gifs")
DEFAULT_GIF_NAME = "default.gif"  # make sure this exists in GIFS_DIR

# --- App init ----------------------------------------------------------------
app = FastAPI(title="Slot Manager API")

# CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static gifs (so frontend can preview if desired)
if not os.path.isdir(GIFS_DIR):
    os.makedirs(GIFS_DIR, exist_ok=True)

# Optionally mount a static route (preview URLs like /static/gifs/filename.gif)
app.mount("/static/gifs", StaticFiles(directory=GIFS_DIR), name="gifs")

# --- Simple in-memory session store ------------------------------------------
SESSION_STORE = {}  # session_id -> { "guilds": [...], "exp": datetime }

# --- Helpers -----------------------------------------------------------------
def _clean_expired_sessions():
    now = datetime.utcnow()
    expired = [k for k, v in SESSION_STORE.items() if v.get("exp") and v["exp"] < now]
    for k in expired:
        SESSION_STORE.pop(k, None)

def _get_font(ttf_name: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    """
    Try to load a TrueType font from ./fonts or system; fall back to default bitmap.
    """
    fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
    ttf = ttf_name or "arial.ttf"
    # Try local fonts dir first
    try_paths = [
        os.path.join(fonts_dir, ttf),
        ttf,  # allow absolute or system path if someone puts a full path in DB
    ]
    for p in try_paths:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    # Fallback (bitmap)
    return ImageFont.load_default()

def _draw_text_with_glow(
    base_img: Image.Image,
    text: str,
    font_family: Optional[str],
    font_size: int,
    font_color: str,
    y: Optional[int]
) -> Image.Image:
    """
    Render crisp text by upscaling, drawing, then downscaling (super-sampling).
    Adds a soft glow/outline for readability on busy backgrounds.
    """
    upscale = 2  # 2x supersampling keeps size good while sharpening text
    W, H = base_img.size
    large = base_img.resize((W * upscale, H * upscale), Image.Resampling.LANCZOS)

    text_layer = Image.new("RGBA", large.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_layer)

    font = _get_font(font_family, (font_size or 64) * upscale)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    x = 80  # left padding (adjust as you like)
    y_px = y * upscale if y is not None else (large.height - th) // 2


    # soft shadow/glow
    shadow = Image.new("RGBA", large.size, (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    sdraw.text((x, y_px), text, font=font, fill=(0, 0, 0, 255))
    for radius in (3, 2, 1):
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=radius))
    text_layer = Image.alpha_composite(text_layer, shadow)

    # foreground text
    draw = ImageDraw.Draw(text_layer)
    # support hex like "#FFFFFF" or names like "white"
    try:
        fill_color = font_color if font_color else "#FFFFFF"
    except Exception:
        fill_color = "#FFFFFF"
    draw.text((x, y_px), text, font=font, fill=fill_color)

    combined = Image.alpha_composite(large.convert("RGBA"), text_layer)
    final = combined.resize((W, H), Image.Resampling.LANCZOS)
    return final

def _iter_gif_frames(path: str):
    """
    Generator yielding (frame_image: PIL.Image, duration_seconds: float).
    Uses imageio reader so we honor frame durations.
    """
    import imageio.v2 as imageio
    reader = imageio.get_reader(path, format="GIF")
    # Default per-frame duration (imageio can give a single duration or per-frame list)
    meta = reader.get_meta_data()
    default_ms = meta.get("duration", 80)
    for i, frame in enumerate(reader):
        # Some GIFs have per-frame durations in 'meta["duration"]' (single) or something else.
        # imageio v2 doesn’t always expose per-frame durations; we’ll use default if none.
        dur = default_ms / 1000.0
        yield Image.fromarray(frame).convert("RGBA"), dur
    reader.close()

# --- OAuth (login → callback) ------------------------------------------------
@app.get("/auth/login")
def auth_login():
    if not (DISCORD_CLIENT_ID and OAUTH_REDIRECT_URI):
        raise HTTPException(status_code=500, detail="OAuth not configured")
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
        "prompt": "consent",
    }
    q = "&".join([f"{k}={httpx.QueryParams({k: v})[k]}" for k, v in params.items()])
    return RedirectResponse(f"https://discord.com/api/oauth2/authorize?{q}")

@app.get("/auth/callback")
async def auth_callback(code: str):
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and OAUTH_REDIRECT_URI):
        raise HTTPException(status_code=500, detail="OAuth not configured")

    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        r = await client.post("https://discord.com/api/oauth2/token", data=token_data, headers=headers)
        r.raise_for_status()
        access_token = r.json()["access_token"]

        # Get the user's guilds
        r2 = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r2.raise_for_status()
        all_guilds = r2.json()

    # Filter only guilds where user has ADMINISTRATOR permission (0x8)
    guilds = [g for g in all_guilds if (g.get("permissions", 0) & 0x8) == 0x8]

    # Create short-lived session
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        "guilds": guilds,
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }

    return RedirectResponse(f"{FRONTEND_URL}/?session={session_id}")

@app.get("/api/decode")
def decode_session(session: str):
    _clean_expired_sessions()
    data = SESSION_STORE.get(session)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    # Return only what frontend needs
    guilds = [
        {"id": g["id"], "name": g["name"], "icon": g.get("icon")}
        for g in data["guilds"]
    ]
    return {"guilds": guilds}

# --- GIFs listing for frontend -----------------------------------------------
@app.get("/api/gifs")
def list_gifs():
    """
    Returns available gif filenames in backend/assets/gifs
    """
    try:
        files = sorted(
            [f for f in os.listdir(GIFS_DIR) if f.lower().endswith((".gif", ".png", ".jpg", ".jpeg", ".webp"))]
        )
        return {"gifs": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Channels (bot token) -----------------------------------------------------
@app.get("/api/guilds/{guild_id}/channels")
def get_guild_channels(guild_id: str):
    """
    Fetch all text channels for a guild using bot token.
    """
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    r = httpx.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers)
    r.raise_for_status()
    channels = r.json()
    text_channels = [{"id": ch["id"], "name": ch["name"]} for ch in channels if ch.get("type") == 0]
    return text_channels  # plain array is fine (your frontend supports both)

# --- Slots --------------------------------------------------------------------
@app.get("/api/guilds/{guild_id}/slots")
def list_slots(guild_id: str):
    """
    Returns slots #2..#25 (initializes on first access).
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        slots = (
            db.query(Slot)
            .filter(Slot.guild_id == guild_id)
            .order_by(Slot.slot_number)
            .all()
        )
        if not slots:
            for s in range(2, 26):
                db.add(Slot(guild_id=guild_id, slot_number=s))
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
                "background_url": s.background_url,  # repurposed for gif name
                "is_gif": bool(s.is_gif),
                "font_family": s.font_family,
                "font_size": s.font_size,
                "font_color": s.font_color,
                "padding_top": s.padding_top,
                "padding_bottom": s.padding_bottom,
            }
            for s in slots
        ]
    finally:
        db_gen.close()


# --- Slot Update --------------------------------------------------------------
class SlotUpdate(BaseModel):
    teamname: Optional[str] = None
    teamtag: Optional[str] = None
    emoji: Optional[str] = None
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    padding_top: Optional[int] = None
    padding_bottom: Optional[int] = None
    background_name: Optional[str] = None  # <- store a local gif/image filename


@app.post("/api/guilds/{guild_id}/slots/{slot_number}")
def update_slot(guild_id: str, slot_number: int, payload: SlotUpdate):
    """
    Update a single slot’s properties.
    """
    db_gen = get_db()
    db = next(db_gen)
    try:
        s = (
            db.query(Slot)
            .filter(Slot.guild_id == guild_id, Slot.slot_number == slot_number)
            .first()
        )
        if not s:
            raise HTTPException(status_code=404, detail="Slot not found")

        # Update fields if provided
        for field, value in payload.model_dump(exclude_unset=True).items():
            if field == "background_name":
                # store gif/image filename in background_url column
                setattr(s, "background_url", value)
            else:
                setattr(s, field, value)

        db.commit()
        return {"ok": True}
    finally:
        db_gen.close()


# --- Send Slots (high quality, local GIFs) ------------------------------------
class SendSlotsBody(BaseModel):
    channel_id: str
    gif_name: Optional[str] = None  # optional: choose a GIF from /api/gifs (fallback to default.gif)

@app.post("/api/guilds/{guild_id}/send_slots")
def send_slots(guild_id: str, body: SendSlotsBody):
    """
    Sends each slot as an image (or animated GIF) to a Discord channel.
    Uses local files from backend/assets/gifs/.
    """
    import io, os, time
    import httpx
    from PIL import Image

    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")

    channel_id = body.channel_id
    chosen_gif = body.gif_name or DEFAULT_GIF_NAME
    gif_path = os.path.join(GIFS_DIR, chosen_gif)

    # ✅ Validate the background file exists locally
    if not os.path.isfile(gif_path):
        fallback = os.path.join(GIFS_DIR, DEFAULT_GIF_NAME)
        if os.path.isfile(fallback):
            gif_path = fallback
        else:
            raise HTTPException(status_code=404, detail=f"Background file not found: {chosen_gif}")

    # ✅ FIX: Properly handle get_db() (no 'with' statement)
    db_gen = get_db()
    db = next(db_gen)
    try:
        slots = (
            db.query(Slot)
            .filter(Slot.guild_id == guild_id)
            .order_by(Slot.slot_number)
            .all()
        )
    finally:
        db_gen.close()

    if not slots:
        raise HTTPException(status_code=404, detail="No slots found for this guild")

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    is_gif = gif_path.lower().endswith(".gif")

    # 🔁 Generate and send each slot image/GIF
    for s in slots:
        teamname = s.teamname or "FreeSlot"
        tag = f" {s.teamtag}" if s.teamtag else ""
        text = f"{s.slot_number} - {teamname} - {tag}"

        font_family = s.font_family or "arial.ttf"
        font_size = s.font_size or 64
        font_color = s.font_color or "#FFFFFF"
        y_pos = s.padding_top if s.padding_top is not None else None

        if is_gif:
            # Build new animated gif with crisp text on each frame
            frames = []
            durations = []

            for frame_img, dur in _iter_gif_frames(gif_path):
                rendered = _draw_text_with_glow(
                    frame_img, text, font_family, font_size, font_color, y_pos
                )
                frames.append(rendered)
                durations.append(dur)

            # Save in-memory GIF
            out_gif = io.BytesIO()
            pal_frames = [
                f.convert("P", palette=Image.ADAPTIVE, dither=Image.Dither.NONE)
                for f in frames
            ]
            pal_frames[0].save(
                out_gif,
                format="GIF",
                save_all=True,
                append_images=pal_frames[1:],
                duration=[int(d * 1000) for d in durations],
                loop=0,
                optimize=False,
                disposal=2,
            )
            out_gif.seek(0)
            files = {"file": ("slot.gif", out_gif, "image/gif")}

        else:
            # Static image – draw once
            base = Image.open(gif_path).convert("RGBA")
            final = _draw_text_with_glow(
                base, text, font_family, font_size, font_color, y_pos
            )
            out_img = io.BytesIO()
            final.save(out_img, format="PNG")
            out_img.seek(0)
            files = {"file": ("slot.png", out_img, "image/png")}

        # 🚀 Upload to Discord
        upload = httpx.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers=headers,
            files=files,
            timeout=60.0,
        )

        if upload.status_code == 429:
            # Respect rate limit and retry once
            retry_after = upload.json().get("retry_after", 2)
            print(f"Rate-limited by Discord. Retrying in {retry_after}s...")
            time.sleep(float(retry_after) + 0.5)
            upload = httpx.post(
                f"https://discord.com/api/v10/channels/{channel_id}/messages",
                headers=headers,
                files=files,
                timeout=60.0,
            )

        upload.raise_for_status()
        time.sleep(0.3)  # Discord global rate limit: 5 messages/sec

    return {"status": "sent"}

# --- Root (optional) ----------------------------------------------------------
@app.get("/")
def root():
    return {"ok": True, "service": "slotmanager-backend"}
# --- Database Initialization ---
from models import Base, engine

print("Initializing database...")
Base.metadata.create_all(bind=engine)
print("Database ready.")
