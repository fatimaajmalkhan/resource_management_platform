"""Database connection -- the one place the connection string lives."""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from dotenv import load_dotenv

# Ensure environment variables are loaded (e.g. when db.py is imported directly by scripts/tests)
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///resource_platform.db")

# Standardize postgres:// to postgresql:// for SQLAlchemy compatibility in cloud deployments
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Ensure SQLite relative paths are absolute relative to the project root to prevent duplicate DBs
if DATABASE_URL.startswith("sqlite:///"):
    db_file = DATABASE_URL[9:]
    if not os.path.isabs(db_file):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        abs_path = os.path.join(project_root, db_file).replace("\\", "/")
        DATABASE_URL = f"sqlite:///{abs_path}"

# SQLite-specific connection pooling and settings
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False, "timeout": 30},
        poolclass=NullPool,  # Create new connection for each request (best for SQLite + async)
        echo=False
    )
    # Enable foreign keys and optimize for bulk inserts
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")  # Write-ahead logging for better concurrency
        cursor.execute("PRAGMA synchronous=NORMAL")  # Faster writes without sacrificing safety
        cursor.close()
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def get_session():
    return SessionLocal()