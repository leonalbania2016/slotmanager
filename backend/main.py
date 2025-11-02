import os
import io
import secrets
import httpx
import numpy as np
import imageio
from PIL import Image, ImageDraw, ImageFont
from fastapi import Body
from datetime import datetime, timedelta
from contextlib import contextmanager
from urllib.parse import urlencode

import jwt
import httpx
import cloudinary
import cloudinary.uploader
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from models import SessionLocal, Base, engine, Slot, GuildConfig
from utils import fetch_image_bytes, generate_from_url_bytes, draw_slot_on_image

# -----------------------------
# DB init
# -----------------------------
Base.metadata.create_all(bind=engine)

@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------
# Config
# -----------------------------
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
# Default background for slot banners (if none set per slot)
DEFAULT_BACKGROUND_URL = "https://cdn.discordapp.com/attachments/1427732546036174951/1432503283498487845/EVERYTHIN3-ezgif.com-video-to-gif-converter.gif?ex=69088a65&is=690738e5&hm=cee311e01ffe66fcd0a7c4023140805f1541f4f3d14e5ef4f0b621141c13c287&"  # ← replace with your default image link
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", f"{BACKEND_URL}/auth/callback")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://slotmanager-frontend.onrender.com")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# -----------------------------
# Cloudinary
# -----------------------------
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")
if CLOUDINARY_URL:
    os.environ["CLOUDINARY_URL"] = CLOUDINARY_URL  # ensure SDK sees it
    cloudinary.config(secure=True)
else:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True,
    )

# -----------------------------
# FastAPI
# -----------------------------
app = FastAPI()

# ✅ CORS settings
from fastapi.middleware.cors import CORSMiddleware

origins = [
    "https://slotmanager-frontend.onrender.com",  # your deployed frontend
    "http://localhost:5173",  # for local development
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# Schemas
# -----------------------------
class SlotUpdate(BaseModel):
    slot_number: int
    teamname: str = ""
    teamtag: str = ""
    emoji: str = ""
    font_family: str = "DejaVuSans.ttf"
    font_size: int = 48
    font_color: str = "#FFFFFF"
    is_gif: int = 0
    padding_top: int = 0
    padding_bottom: int = 0

# -----------------------------
# Auth
# -----------------------------
@app.get("/auth/login")
def auth_login():
    if not DISCORD_CLIENT_ID or not OAUTH_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="OAuth not configured")
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds",
    }
    return RedirectResponse("https://discord.com/api/oauth2/authorize?" + urlencode(params))

import uuid

# Temporary in-memory session store (simple; use Redis or DB for persistence)
SESSION_STORE = {}

@app.get("/auth/callback")
async def auth_callback(code: str):
    if not (DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET and OAUTH_REDIRECT_URI):
        raise HTTPException(status_code=500, detail="OAuth not configured")

    async with httpx.AsyncClient() as client:
        # Step 1: Exchange code for access token
        token_data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        token_res = await client.post(
            "https://discord.com/api/oauth2/token", data=token_data, headers=headers
        )
        token_res.raise_for_status()
        access_token = token_res.json()["access_token"]

        # Step 2: Get user's guilds
        r2 = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        r2.raise_for_status()
        all_guilds = r2.json()

        # ✅ Step 3: Filter only guilds where user has ADMIN permission
        guilds = []
        for g in all_guilds:
            try:
                perms = int(g.get("permissions", 0))
                if (perms & 0x8) == 0x8:  # 0x8 = ADMIN
                    guilds.append(g)
            except (ValueError, TypeError):
                continue

    # Step 4: Store filtered guilds in session
    session_id = str(uuid.uuid4())
    SESSION_STORE[session_id] = {
        "guilds": guilds,
        "exp": datetime.utcnow() + timedelta(minutes=5)
    }

    frontend_url = os.getenv("FRONTEND_URL", "https://slotmanager-frontend.onrender.com")
    return RedirectResponse(f"{frontend_url}/?session={session_id}")


@app.get("/api/decode")
def decode_session(session: str):
    data = SESSION_STORE.get(session)
    if not data:
        raise HTTPException(status_code=404, detail="Session not found")
    if data["exp"] < datetime.utcnow():
        raise HTTPException(status_code=401, detail="Session expired")
    return {"guilds": data["guilds"]}

# -----------------------------
# Slots
# -----------------------------
@app.get("/api/guilds/{guild_id}/slots")
def list_slots(guild_id: str):
    with get_db() as db:
        slots = (
            db.query(Slot)
            .filter(Slot.guild_id == guild_id)
            .order_by(Slot.slot_number)
            .all()
        )
        if not slots:
            # initialize slots 2..25 on first access
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
                "background_url": s.background_url,
                "is_gif": bool(s.is_gif),
                "font_family": s.font_family,
                "font_size": s.font_size,
                "font_color": s.font_color,
                "padding_top": s.padding_top,
                "padding_bottom": s.padding_bottom,
            }
            for s in slots
        ]
