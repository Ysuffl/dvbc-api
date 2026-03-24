from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
import enum

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

# Table Schemas
class TableBase(BaseModel):
    code: str
    x_pos: float
    y_pos: float
    shape: str
    status: TableStatus = TableStatus.AVAILABLE
    area_id: str

class TableCreate(TableBase):
    pass

class TableUpdate(BaseModel):
    code: Optional[str] = None
    x_pos: Optional[float] = None
    y_pos: Optional[float] = None
    shape: Optional[str] = None
    status: Optional[TableStatus] = None
    area_id: Optional[str] = None

class TableBilled(BaseModel):
    billed_price: Optional[float] = None

# Customer Schemas
class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    category: CustomerCategory = CustomerCategory.REGULER
    age: Optional[int] = None

class CustomerResponse(CustomerBase):
    id: int
    total_spending: float = 0.0
    master_level: str = "Bronze"
    last_status: Optional[BookingStatus] = None
    last_visit: Optional[datetime] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# Booking Schemas
class BookingBase(BaseModel):
    table_id: int
    customer_id: int
    pax: int
    start_time: datetime
    end_time: datetime
    billed_at: Optional[datetime] = None
    billed_price: Optional[float] = None
    status: BookingStatus = BookingStatus.PENDING
    notes: Optional[str] = None
    cancel_reason: Optional[str] = None

class BookingCreate(BaseModel):
    table_id: int
    customer_name: str
    customer_category: CustomerCategory = CustomerCategory.REGULER
    phone: Optional[str] = None
    age: Optional[int] = None
    pax: int
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None

class EventBookingCreate(BaseModel):
    table_ids: List[int]
    customer_name: str
    customer_category: CustomerCategory = CustomerCategory.EVENT
    phone: Optional[str] = None
    age: Optional[int] = None
    pax: int
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None
    area_name: Optional[str] = None

class BookingUpdate(BaseModel):
    status: Optional[BookingStatus] = None
    billed_at: Optional[datetime] = None
    billed_price: Optional[float] = None
    cancel_reason: Optional[str] = None

class BookingResponse(BaseModel):
    id: int
    table_id: int
    customer_id: int
    pax: int
    start_time: datetime
    end_time: datetime
    billed_at: Optional[datetime] = None
    billed_price: Optional[float] = None
    status: BookingStatus
    notes: Optional[str] = None
    cancel_reason: Optional[str] = None
    
    # Nested customer for convenience
    customer: Optional[CustomerResponse] = None

    model_config = ConfigDict(from_attributes=True)

class TableResponse(TableBase):
    id: int
    bookings: List[BookingResponse] = []

    model_config = ConfigDict(from_attributes=True)

# WebSocket Response
class WSMessage(BaseModel):
    type: str
    data: dict
