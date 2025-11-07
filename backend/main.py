import os
import io
import time
import json
from urllib.parse import quote
import httpx
import imageio
from typing import Optional, List, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pydantic import BaseModel
from sqlalchemy import text

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response

from models import Base, engine, get_db, Slot, GuildConfig

# =============================================================================
# App & CORS
# =============================================================================
app = FastAPI(title="Slot Manager Backend")

FRONTEND_URL = os.getenv("VITE_FRONTEND_URL") or os.getenv("FRONTEND_URL", "https://slotmanager-frontend.onrender.com")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://slotmanager-backend.onrender.com/auth/callback")
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://slotmanager-frontend.onrender.com"],  # adjust
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Files / Paths
# =============================================================================
BASE_DIR = os.path.dirname(__file__)
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
GIFS_DIR = os.path.join(ASSETS_DIR, "gifs")
os.makedirs(GIFS_DIR, exist_ok=True)
DEFAULT_GIF_NAME = "default.gif"  # put one here: backend/assets/gifs/default.gif

# =============================================================================
# DB bootstrap / safe migrations
# =============================================================================
print("Initializing database...")
Base.metadata.create_all(bind=engine)

def _ensure_columns():
    with engine.begin() as conn:
        for col in ("discord_message_id", "discord_channel_id"):
            try:
                conn.execute(text(f"ALTER TABLE slots ADD COLUMN {col} VARCHAR"))
            except Exception:
                pass

_ensure_columns()
print("Database ready.")

# =============================================================================
# Helpers
# =============================================================================
def _db():
    return next(get_db())

# --- Emoji image cache for speed --------------------------------------------
EMOJI_IMG_CACHE: dict[str, Image.Image] = {}

def _fetch_emoji_image(url: str, target_px: int) -> Optional[Image.Image]:
    """Download and cache an emoji image (static or animated first frame) and scale to ~target_px height."""
    if not url or not url.startswith("http"):
        return None
    key = f"{url}@{target_px}"
    if key in EMOJI_IMG_CACHE:
        return EMOJI_IMG_CACHE[key]
    try:
        r = httpx.get(url, timeout=10.0)
        r.raise_for_status()
        img = Image.open(io.BytesIO(r.content)).convert("RGBA")
        # Scale height to target_px
        ratio = target_px / max(1, img.height)
        new_w = max(1, int(img.width * ratio))
        new_h = max(1, int(img.height * ratio))
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        EMOJI_IMG_CACHE[key] = img
        return img
    except Exception:
        return None

def _iter_gif_frames(path: str):
    reader = imageio.get_reader(path, format="GIF")
    meta = reader.get_meta_data()
    duration = (meta.get("duration", 80) or 80) / 1000.0
    for frame in reader:
        yield Image.fromarray(frame).convert("RGBA"), duration

def _load_font(font_family: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    # Try given font family under ./fonts first, then system fallback
    font_path = os.path.join(BASE_DIR, "fonts", (font_family or "DejaVuSans.ttf"))
    try:
        return ImageFont.truetype(font_path, size)
    except Exception:
        try:
            return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)
        except Exception:
            return ImageFont.load_default()

def _render_text_with_glow(
    base_img: Image.Image,
    text: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    color_hex: str,
) -> None:
    """Render crisp text with a soft glow onto base_img at (x, y)."""
    # upscale canvas to improve glow quality
    upscale = 2
    large = base_img.resize((base_img.width * upscale, base_img.height * upscale), Image.Resampling.LANCZOS)
    text_layer = Image.new("RGBA", large.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(text_layer)

    # upscale font
    try:
        font_path = getattr(font, "path", None) or getattr(font, "font", None)
        size = getattr(font, "size", 48)
        ufont = ImageFont.truetype(font_path, size * upscale) if font_path else ImageFont.load_default()
    except Exception:
        ufont = ImageFont.load_default()

    ux, uy = x * upscale, y * upscale
    # soft glow
    glow = Image.new("RGBA", large.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            gd.text((ux + dx, uy + dy), text, font=ufont, fill=(0, 0, 0, 180))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=3))

    # main text
    d.text((ux, uy), text, font=ufont, fill=color_hex or "#FFFFFF")

    combined = Image.alpha_composite(large, glow)
    combined = Image.alpha_composite(combined, text_layer)
    final = combined.resize(base_img.size, Image.Resampling.LANCZOS)
    base_img.paste(final, (0, 0), final)

