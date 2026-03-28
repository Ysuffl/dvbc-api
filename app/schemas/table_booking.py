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

# Area Schemas
class AreaResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    floor_number: int = 1
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)

# Table Schemas
class TableBase(BaseModel):
    code: str
    x_pos: float
    y_pos: float
    shape: str
    status: TableStatus = TableStatus.AVAILABLE
    area_id: Optional[str] = None          # legacy
    area_fk_id: Optional[int] = None       # FK ke areas
    min_spending: float = 0.0              # minimum cash meja
    capacity: int = 4                      # kapasitas
    hold_until: Optional[datetime] = None
    hold_by_customer_id: Optional[int] = None

class TableCreate(TableBase):
    pass

class TableUpdate(BaseModel):
    code: Optional[str] = None
    x_pos: Optional[float] = None
    y_pos: Optional[float] = None
    shape: Optional[str] = None
    status: Optional[TableStatus] = None
    area_id: Optional[str] = None
    area_fk_id: Optional[int] = None
    min_spending: Optional[float] = None
    capacity: Optional[int] = None
    hold_until: Optional[datetime] = None
    hold_by_customer_id: Optional[int] = None

class TableBilled(BaseModel):
    billed_price: Optional[float] = None
# Master Level Schemas
class MasterLevelResponse(BaseModel):
    id: int
    name: str
    min_spending: float
    badge_color: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

# Tag Schemas
class TagResponse(BaseModel):
    id: int
    group_name: str
    name: str
    
    model_config = ConfigDict(from_attributes=True)

# Customer Schemas
class CustomerBase(BaseModel):
    name: str
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None

class CustomerCreate(BaseModel):
    name: str
    phone: str
    age: Optional[int] = None
    gender: Gender

class CustomerResponse(CustomerBase):
    id: int
    total_spending: float = 0.0
    master_level_id: int = 1
    master_level: Optional[MasterLevelResponse] = None
    total_visits: int = 0
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
    gender: Optional[Gender] = None
    pax: int
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None
    tag_ids: Optional[List[int]] = []

class EventBookingCreate(BaseModel):
    table_ids: List[int]
    customer_name: str
    customer_category: CustomerCategory = CustomerCategory.EVENT
    phone: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[Gender] = None
    pax: int
    start_time: datetime
    end_time: datetime
    notes: Optional[str] = None
    area_name: Optional[str] = None
    tag_ids: Optional[List[int]] = []

class BookingUpdate(BaseModel):
    pax: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    notes: Optional[str] = None
    status: Optional[BookingStatus] = None
    billed_at: Optional[datetime] = None
    billed_price: Optional[float] = None
    cancel_reason: Optional[str] = None
    tag_ids: Optional[List[int]] = None
    
    # Allow updating basic customer info via booking update
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_category: Optional[CustomerCategory] = None
    customer_age: Optional[int] = None
    customer_gender: Optional[Gender] = None

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
    category: Optional[str] = 'reguler'   # kategori booking
    notes: Optional[str] = None
    cancel_reason: Optional[str] = None
    tags: List[TagResponse] = []
    
    # Nested customer for convenience
    customer: Optional[CustomerResponse] = None

    model_config = ConfigDict(from_attributes=True)

class TableResponse(TableBase):
    id: int
    bookings: List[BookingResponse] = []
    hold_customer: Optional[CustomerResponse] = None
    area: Optional[AreaResponse] = None    # nested area info

    model_config = ConfigDict(from_attributes=True)

# WebSocket Response
class WSMessage(BaseModel):
    type: str
    data: dict
