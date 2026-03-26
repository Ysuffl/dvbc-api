from sqlalchemy import Column, Integer, String, Float, Enum, ForeignKey, DateTime
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

def compute_master_level(total_spending: float) -> str:
    if total_spending >= 7_000_000:
        return "Platinum"
    elif total_spending >= 3_000_000:
        return "Gold"
    elif total_spending >= 1_000_000:
        return "Silver"
    return "Bronze"

class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    category = Column(Enum(CustomerCategory), default=CustomerCategory.REGULER)
    age = Column(Integer, nullable=True)
    total_spending = Column(Float, default=0.0)
    master_level = Column(String(20), default="Bronze")
    created_at = Column(DateTime, default=datetime.now)

    bookings = relationship("Booking", back_populates="customer")
    last_status = Column(Enum(BookingStatus), nullable=True)
    last_visit = Column(DateTime, nullable=True)

class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    x_pos = Column(Float, nullable=False)
    y_pos = Column(Float, nullable=False)
    shape = Column(String, nullable=False)
    status = Column(Enum(TableStatus), default=TableStatus.AVAILABLE)
    area_id = Column(String, nullable=False)

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
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING)
    notes = Column(String, nullable=True)
    cancel_reason = Column(String, nullable=True)

    table = relationship("Table", back_populates="bookings")
    customer = relationship("Customer", back_populates="bookings")