from fastapi import Body, HTTPException
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import httpx

import imageio
from PIL import Image, ImageDraw, ImageFont
import io

@app.post("/api/guilds/{guild_id}/send_slots")
def send_slots(guild_id: str, channel_id: str = Body(...)):
    """
    Sends the slot list as images to a Discord channel.
    Keeps GIF animation if the background is animated.
    """
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}

    with get_db() as db:
        slots = db.query(Slot).filter(Slot.guild_id == guild_id).order_by(Slot.slot_number).all()

    if not slots:
        raise HTTPException(status_code=404, detail="No slots found for this guild")

    # Default background (still or animated)
    DEFAULT_BACKGROUND_URL = "https://cdn.discordapp.com/attachments/xxxx/slot_bg.gif"

    for s in slots:
        bg_url = s.background_url or DEFAULT_BACKGROUND_URL
        teamname = s.teamname or "Unassigned"
        tag = f" ({s.teamtag})" if s.teamtag else ""
        text = f"#{s.slot_number}: {teamname}{tag}"

        # Download background
        r = httpx.get(bg_url)
        r.raise_for_status()
        bg_bytes = io.BytesIO(r.content)

        # 🧠 Detect GIFs
        if bg_url.lower().endswith(".gif"):
            frames = imageio.mimread(bg_bytes, memtest=False)
            new_frames = []
            for frame in frames:
                img = Image.fromarray(frame)
                draw = ImageDraw.Draw(img)
                font_path = os.path.join("fonts", s.font_family or "arial.ttf")
                font = ImageFont.truetype(font_path, s.font_size or 64)
                bbox = draw.textbbox((0, 0), text, font=font)
                text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                x = (img.width - text_w) / 2
                y = s.padding_top or 100
                draw.text((x, y), text, font=font, fill=s.font_color or "#FFFFFF")
                new_frames.append(np.array(img))

            # Save as animated GIF again
            out_gif = io.BytesIO()
            imageio.mimsave(out_gif, new_frames, format="GIF", loop=0, duration=0.08)
            out_gif.seek(0)
            files = {"file": ("slot.gif", out_gif, "image/gif")}
        else:
            img = Image.open(bg_bytes).convert("RGBA")
            draw = ImageDraw.Draw(img)
            font_path = os.path.join("fonts", s.font_family or "arial.ttf")
            font = ImageFont.truetype(font_path, s.font_size or 64)
            bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            x = (img.width - text_w) / 2
            y = s.padding_top or 100
            draw.text((x, y), text, font=font, fill=s.font_color or "#FFFFFF")

            out_img = io.BytesIO()
            img.save(out_img, format="PNG")
            out_img.seek(0)
            files = {"file": ("slot.png", out_img, "image/png")}

        # Upload to Discord
        upload = httpx.post(
            f"https://discord.com/api/v10/channels/{channel_id}/messages",
            headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
            files=files
        )
        upload.raise_for_status()

    return {"status": "sent"}

from fastapi import Body

@app.post("/api/guilds/{guild_id}/slots/{slot_number}")
def update_slot(guild_id: str, slot_number: int, data: dict = Body(...)):
    with get_db() as db:
        slot = db.query(Slot).filter(
            Slot.guild_id == guild_id, Slot.slot_number == slot_number
        ).first()

        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")

        # Update fields
        slot.teamname = data.get("teamname")
        slot.teamtag = data.get("teamtag")
        slot.emoji = data.get("emoji")
        slot.background_url = data.get("background_url")

        # Optional: if you want to save which channel slots go to
        if "channel_id" in data:
            slot.channel_id = data.get("channel_id")

        db.commit()

    return {"status": "ok", "slot_number": slot_number}
@app.post("/api/guilds/{guild_id}/send_slots")
def send_slots(guild_id: str, data: dict = Body(...)):
    channel_id = data.get("channel_id")
    if not channel_id:
        raise HTTPException(status_code=400, detail="channel_id missing")

    with get_db() as db:
        slots = db.query(Slot).filter(Slot.guild_id == guild_id).order_by(Slot.slot_number).all()

    content = "\n".join(
        f"#{s.slot_number} {s.teamname or 'Unassigned'} ({s.teamtag or ''})"
        for s in slots
    )

    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    payload = {"content": f"**Slot List for {guild_id}:**\n{content}"}

    httpx.post(f"https://discord.com/api/v10/channels/{channel_id}/messages", json=payload, headers=headers)

    return {"status": "ok"}

