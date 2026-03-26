from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey, DateTime, Table as SQLTable
from sqlalchemy.orm import relationship
from app.db.base_class import Base
import enum
from datetime import datetime

class TableStatus(str, enum.Enum):
    AVAILABLE = "available"
    BOOKED = "booked"
    OCCUPIED = "occupied"
    BILLED = "billed"
    OUT_OF_SERVICE = "out_of_service"
    HOLD = "hold"

class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    ARRIVED = "arrived"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    BILLED = "billed"

class CustomerCategory(str, enum.Enum):
    REGULER = "reguler"
    EVENT = "event"
    PRIORITAS = "prioritas"
    BIG_SPENDER = "big_spender"
    DRINKER = "drinker"
    PARTY = "party"
    DINNER = "dinner"
    LUNCH = "lunch"
    FAMILY = "family"
    YOUNGSTER = "youngster"
    
class Gender(str, enum.Enum):
    MALE = "Laki-laki"
    FEMALE = "Perempuan"

booking_tags = SQLTable(
    "booking_tags",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("booking_id", Integer, ForeignKey("bookings.id", ondelete="CASCADE")),
    Column("tag_id", Integer, ForeignKey("master_tags.id", ondelete="CASCADE")),
)

class MasterTag(Base):
    __tablename__ = "master_tags"

    id = Column(Integer, primary_key=True, index=True)
    group_name = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class MasterLevel(Base):
    __tablename__ = "master_levels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    min_spending = Column(Float, default=0.0)
    badge_color = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

def compute_master_level_id(total_spending: float) -> int:
    if total_spending >= 20_000_000:
        return 4 # Platinum
    elif total_spending >= 5_000_000:
        return 3 # Gold
    elif total_spending >= 1_000_000:
        return 2 # Silver
    return 1 # Bronze

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    category = Column(Enum(CustomerCategory, native_enum=False, length=255), default=CustomerCategory.REGULER)
    age = Column(Integer, nullable=True)
    gender = Column(Enum(Gender, native_enum=False, length=255), nullable=True)
    total_spending = Column(Float, default=0.0)
    master_level_id = Column(Integer, ForeignKey("master_levels.id"), default=1)
    created_at = Column(DateTime, default=datetime.now)

    master_level = relationship("MasterLevel", lazy="joined")
    bookings = relationship("Booking", back_populates="customer")
    last_status = Column(Enum(BookingStatus, native_enum=False, length=255), nullable=True)
    last_visit = Column(DateTime, nullable=True)

class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    x_pos = Column(Float, nullable=False)
    y_pos = Column(Float, nullable=False)
    shape = Column(String, nullable=False)
    status = Column(Enum(TableStatus, native_enum=False, length=255), default=TableStatus.AVAILABLE)
    area_id = Column(String, nullable=False)
    hold_until = Column(DateTime, nullable=True)
    hold_by_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    hold_customer = relationship("Customer", foreign_keys=[hold_by_customer_id], lazy="joined")

    bookings = relationship("Booking", back_populates="table")

class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    pax = Column(Integer, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    billed_at = Column(DateTime, nullable=True)
    billed_price = Column(Float, nullable=True)
    status = Column(Enum(BookingStatus, native_enum=False, length=255), default=BookingStatus.PENDING)
    notes = Column(String, nullable=True)
    cancel_reason = Column(String, nullable=True)

    table = relationship("Table", back_populates="bookings")
    customer = relationship("Customer", back_populates="bookings")
    tags = relationship("MasterTag", secondary=booking_tags, lazy="joined")
