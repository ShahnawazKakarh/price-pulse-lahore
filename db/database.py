"""
Price Pulse Lahore — Database Connection & Session
QA Pulse by SK · skakarh.com
"""

import os
import logging
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from db.models import Base

load_dotenv()

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/price_pulse")

# Create engine
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,   # verify connection health before use
    echo=False,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def get_db() -> Session:
    """Context manager for DB sessions. Auto-commits or rolls back."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Create all tables and convert price_readings to a TimescaleDB hypertable.
    Safe to run multiple times (idempotent).
    """
    logger.info("Initialising database...")

    # Create all SQLAlchemy tables
    Base.metadata.create_all(bind=engine)
    logger.info("Tables created (or already exist)")

    # Convert price_readings to TimescaleDB hypertable
    with engine.connect() as conn:
        try:
            # Check if TimescaleDB extension is available
            result = conn.execute(text(
                "SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"
            ))
            has_timescale = result.fetchone() is not None

            if has_timescale:
                # Check if already a hypertable
                result = conn.execute(text(
                    "SELECT 1 FROM timescaledb_information.hypertables "
                    "WHERE hypertable_name = 'price_readings'"
                ))
                already_hypertable = result.fetchone() is not None

                if not already_hypertable:
                    conn.execute(text(
                        "SELECT create_hypertable('price_readings', 'date', "
                        "if_not_exists => TRUE)"
                    ))
                    conn.commit()
                    logger.info("price_readings converted to TimescaleDB hypertable")
                else:
                    logger.info("price_readings is already a hypertable")
            else:
                logger.warning(
                    "TimescaleDB extension not found — running as standard PostgreSQL. "
                    "Install TimescaleDB for time-series optimisation."
                )

        except Exception as e:
            logger.warning(f"TimescaleDB setup skipped: {e}")

    logger.info("Database initialisation complete")


def check_connection() -> bool:
    """Quick health check — returns True if DB is reachable."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"DB connection failed: {e}")
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    if not check_connection():
        logger.error("Cannot connect to database. Check DATABASE_URL in .env")
        sys.exit(1)

    init_db()
    logger.info("Done.")