@app.post("/api/guilds/{guild_id}/slots/{slot_number}/upload")
async def upload_background(guild_id: str, slot_number: int, file: UploadFile = File(...)):
    contents = await file.read()
    public_id = f"slot_{guild_id}_{slot_number}_{int(__import__('time').time())}"

    # upload_large handles big GIFs
    res = cloudinary.uploader.upload_large(
        io.BytesIO(contents),
        public_id=public_id,
        resource_type="auto",
        overwrite=True,
    )
    url = res.get("secure_url") or res.get("url")
    is_gif = 1 if (res.get("format", "") or "").lower() == "gif" else 0

    with get_db() as db:
        slot = db.query(Slot).filter(Slot.guild_id == guild_id, Slot.slot_number == slot_number).first()
        if not slot:
            slot = Slot(guild_id=guild_id, slot_number=slot_number)
            db.add(slot)
        slot.background_url = url
        slot.is_gif = is_gif
        db.commit()

    return {"url": url, "is_gif": bool(is_gif)}

@app.post("/api/guilds/{guild_id}/slots/{slot_number}")
def update_slot(guild_id: str, slot_number: int, payload: SlotUpdate):
    with get_db() as db:
        slot = db.query(Slot).filter(Slot.guild_id == guild_id, Slot.slot_number == slot_number).first()
        if not slot:
            slot = Slot(guild_id=guild_id, slot_number=slot_number)
            db.add(slot)

        slot.teamname = payload.teamname
        slot.teamtag = payload.teamtag
        slot.emoji = payload.emoji
        slot.font_family = payload.font_family
        slot.font_size = payload.font_size
        slot.font_color = payload.font_color
        slot.is_gif = payload.is_gif
        slot.padding_top = payload.padding_top
        slot.padding_bottom = payload.padding_bottom

        db.commit()

    return {"ok": True}

# -----------------------------
# Guild channel config
# -----------------------------
@app.post("/api/guilds/{guild_id}/channel")
def set_channel(guild_id: str, channel_id: str = Form(...)):
    with get_db() as db:
        cfg = db.query(GuildConfig).filter(GuildConfig.guild_id == guild_id).first()
        if not cfg:
            cfg = GuildConfig(guild_id=guild_id, channel_id=channel_id)
            db.add(cfg)
        else:
            cfg.channel_id = channel_id
        db.commit()
    return {"ok": True}

@app.get("/api/guilds/{guild_id}/channel")
def get_channel(guild_id: str):
    with get_db() as db:
        cfg = db.query(GuildConfig).filter(GuildConfig.guild_id == guild_id).first()
        return {"channel_id": cfg.channel_id if cfg else ""}

@app.get("/api/guilds/{guild_id}/channels")
def get_guild_channels(guild_id: str):
    """Fetches all text channels for a guild using the bot token."""
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    r = httpx.get(f"https://discord.com/api/v10/guilds/{guild_id}/channels", headers=headers)
    r.raise_for_status()
    channels = r.json()

    # Only return text channels (type == 0)
    text_channels = [
        {"id": ch["id"], "name": ch["name"]}
        for ch in channels
        if ch.get("type") == 0
    ]
    return text_channels

# -----------------------------
# Image generation
# -----------------------------
@app.get("/api/generate/{guild_id}/{slot_number}")
def api_generate(guild_id: str, slot_number: int):
    with get_db() as db:
        slot = db.query(Slot).filter(Slot.guild_id == guild_id, Slot.slot_number == slot_number).first()
        if not slot:
            raise HTTPException(status_code=404, detail="Slot not found")

        meta = {
            "slot_number": slot.slot_number,
            "teamname": slot.teamname,
            "teamtag": slot.teamtag,
            "emoji": slot.emoji,
            "font_family": slot.font_family,
            "font_size": slot.font_size,
            "font_color": slot.font_color,
            "padding_top": slot.padding_top,
            "padding_bottom": slot.padding_bottom,
        }

        if not slot.background_url:
            from PIL import Image
            im = Image.new("RGBA", (1280, 120), (10, 22, 50, 255))
            im = draw_slot_on_image(im, meta)
            out = io.BytesIO()
            im.save(out, format="PNG")
            out.seek(0)
            return StreamingResponse(out, media_type="image/png")

        bg_bytes, content_type = fetch_image_bytes(slot.background_url)
        out_bytes, mime = generate_from_url_bytes(bg_bytes, content_type, meta)
        return StreamingResponse(io.BytesIO(out_bytes), media_type=mime)

# -----------------------------
# Placeholder: bot-triggered send
# -----------------------------
@app.post("/api/guilds/{guild_id}/send/{slot_number}")
def trigger_send(guild_id: str, slot_number: int):
    return {"ok": True}

# -----------------------------
# Health check (optional)
# -----------------------------
@app.get("/healthz")
def healthz():
    return {"ok": True}