"""
Price Pulse Lahore — Database Models
SQLAlchemy ORM models + TimescaleDB hypertable setup
QA Pulse by SK · skakarh.com
"""

from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    Text, Index, UniqueConstraint, ForeignKey, Enum
)
from sqlalchemy.orm import DeclarativeBase, relationship
import enum


class Base(DeclarativeBase):
    pass


class Category(str, enum.Enum):
    vegetables           = "vegetables"
    fruits               = "fruits"
    poultry              = "poultry"
    essential_commodities = "essential_commodities"


class Direction(str, enum.Enum):
    up     = "up"
    down   = "down"
    stable = "stable"


# ── Table 1: items ─────────────────────────────────────────────────────────────
# Master list of all unique commodities. One row per item, never duplicated.
class Item(Base):
    __tablename__ = "items"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    slug            = Column(String(100), unique=True, nullable=False)   # e.g. "tomato"
    name_english    = Column(String(150), nullable=False)                # e.g. "Tomato"
    name_urdu       = Column(String(150), nullable=True)                 # e.g. "ٹماٹر"
    category        = Column(String(50), nullable=False)                 # vegetables / fruits / poultry / essential_commodities
    unit            = Column(String(20), nullable=False, default="kg")   # kg / litre / dozen / piece
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Aliases for fuzzy matching (e.g. "Tamatar", "Tamater", "Tomatoes")
    aliases         = Column(Text, nullable=True)  # JSON array stored as text

    # Relationship
    price_readings  = relationship("PriceReading", back_populates="item")

    def __repr__(self):
        return f"<Item {self.slug} ({self.category})>"


# ── Table 2: price_readings ────────────────────────────────────────────────────
# One row per item per day. This becomes a TimescaleDB hypertable.
# All trend/change fields are pre-computed on write for fast API reads.
class PriceReading(Base):
    __tablename__ = "price_readings"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    item_id         = Column(Integer, ForeignKey("items.id"), nullable=False)
    date            = Column(DateTime(timezone=True), nullable=False)     # the date this price applies to

    # Raw prices from OCR
    min_price       = Column(Integer, nullable=False, default=0)          # PKR
    max_price       = Column(Integer, nullable=False, default=0)          # PKR
    avg_price       = Column(Float,   nullable=False, default=0.0)        # (min+max)/2

    # Quality grade if mentioned (A, B, C or null)
    quality         = Column(String(5), nullable=True)

    # Pre-computed change fields (calculated on insert vs previous day)
    prev_avg_price  = Column(Float,   nullable=True)                      # yesterday's avg
    price_change    = Column(Float,   nullable=True)                      # absolute change in PKR
    price_change_pct= Column(Float,   nullable=True)                      # % change vs yesterday
    direction       = Column(String(10), nullable=True)                   # up / down / stable

    # 7-day rolling average (pre-computed)
    avg_7d          = Column(Float, nullable=True)

    # Source metadata
    source_url      = Column(Text, nullable=True)
    scraped_at      = Column(DateTime(timezone=True), nullable=True)

    created_at      = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationship
    item            = relationship("Item", back_populates="price_readings")

    # Unique: one reading per item per day
    __table_args__ = (
        UniqueConstraint("item_id", "date", name="uq_item_date"),
        Index("ix_price_readings_date", "date"),
        Index("ix_price_readings_item_id", "item_id"),
        Index("ix_price_readings_item_date", "item_id", "date"),
    )

    def __repr__(self):
        return f"<PriceReading item_id={self.item_id} date={self.date} avg={self.avg_price}>"


# ── Table 3: scrape_logs ───────────────────────────────────────────────────────
# Audit trail for every pipeline run. Essential for debugging + monitoring.
class ScrapeLog(Base):
    __tablename__ = "scrape_logs"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    run_at          = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status          = Column(String(20), nullable=False)  # success / partial / failed
    categories_ok   = Column(Text, nullable=True)         # JSON array of successful categories
    categories_fail = Column(Text, nullable=True)         # JSON array of failed categories
    images_scraped  = Column(Integer, default=0)
    records_extracted = Column(Integer, default=0)
    duration_seconds  = Column(Float, nullable=True)
    error_message   = Column(Text, nullable=True)
    pipeline_version  = Column(String(20), nullable=True, default="1.0.0")

    def __repr__(self):
        return f"<ScrapeLog {self.run_at} status={self.status} records={self.records_extracted}>"
