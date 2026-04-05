"""
Seed the admin user (Sandeep) into the new PostgreSQL database
and insert baseline health data (DEXA, VO2 max, UserProfile).

Run from backend/ with the venv active:
    python ../scripts/seed_admin_user.py
"""
import sys
import os
import uuid
from datetime import date, datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from database.engine import SessionLocal
from database.models import User, UserProfile, DexaScan, Vo2MaxLog
from config import settings


def seed():
    db = SessionLocal()
    try:
        admin_email = settings.admin_email or settings.allowed_email
        if not admin_email:
            print("ERROR: Set ADMIN_EMAIL in .env before running this script.")
            return

        # ── 1. Create admin User row ──────────────────────────────────────────
        existing_user = db.query(User).filter(User.email == admin_email.lower()).first()
        if existing_user:
            admin_user = existing_user
            print(f"User already exists: {admin_email} (id={admin_user.id})")
        else:
            admin_user = User(
                id=uuid.uuid4(),
                email=admin_email.lower(),
                name="Sandeep Rao",
                auth_provider="google",
                is_active=True,
                is_admin=True,
            )
            db.add(admin_user)
            db.flush()
            print(f"Created admin user: {admin_email} (id={admin_user.id})")

        user_id = admin_user.id

        # ── 2. Create UserProfile ─────────────────────────────────────────────
        existing_profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        if not existing_profile:
            profile = UserProfile(
                user_id=user_id,
                name="Sandeep Rao",
                email=admin_email.lower(),
                dob=date(1979, 11, 11),
                height_inches=68.0,
                bf_goal_pct=18.0,
                vo2max_goal=50.0,
                goal_date=date(2026, 12, 31),
                calorie_target=2200,
                measurement_system="imperial",
                training_device="tonal",
                dietary_preference="vegetarian",
                mcp_api_key=str(uuid.uuid4()),
                onboarding_complete=True,
                weekly_email_enabled=True,
                weekly_email_cc="preetha.s.rao@gmail.com",
            )
            db.add(profile)
            print(f"Created UserProfile for {admin_email}")
        else:
            # Ensure existing profile has the new fields set
            if not existing_profile.mcp_api_key:
                existing_profile.mcp_api_key = str(uuid.uuid4())
            existing_profile.onboarding_complete = True
            existing_profile.dietary_preference = existing_profile.dietary_preference or "vegetarian"
            print(f"UserProfile already exists — updated missing fields.")

        # ── 3. Seed DEXA baseline ─────────────────────────────────────────────
        existing_dexa = db.query(DexaScan).filter(
            DexaScan.user_id == user_id,
            DexaScan.scan_date == date(2026, 3, 13),
        ).first()
        if not existing_dexa:
            db.add(DexaScan(
                user_id=user_id,
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
            print("Seeded DEXA baseline (2026-03-13)")

        # ── 4. Seed VO2 max baseline ──────────────────────────────────────────
        existing_vo2 = db.query(Vo2MaxLog).filter(
            Vo2MaxLog.user_id == user_id,
            Vo2MaxLog.date == date(2026, 3, 13),
        ).first()
        if not existing_vo2:
            db.add(Vo2MaxLog(
                user_id=user_id,
                date=date(2026, 3, 13),
                vo2max=45.0,
                source="manual",
            ))
            print("Seeded VO2 max baseline (2026-03-13)")

        db.commit()
        print("\nSeed complete.")
        print(f"  Admin user_id: {user_id}")

        # Print MCP key for reference
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        print(f"  MCP API key:   {profile.mcp_api_key}")

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    seed()
