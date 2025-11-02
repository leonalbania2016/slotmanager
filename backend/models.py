import os
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Slot(Base):
    __tablename__ = "slots"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, index=True)
    slot_number = Column(Integer, index=True)
    teamname = Column(String, default="")
    teamtag = Column(String, default="")
    emoji = Column(String, default="")
    background_url = Column(String, default="")  # Cloudinary URL or empty
    is_gif = Column(Integer, default=0)
    font_family = Column(String, default="DejaVuSans.ttf")
    font_size = Column(Integer, default=48)
    font_color = Column(String, default="#FFFFFF")
    padding_top = Column(Integer, default=0)
    padding_bottom = Column(Integer, default=0)


class GuildConfig(Base):
    __tablename__ = "guildconfigs"
    id = Column(Integer, primary_key=True, index=True)
    guild_id = Column(String, unique=True, index=True)
    channel_id = Column(String, default="")


# ✅ Add this helper at the bottom
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
