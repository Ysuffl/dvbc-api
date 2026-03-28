from sqlalchemy import Column, Integer, String, Float, Numeric, Enum, ForeignKey, DateTime, Table as SQLTable
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
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
    HOLD = "hold"

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
    MALE = "MALE"
    FEMALE = "FEMALE"

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
    age = Column(Integer, nullable=True)
    gender = Column(Enum(Gender, native_enum=False, length=255, values_callable=lambda obj: [e.value for e in obj]), nullable=True)
    total_spending = Column(Float, default=0.0)
    master_level_id = Column(Integer, ForeignKey("master_levels.id"), default=1)
    total_visits = Column(Integer, default=0)   # sync dengan migration Laravel
    created_at = Column(DateTime, default=datetime.now)

    master_level = relationship("MasterLevel", lazy="joined")
    bookings = relationship("Booking", back_populates="customer")
    last_visit = Column(DateTime, nullable=True)

class Area(Base):
    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String, nullable=True)
    floor_number = Column(Integer, default=1)
    is_active = Column(String, default="1")  # boolean as string for compat
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tables = relationship("Table", back_populates="area")

class Table(Base):
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    x_pos = Column(Float, nullable=False)
    y_pos = Column(Float, nullable=False)
    shape = Column(String, nullable=False)
    status = Column(Enum(TableStatus, native_enum=False, length=255, values_callable=lambda obj: [e.value for e in obj]), default=TableStatus.AVAILABLE)
    area_id = Column(String, nullable=True)        # legacy string (tetap ada)
    area_fk_id = Column(Integer, ForeignKey("areas.id"), nullable=True)  # FK ke areas
    min_spending = Column(Numeric(15, 2), default=0)  # minimum cash untuk meja ini
    capacity = Column(Integer, default=4)              # kapasitas tempat duduk
    hold_until = Column(DateTime, nullable=True)
    hold_by_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)
    hold_customer = relationship("Customer", foreign_keys=[hold_by_customer_id], lazy="joined")
    area = relationship("Area", back_populates="tables", lazy="joined")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

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
    billed_price = Column(Numeric(15, 2), nullable=True)  # Numeric untuk presisi uang
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    status = Column(Enum(BookingStatus, native_enum=False, length=255, values_callable=lambda obj: [e.value for e in obj]), default=BookingStatus.PENDING)
    category = Column(Enum(CustomerCategory, native_enum=False, length=255, values_callable=lambda obj: [e.value for e in obj]), default=CustomerCategory.REGULER)
    notes = Column(String, nullable=True)
    cancel_reason = Column(String, nullable=True)

    table = relationship("Table", back_populates="bookings")
    customer = relationship("Customer", back_populates="bookings")
    tags = relationship("MasterTag", secondary=booking_tags, lazy="joined")