def _measure(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> Tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def _compose_slot_frame(
    base_img: Image.Image,
    slot_number: int,
    teamname: str,
    teamtag: str,
    emoji_value: Optional[str],
    font_family: Optional[str],
    font_size: Optional[int],
    font_color: Optional[str],
    padding_top: Optional[int],
    padding_bottom: Optional[int],
) -> Image.Image:
    """Draw: left=slot number, center=team (name/tag), right=emoji (image if URL, else unicode)."""
    img = base_img.copy()
    W, H = img.size

    fsize = int(font_size or 64)
    font = _load_font(font_family, fsize)
    color = font_color or "#FFFFFF"

    # vertical band
    top = int(padding_top if padding_top is not None else 0)
    bottom = max(0, H - int(padding_bottom or 0))
    usable_h = max(1, bottom - top)

    # texts
    main_text = ""
    if teamname and teamtag:
        main_text = f"{teamname} {teamtag}"
    else:
        main_text = teamname or teamtag or "FreeSlot"

    slot_text = f"{slot_number}:"

    d = ImageDraw.Draw(img)
    slot_w, slot_h = _measure(d, slot_text, font)
    main_w, main_h = _measure(d, main_text, font)

    # y center in band
    y_text = top + (usable_h - main_h) // 2

    # left slot number
    left_x = 24
    _render_text_with_glow(img, slot_text, font, left_x, y_text, color)

    # center main text
    center_x = (W - main_w) // 2
    _render_text_with_glow(img, main_text, font, center_x, y_text, color)

    # right emoji
    # if emoji_value startswith http -> treat as CDN image; otherwise draw unicode
    if emoji_value and isinstance(emoji_value, str):
        if emoji_value.startswith("http"):
            # target height ~ font size
            em = _fetch_emoji_image(emoji_value, target_px=fsize)
            if em is not None:
                ex = W - em.width - 24
                ey = top + (usable_h - em.height) // 2
                img.paste(em, (ex, ey), em)
        else:
            ew, eh = _measure(d, emoji_value, font)
            ex = W - ew - 24
            ey = top + (usable_h - eh) // 2
            _render_text_with_glow(img, emoji_value, font, ex, ey, color)

    return img

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
class SlotItem(BaseModel):
    slot_number: int
    teamname: Optional[str] = None
    teamtag: Optional[str] = None
    emoji: Optional[str] = None          # unicode (🔥) OR Discord CDN URL
    font_family: Optional[str] = None
    font_size: Optional[int] = None
    font_color: Optional[str] = None
    padding_top: Optional[int] = None
    padding_bottom: Optional[int] = None
    background_name: Optional[str] = None  # file name in assets/gifs

class BulkSlotsBody(BaseModel):
    slots: List[SlotItem]

class SendSlotsBody(BaseModel):
    channel_id: str
    gif_name: Optional[str] = None

class GuildChannelBody(BaseModel):
    channel_id: str

# =============================================================================
# Routes
# =============================================================================
# ----------------------------------------------------------------------
# Return available GIFs for the guild
# ----------------------------------------------------------------------
@app.get("/api/guilds/{guild_id}/gifs")
async def list_guild_gifs(guild_id: str):
    gifs_dir = os.path.join("assets", "gifs")
    try:
        files = [
            f
            for f in os.listdir(gifs_dir)
            if f.lower().endswith((".gif", ".mp4"))
        ]
        return {"status": "success", "gifs": files}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------
# Return Discord channels for the guild
# ----------------------------------------------------------------------
@app.get("/api/guilds/{guild_id}/channels")
async def get_guild_channels(guild_id: str):
    try:
        url = f"https://discord.com/api/guilds/{guild_id}/channels"
        headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail="Failed to fetch channels")
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
def root():
    return {"ok": True, "service": "slotmanager-backend"}

