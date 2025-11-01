import os
import io
import secrets
from fastapi import FastAPI, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from urllib.parse import urlencode
from models import SessionLocal, Base, engine, Slot, GuildConfig
from utils import fetch_image_bytes, generate_from_url_bytes, draw_slot_on_image
import cloudinary
import cloudinary.uploader
import httpx
from pydantic import BaseModel

# Init DB
Base.metadata.create_all(bind=engine)

# Config
DISCORD_CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
DISCORD_CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
OAUTH_REDIRECT_URI = os.getenv("OAUTH_REDIRECT_URI", f"{BACKEND_URL}/auth/callback")
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))

# Cloudinary setup
import os
import cloudinary

CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "")

if CLOUDINARY_URL:
    os.environ["CLOUDINARY_URL"] = CLOUDINARY_URL  # ensure it's visible to SDK
    cloudinary.config(secure=True)
else:
    cloudinary.config(
        cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
        api_key=os.getenv("CLOUDINARY_API_KEY"),
        api_secret=os.getenv("CLOUDINARY_API_SECRET"),
        secure=True
    )



app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Pydantic
class SlotUpdate(BaseModel):
    slot_number: int
    teamname: str = ""
    teamtag: str = ""
    emoji: str = ""
    font_family: str = "DejaVuSans.ttf"
    font_size: int = 48
    font_color: str = "#FFFFFF"
    is_gif: int = 0
    padding_top: int = 0     # NEW
    padding_bottom: int = 0  # NEW

# OAuth: login
@app.get("/auth/login")
def auth_login():
    params = {
        "client_id": DISCORD_CLIENT_ID,
        "redirect_uri": OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": "identify guilds"
    }
    return RedirectResponse("https://discord.com/api/oauth2/authorize?" + urlencode(params))

@app.get("/auth/callback")
async def auth_callback(code: str):
    import urllib.parse, json

    async with httpx.AsyncClient() as client:
        data = {
            "client_id": DISCORD_CLIENT_ID,
            "client_secret": DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": OAUTH_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        # Exchange code for access token
        r = await client.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
        if r.status_code != 200:
            return JSONResponse({"error": "Token exchange failed", "details": r.text}, status_code=400)
        tokens = r.json()
        access_token = tokens.get("access_token")

        # Fetch user's guilds
        r2 = await client.get(
            "https://discord.com/api/users/@me/guilds",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if r2.status_code != 200:
            return JSONResponse({"error": "Guild fetch failed", "details": r2.text}, status_code=400)
        guilds = r2.json()

    # ✅ Redirect user to frontend with encoded guilds
    frontend_url = os.getenv("FRONTEND_URL", "https://slotmanager-frontend.onrender.com")
    encoded_guilds = urllib.parse.quote(json.dumps(guilds))
    return RedirectResponse(f"{frontend_url}/?guilds={encoded_guilds}")


@app.get("/api/guilds/{guild_id}/slots")
def list_slots(guild_id: str):
    db = next(get_db())
    slots = db.query(Slot).filter(Slot.guild_id == guild_id).order_by(Slot.slot_number).all()
    if not slots:
        for s in range(2, 26):
            slot = Slot(guild_id=guild_id, slot_number=s)
            db.add(slot)
        db.commit()
        slots = db.query(Slot).filter(Slot.guild_id == guild_id).order_by(Slot.slot_number).all()
    return [{
        "slot_number": s.slot_number,
        "teamname": s.teamname,
        "teamtag": s.teamtag,
        "emoji": s.emoji,
        "background_url": s.background_url,
        "is_gif": bool(s.is_gif),
        "font_family": s.font_family,
        "font_size": s.font_size,
        "font_color": s.font_color,
        "padding_top": s.padding_top,        # NEW
        "padding_bottom": s.padding_bottom   # NEW
    } for s in slots]

@app.post("/api/guilds/{guild_id}/slots/{slot_number}/upload")
async def upload_background(guild_id: str, slot_number: int, file: UploadFile = File(...)):
    contents = await file.read()
    pub = f"slot_{guild_id}_{slot_number}_{int(__import__('time').time())}"
    # Cloudinary upload_large supports big gifs
    res = cloudinary.uploader.upload_large(io.BytesIO(contents), public_id=pub, resource_type="auto", overwrite=True)
    url = res.get("secure_url") or res.get("url")
    is_gif = 1 if res.get("format","").lower() == "gif" else 0

    db = next(get_db())
    slot = db.query(Slot).filter(Slot.guild_id==guild_id, Slot.slot_number==slot_number).first()
    if not slot:
        slot = Slot(guild_id=guild_id, slot_number=slot_number)
        db.add(slot)
    slot.background_url = url
    slot.is_gif = is_gif
    db.commit()
    return {"url": url, "is_gif": bool(is_gif)}

@app.post("/api/guilds/{guild_id}/slots/{slot_number}")
def update_slot(guild_id: str, slot_number: int, payload: SlotUpdate):
    db = next(get_db())
    slot = db.query(Slot).filter(Slot.guild_id==guild_id, Slot.slot_number==slot_number).first()
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
    slot.padding_top = payload.padding_top        # NEW
    slot.padding_bottom = payload.padding_bottom  # NEW
    db.commit()
    return {"ok": True}

@app.post("/api/guilds/{guild_id}/channel")
def set_channel(guild_id: str, channel_id: str = Form(...)):
    db = next(get_db())
    cfg = db.query(GuildConfig).filter(GuildConfig.guild_id==guild_id).first()
    if not cfg:
        cfg = GuildConfig(guild_id=guild_id, channel_id=channel_id)
        db.add(cfg)
    else:
        cfg.channel_id = channel_id
    db.commit()
    return {"ok": True}

@app.get("/api/guilds/{guild_id}/channel")
def get_channel(guild_id: str):
    db = next(get_db())
    cfg = db.query(GuildConfig).filter(GuildConfig.guild_id==guild_id).first()
    return {"channel_id": cfg.channel_id if cfg else ""}

@app.get("/api/guilds/{guild_id}/channels")
def get_guild_channels(guild_id: str):
    if not DISCORD_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}
    url = f"https://discord.com/api/v10/guilds/{guild_id}/channels"
    resp = httpx.get(url, headers=headers, timeout=20.0)
    resp.raise_for_status()
    channels = resp.json()
    text_channels = [ {"id": c["id"], "name": c.get("name"), "type": c.get("type")} for c in channels if c.get("type") in (0,5) ]
    return {"channels": text_channels}

@app.get("/api/generate/{guild_id}/{slot_number}")
def api_generate(guild_id: str, slot_number: int):
    db = next(get_db())
    slot = db.query(Slot).filter(Slot.guild_id==guild_id, Slot.slot_number==slot_number).first()
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
        "padding_bottom": slot.padding_bottom
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

@app.post("/api/guilds/{guild_id}/send/{slot_number}")
def trigger_send(guild_id: str, slot_number: int):
    return {"ok": True}
