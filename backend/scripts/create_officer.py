import getpass
import sys

from app.auth import hash_password
from app.db.session import SessionLocal, engine
from app.models.user import User


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python scripts/create_officer.py <email> <display-name>")

    email = sys.argv[1].strip().lower()
    display_name = sys.argv[2].strip()
    password = getpass.getpass("Officer password: ")

    if not password:
        raise SystemExit("Password cannot be empty")

    db = SessionLocal()
    try:
        # Keep the local seed command usable when migration 003 has not run yet.
        User.__table__.create(bind=engine, checkfirst=True)
        existing = db.query(User).filter(User.email == email).first()
        if existing is not None:
            raise SystemExit("An account with this email already exists")

        db.add(
            User(
                email=email,
                password_hash=hash_password(password),
                display_name=display_name,
                role="OFFICER",
            )
        )
        db.commit()
        print(f"Created officer account for {email}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