@app.get("/api/gifs")
def list_gifs():
    if not os.path.exists(GIFS_DIR):
        raise HTTPException(status_code=404, detail="GIF directory not found")
    files = [f for f in os.listdir(GIFS_DIR) if f.lower().endswith((".gif", ".png", ".jpg", ".jpeg", ".webp"))]
    return {"gifs": files}

# --- Guild Channels (for bot compatibility) ----------------------------------
@app.get("/api/guilds/{guild_id}/channel")
def get_guild_channel(guild_id: str):
    db = _db()
    gc = db.query(GuildConfig).filter(GuildConfig.guild_id == guild_id).first()
    return {"channel_id": gc.channel_id if gc else ""}

@app.post("/api/guilds/{guild_id}/channel")
def set_guild_channel(guild_id: str, body: GuildChannelBody):
    db = _db()
    gc = db.query(GuildConfig).filter(GuildConfig.guild_id == guild_id).first()
    if not gc:
        gc = GuildConfig(guild_id=guild_id, channel_id=body.channel_id)
        db.add(gc)
    else:
        gc.channel_id = body.channel_id
        db.add(gc)
    db.commit()
    return {"ok": True, "channel_id": gc.channel_id}

# --- Guild emojis (custom) ----------------------------------------------------
@app.get("/api/guilds/{guild_id}/emojis")
def list_guild_emojis(guild_id: str):
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    r = httpx.get(f"https://discord.com/api/v10/guilds/{guild_id}/emojis", headers=headers, timeout=15.0)
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    data = r.json()
    out = []
    for e in data:
        eid = e["id"]
        animated = bool(e.get("animated"))
        ext = "gif" if animated else "png"
        url = f"https://cdn.discordapp.com/emojis/{eid}.{ext}?quality=lossless"
        out.append({"id": eid, "name": e.get("name", ""), "animated": animated, "url": url})
    return {"emojis": out}

# --- Slots list & lazy init ---------------------------------------------------
@app.get("/api/guilds/{guild_id}/slots")
def list_slots(guild_id: str):
    db = _db()
    slots = (
        db.query(Slot)
        .filter(Slot.guild_id == guild_id)
        .order_by(Slot.slot_number)
        .all()
    )
    if not slots:
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
            "emoji": s.emoji,  # unicode or CDN url
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

# --- Save one slot (kept for compatibility) ----------------------------------
@app.post("/api/guilds/{guild_id}/slots/{slot_number}")
def update_slot(guild_id: str, slot_number: int, data: dict):
    db = _db()
    s = db.query(Slot).filter(Slot.guild_id == guild_id, Slot.slot_number == slot_number).first()
    if not s:
        s = Slot(guild_id=guild_id, slot_number=slot_number)
        db.add(s)
    for k in ("teamname", "teamtag", "emoji", "font_family", "font_size", "font_color", "padding_top", "padding_bottom"):
        if k in data and data[k] is not None:
            setattr(s, k, data[k])
    db.commit()
    return {"status": "ok"}

