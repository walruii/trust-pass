import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

# Reads the .env file in the current working directory and populates os.environ
load_dotenv()

# PostgreSQL URL format: postgresql://<user>:<password>@<host>:<port>/<dbname>
DATABASE_URL = os.getenv(
    "DATABASE_URL",
)

# pool_pre_ping=True checks for stale connections before executing queries
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session factory for route dependencies
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for ORM models
class Base(DeclarativeBase):
    pass

# Dependency generator for database sessions
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
