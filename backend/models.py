import os
from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.sql import func

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# SQLAlchemy setup
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()

# ------------------------------------------------------------
# Slot Model
# ------------------------------------------------------------
class Slot(Base):
    __tablename__ = "slots"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, index=True)
    slot_number = Column(Integer, index=True)
    teamname = Column(String, default="")
    teamtag = Column(String, default="")
    emoji = Column(String, default="")         # text form (<:name:id> or unicode)
    emoji_url = Column(String, default="")     # actual CDN URL for Discord emojis
    background_url = Column(String, default="")
    is_gif = Column(Integer, default=0)
    font_family = Column(String, default="DejaVuSans.ttf")
    font_size = Column(Integer, default=48)
    font_color = Column(String, default="#FFFFFF")
    padding_top = Column(Integer, default=0)
    padding_bottom = Column(Integer, default=0)

    discord_message_id = Column(String, nullable=True)
    discord_channel_id = Column(String, nullable=True)

    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

# ------------------------------------------------------------
# Guild Config
# ------------------------------------------------------------
class GuildConfig(Base):
    __tablename__ = "guildconfigs"

    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, unique=True, index=True)
    channel_id = Column(String, default="")

# ------------------------------------------------------------
# Session Helper
# ------------------------------------------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------------------------------------
# Initialize tables
# ------------------------------------------------------------
Base.metadata.create_all(bind=engine)
print("✅ Database tables created or verified.")