# --- Save ALL slots at once (one-button save) --------------------------------
@app.post("/api/guilds/{guild_id}/slots/bulk_update")
async def bulk_update_slots(guild_id: str, request: Request):
    """
    Save/update all provided slots in a single transaction.
    Hardened parsing to avoid 422s:
      - Accepts a plain array or an object with { "slots": [...] }.
      - Accepts background_name or background_url.
      - Coerces slot_number to int where possible.
      - Normalizes custom emoji formats to Discord CDN URLs.
    """
    try:
        raw = await request.json()
        print("📦 Incoming bulk_update body:", json.dumps(raw, indent=2))

        # Accept either a list or { "slots": [...] }
        if isinstance(raw, list):
            payload_slots = raw
        elif isinstance(raw, dict) and "slots" in raw and isinstance(raw["slots"], list):
            payload_slots = raw["slots"]
        else:
            raise HTTPException(status_code=400, detail="Body must be a list of slots or an object with 'slots' array")

        def to_emoji_value(raw_emoji: Optional[str]) -> Optional[str]:
            if not raw_emoji:
                return raw_emoji
            val = str(raw_emoji).strip()
            if val.startswith("http"):
                return val
            if val.startswith("<") and val.endswith(">") and ":" in val:
                parts = val.strip("<>").split(":")
                if len(parts) >= 2:
                    eid = parts[-1]
                    animated = parts[0] == "a"
                    ext = "gif" if animated else "png"
                    return f"https://cdn.discordapp.com/emojis/{eid}.{ext}?quality=lossless"
            return val

        db = _db()
        updated = 0

        for item in payload_slots:
            if not isinstance(item, dict):
                continue

            # Coerce/validate slot_number
            sn = item.get("slot_number")
            try:
                sn = int(sn)
            except Exception:
                # skip invalid slot entries rather than 422
                continue

            s = db.query(Slot).filter(Slot.guild_id == guild_id, Slot.slot_number == sn).first()
            if not s:
                s = Slot(guild_id=guild_id, slot_number=sn)
                db.add(s)

            # Normalize fields
            teamname = item.get("teamname")
            teamtag = item.get("teamtag")
            emoji = to_emoji_value(item.get("emoji"))
            font_family = item.get("font_family")
            font_size = item.get("font_size")
            font_color = item.get("font_color")
            padding_top = item.get("padding_top")
            padding_bottom = item.get("padding_bottom")

            # Accept background_name OR background_url
            background_name = item.get("background_name")
            background_url = item.get("background_url")
            bg_value = background_name or background_url or DEFAULT_GIF_NAME

            # Apply to model
            s.teamname = teamname
            s.teamtag = teamtag
            s.emoji = emoji
            s.font_family = font_family
            s.font_size = font_size
            s.font_color = font_color
            s.padding_top = padding_top
            s.padding_bottom = padding_bottom
            s.background_url = bg_value

            updated += 1

        db.commit()
        return {"ok": True, "updated": updated}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Never 422 on normalization issues—return helpful message
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")

# --- Single image generation (for bot) ---------------------------------------
@app.get("/api/generate/{guild_id}/{slot_number}")
def generate_single(guild_id: str, slot_number: int, gif_name: Optional[str] = None):
    """
    Generate and return a single slot image as GIF/PNG (bytes).
    Chooses a background from assets/gifs: gif_name or DEFAULT_GIF_NAME.
    Uses per-slot settings, including emoji (unicode or CDN url).
    """
    gif_file = gif_name or DEFAULT_GIF_NAME
    bg_path = os.path.join(GIFS_DIR, gif_file)
    if not os.path.isfile(bg_path):
        raise HTTPException(status_code=404, detail=f"Background not found: {gif_file}")

    db = _db()
    s = db.query(Slot).filter(Slot.guild_id == guild_id, Slot.slot_number == slot_number).first()
    if not s:
        raise HTTPException(status_code=404, detail="Slot not found")

    team = (s.teamname or "FreeSlot").strip()
    tag = (s.teamtag or "").strip()
    text = f"{team} {tag}".strip()

    is_gif = bg_path.lower().endswith(".gif")

    if is_gif:
        frames, durations = [], []
        for frame_img, dur in _iter_gif_frames(bg_path):
            frm = _compose_slot_frame(
                frame_img, s.slot_number, team, tag, s.emoji,
                s.font_family, s.font_size, s.font_color, s.padding_top, s.padding_bottom
            )
            frames.append(frm)
            durations.append(dur)

        out = io.BytesIO()
        pal = [f.convert("P", palette=Image.ADAPTIVE, dither=Image.Dither.NONE) for f in frames]
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
        return Response(content=out.getvalue(), media_type="image/gif")
    else:
        base = Image.open(bg_path).convert("RGBA")
        final = _compose_slot_frame(
            base, s.slot_number, team, tag, s.emoji,
            s.font_family, s.font_size, s.font_color, s.padding_top, s.padding_bottom
        )
        out = io.BytesIO()
        final.save(out, format="PNG")
        out.seek(0)
        return Response(content=out.getvalue(), media_type="image/png")

