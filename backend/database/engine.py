from datetime import date, datetime
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from config import settings
from database.models import Base, DexaScan, Vo2MaxLog, UserProfile

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
)

# Enable WAL mode for better concurrent reads
@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    Base.metadata.create_all(bind=engine)
    _seed_initial_data()


def _seed_initial_data():
    db = SessionLocal()
    try:
        # Seed DEXA baseline (03/13/2026)
        existing_dexa = db.query(DexaScan).filter(
            DexaScan.scan_date == date(2026, 3, 13)
        ).first()
        if not existing_dexa:
            db.add(DexaScan(
                scan_date=date(2026, 3, 13),
                total_weight_lbs=181.5,
                body_fat_pct=28.4,
                fat_mass_lbs=52.0,
                lean_mass_lbs=123.9,
                bone_mass_lbs=6.1,
                visceral_fat_lbs=1.38,
                ag_ratio=1.17,
                almi=8.6,
                ffmi=19.7,
                t_score=0.50,
                facility="Dexafit Boston",
                notes="Baseline DEXA scan. Body score B-.",
                raw_pdf_path="health-metrics/Dexa - 03-13-2026.pdf",
            ))

        # Seed VO2 max baseline
        existing_vo2 = db.query(Vo2MaxLog).filter(
            Vo2MaxLog.date == date(2026, 3, 13)
        ).first()
        if not existing_vo2:
            db.add(Vo2MaxLog(
                date=date(2026, 3, 13),
                vo2max=45.0,
                source="manual",
            ))

        # Seed user profile
        existing_profile = db.query(UserProfile).first()
        if not existing_profile:
            db.add(UserProfile(
                name="Sandeep Rao",
                dob=date(1979, 11, 11),
                height_inches=68.0,
                bf_goal_pct=18.0,
                vo2max_goal=50.0,
                goal_date=date(2026, 12, 31),
                calorie_target=2200,
            ))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Seed error: {e}")
    finally:
        db.close()