# --- Send or update all slots to a Discord channel ---------------------------
@app.post("/api/guilds/{guild_id}/send_slots")
def send_slots(guild_id: str, body: SendSlotsBody):
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="DISCORD_BOT_TOKEN not configured")

    channel_id = body.channel_id
    chosen_bg = body.gif_name or DEFAULT_GIF_NAME
    bg_path = os.path.join(GIFS_DIR, chosen_bg)
    if not os.path.isfile(bg_path):
        raise HTTPException(status_code=404, detail=f"Background not found: {chosen_bg}")

    db = _db()
    slots = (
        db.query(Slot)
        .filter(Slot.guild_id == guild_id)
        .order_by(Slot.slot_number)
        .all()
    )
    if not slots:
        raise HTTPException(status_code=404, detail="No slots found for this guild")

    is_gif = bg_path.lower().endswith(".gif")

    for s in slots:
        team = (s.teamname or "FreeSlot").strip()
        tag = (s.teamtag or "").strip()

        if is_gif:
            frames, durations = [], []
            for frame_img, dur in _iter_gif_frames(bg_path):
                frm = _compose_slot_frame(
                    frame_img, s.slot_number, team, tag, s.emoji,
                    s.font_family, s.font_size, s.font_color, s.padding_top, s.padding_bottom
                )
                frames.append(frm)
                durations.append(dur)

            out = io.BytesIO()
            pal = [f.convert("P", palette=Image.ADAPTIVE, dither=Image.Dither.NONE) for f in frames]
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
            base = Image.open(bg_path).convert("RGBA")
            final = _compose_slot_frame(
                base, s.slot_number, team, tag, s.emoji,
                s.font_family, s.font_size, s.font_color, s.padding_top, s.padding_bottom
            )
            out = io.BytesIO()
            final.save(out, format="PNG")
            out.seek(0)
            filename, file_bytes = f"slot_{s.slot_number}.png", out.getvalue()

        # send new or edit
        if s.discord_message_id and s.discord_channel_id == channel_id:
            resp = _discord_edit_file(channel_id, s.discord_message_id, filename, file_bytes, DISCORD_BOT_TOKEN)
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

        time.sleep(0.4)  # polite pacing

    return {"status": "sent"}

# =============================================================================
# OAuth callback – redirects to your frontend dashboard (SAFE ENCODING)
# =============================================================================
@app.get("/auth/callback")
def auth_callback(code: str):
    if not all([DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET, REDIRECT_URI]):
        raise HTTPException(status_code=500, detail="OAuth not configured")

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
        raise HTTPException(status_code=400, detail="Failed to get access token")

    token_json = token_response.json()
    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Missing access token")

    # Fetch user and guilds
    user_data = httpx.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    ).json()

    guilds_resp = httpx.get(
        "https://discord.com/api/users/@me/guilds",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15.0,
    )

    if guilds_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch guilds")

    guilds = guilds_resp.json()
    allowed = [
        {"id": g["id"], "name": g["name"]}
        for g in guilds
        if g.get("permissions", 0) & 0x20  # MANAGE_GUILD
    ]

    # Redirect to frontend with token and data
    encoded_guilds = quote(json.dumps(allowed))
    encoded_token = quote(access_token)
    redirect_url = (
        f"{FRONTEND_URL}/select-guild?"
        f"user_id={user_data['id']}"
        f"&username={quote(user_data['username'])}"
        f"&token={encoded_token}"
        f"&guilds={encoded_guilds}"
    )
    return RedirectResponse(url=redirect_url)
from fastapi.responses import RedirectResponse

DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
REDIRECT_URI = os.getenv(
    "REDIRECT_URI", "https://slotmanager-backend.onrender.com/auth/callback"
)
FRONTEND_URL = os.getenv(
    "FRONTEND_URL", "https://slotmanager-frontend.onrender.com"
)

@app.get("/login")
def discord_login():
    """
    Redirect the user to Discord OAuth2 authorization page.
    """
    if not DISCORD_CLIENT_ID:
        raise HTTPException(status_code=500, detail="DISCORD_CLIENT_ID not configured")

    params = (
        f"client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )

    return RedirectResponse(url=f"https://discord.com/api/oauth2/authorize?{params}")
