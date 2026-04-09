from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from sqlalchemy.orm import selectinload
from app.models.table_booking import Booking, Table, TableStatus, BookingStatus, Customer, MasterLevel, MasterTag, MasterTagGroup, CustomerCategory
from app.schemas.table_booking import BookingCreate, BookingUpdate, EventBookingCreate
from typing import List, Optional
from datetime import datetime, timedelta

def get_now():
    # Force Asia/Jakarta (UTC+7) to match Laravel
    return datetime.utcnow() + timedelta(hours=7)

async def get_bookings(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Booking]:
    query = select(Booking).options(
        selectinload(Booking.tags).selectinload(MasterTag.group),
        selectinload(Booking.customer)
    ).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.unique().scalars().all()

async def create_booking(db: AsyncSession, booking_in: BookingCreate) -> Optional[Booking]:
    # Check if table exists
    table_query = select(Table).where(Table.id == booking_in.table_id)
    table_result = await db.execute(table_query)
    db_table = table_result.scalar_one_or_none()
    
    if not db_table:
        return None

    # Check for overlapping bookings (only consider non-expired active bookings)
    now = get_now()
    overlap_query = select(Booking).where(
        Booking.table_id == booking_in.table_id,
        Booking.status.notin_([BookingStatus.CANCELLED, BookingStatus.HOLD, BookingStatus.COMPLETED]),
        Booking.start_time < booking_in.end_time,
        Booking.end_time > booking_in.start_time,
        Booking.end_time > now  # Ignore bookings that should have finished by now
    )
    overlap_result = await db.execute(overlap_query)
    if overlap_result.unique().scalars().first():
        raise ValueError("Table is already booked during this time")

    # Upsert Customer: find existing by name+phone or create new
    cust_query = select(Customer).where(
        Customer.name == booking_in.customer_name,
        Customer.phone == booking_in.phone
    )
    cust_result = await db.execute(cust_query)
    db_customer = cust_result.scalars().first()
    if not db_customer:
        db_customer = Customer(
            name=booking_in.customer_name,
            phone=booking_in.phone,
            age=booking_in.age,
            gender=booking_in.gender,
            nat=booking_in.nat,
        )
        db.add(db_customer)
        await db.flush()
    else:
        # Update age/gender/nat if provided and not yet set
        if booking_in.age is not None and db_customer.age is None:
            db_customer.age = booking_in.age
            db.add(db_customer)
        if booking_in.gender is not None and db_customer.gender is None:
            db_customer.gender = booking_in.gender
            db.add(db_customer)
        if booking_in.nat is not None:
            db_customer.nat = booking_in.nat
            db.add(db_customer)

    # Cancel ANY other HOLD bookings for this table to avoid lingering HOLDS
    all_holds_query = select(Booking).where(Booking.table_id == booking_in.table_id, Booking.status == BookingStatus.HOLD)
    all_holds_result = await db.execute(all_holds_query)
    all_holds = all_holds_result.unique().scalars().all()
    
    db_booking = None
    for hold_b in all_holds:
        if db_customer and hold_b.customer_id == db_customer.id and db_booking is None:
            db_booking = hold_b  # Reuse this one
        else:
            hold_b.status = BookingStatus.CANCELLED
            hold_b.cancel_reason = "Overwritten by new booking"
            db.add(hold_b)

    if db_booking and booking_in:
        # Update existing hold to pending
        db_booking.pax = booking_in.pax
        db_booking.start_time = booking_in.start_time
        db_booking.end_time = booking_in.end_time
        db_booking.status = BookingStatus.PENDING
        db_booking.notes = booking_in.notes
    elif booking_in and db_customer:
        # Create new
        db_booking = Booking(
            table_id=booking_in.table_id,
            customer_id=db_customer.id,
            pax=booking_in.pax,
            start_time=booking_in.start_time,
            end_time=booking_in.end_time,
            status=BookingStatus.PENDING,
            notes=booking_in.notes,
        )
    
    if not db_booking:
        return None
    
    # Attach Tags
    if booking_in.tag_ids:
        tag_query = select(MasterTag).where(MasterTag.id.in_(booking_in.tag_ids))
        tag_result = await db.execute(tag_query)
        db_booking.tags = tag_result.scalars().all()
        
    db.add(db_booking)
    
    db_table.status = TableStatus.BOOKED
    db_table.hold_until = None
    db_table.hold_by_customer_id = None
    db.add(db_table)
    
    await db.flush()  # Pastikan ID ter-generate sebelum commit
    booking_id = db_booking.id  # Simpan ID SEBELUM commit (expire)
    
    await db.commit()
    # Gunakan booking_id yang sudah disimpan, bukan db_booking.id (sudah expired)
    return await get_booking_by_id(db, booking_id)

async def get_booking_by_id(db: AsyncSession, booking_id: int) -> Optional[Booking]:
    query = select(Booking).options(
        selectinload(Booking.tags).selectinload(MasterTag.group),
        selectinload(Booking.customer)
    ).where(Booking.id == booking_id)
    result = await db.execute(query)
    return result.unique().scalar_one_or_none()

async def update_booking_status(db: AsyncSession, booking_id: int, status: BookingStatus, cancel_reason: Optional[str] = None, billed_price: Optional[float] = None) -> Optional[Booking]:
    db_booking = await get_booking_by_id(db, booking_id)
    if not db_booking:
        return None
    
    if cancel_reason is not None:
        db_booking.cancel_reason = cancel_reason

    # Simpan apakah ini billing sebelum overwrite status
    is_billed = (status == BookingStatus.BILLED)

    if is_billed:
        now = datetime.now()
        db_booking.billed_at = now
        if billed_price is not None:
            db_booking.billed_price = billed_price
        # billed → langsung completed
        status = BookingStatus.COMPLETED
    
    db_booking.status = status
        
    if db_booking.customer_id:
        cust_query = select(Customer).where(Customer.id == db_booking.customer_id)
        cust_result = await db.execute(cust_query)
        db_customer = cust_result.scalar_one_or_none()
        
        if db_customer:
            # Update total_spending dan level saat billed dari database (Source of Truth)
            if is_billed and billed_price is not None:
                # Precision fix: handles Decimal from DB vs float from API
                spending_before = float(db_customer.total_spending or 0.0)
                db_customer.total_spending = spending_before + float(billed_price)
                
                # Fetch levels from DB order by min_spending desc
                level_stmt = select(MasterLevel).where(MasterLevel.min_spending <= db_customer.total_spending).order_by(MasterLevel.min_spending.desc()).limit(1)
                level_res = await db.execute(level_stmt)
                matching_level = level_res.scalar_one_or_none()
                if matching_level:
                    db_customer.master_level_id = matching_level.id
            
            # Increment total_visits saat customer benar-benar datang (ARRIVED)
            if status == BookingStatus.ARRIVED:
                db_customer.total_visits = (db_customer.total_visits or 0) + 1
            
            db_customer.last_visit = datetime.now()
            db.add(db_customer)

    table_query = select(Table).where(Table.id == db_booking.table_id)
    table_result = await db.execute(table_query)
    db_table = table_result.scalar_one_or_none()

    if status in [BookingStatus.CANCELLED, BookingStatus.COMPLETED]:
        if db_table:
            db_table.status = TableStatus.AVAILABLE
            db_table.hold_until = None
            db_table.hold_by_customer_id = None
            db.add(db_table)
        db.add(db_booking)
        booking_id_val = db_booking.id
        await db.commit()
        return await get_booking_by_id(db, booking_id_val)
    
    elif status == BookingStatus.CONFIRMED:
        if db_table:
            db_table.status = TableStatus.BOOKED
            db_table.hold_until = None
            db_table.hold_by_customer_id = None
            db.add(db_table)
    
    elif status == BookingStatus.ARRIVED:
        if db_table:
            db_table.status = TableStatus.OCCUPIED
            db.add(db_table)

    db.add(db_booking)
    booking_id_val = db_booking.id
    await db.commit()
    return await get_booking_by_id(db, booking_id_val)

async def get_customers(db: AsyncSession) -> List[Customer]:
    result = await db.execute(select(Customer).options(selectinload(Customer.master_level)).order_by(Customer.name))
    return result.scalars().all()

from app.schemas.table_booking import CustomerCreate

async def create_customer(db: AsyncSession, customer_in: CustomerCreate) -> Customer:
    db_customer = Customer(
        name=customer_in.name,
        phone=customer_in.phone,
        age=customer_in.age,
        gender=customer_in.gender,
        nat=customer_in.nat,
    )
    db.add(db_customer)
    await db.commit()
    await db.refresh(db_customer)
    return db_customer

async def get_master_tags(db: AsyncSession) -> List[MasterTag]:
    query = select(MasterTag).join(MasterTag.group).options(selectinload(MasterTag.group)).order_by(MasterTagGroup.name, MasterTag.name)
    result = await db.execute(query)
    return result.scalars().all()

from app.schemas.table_booking import EventBookingCreate

async def create_event_bookings(db: AsyncSession, booking_in: EventBookingCreate) -> List[Booking]:
    # Upsert Customer
    cust_query = select(Customer).where(
        Customer.name == booking_in.customer_name,
        Customer.phone == booking_in.phone
    )
    cust_result = await db.execute(cust_query)
    db_customer = cust_result.scalars().first()
    if not db_customer:
        db_customer = Customer(
            name=booking_in.customer_name,
            phone=booking_in.phone,
            age=booking_in.age,
            gender=booking_in.gender,
            nat=booking_in.nat,
        )
        db.add(db_customer)
        await db.flush()
    else:
        if booking_in.age is not None and db_customer.age is None:
            db_customer.age = booking_in.age
            db.add(db_customer)
        if booking_in.gender is not None and db_customer.gender is None:
            db_customer.gender = booking_in.gender
            db.add(db_customer)
        if booking_in.nat is not None:
            db_customer.nat = booking_in.nat
            db.add(db_customer)
            
    # Pre-fetch Tags
    db_tags = []
    if booking_in.tag_ids:
        tag_query = select(MasterTag).where(MasterTag.id.in_(booking_in.tag_ids))
        tag_result = await db.execute(tag_query)
        db_tags = tag_result.scalars().all()

    bookings = []
    now = get_now()
    
    for table_id in booking_in.table_ids:
        table_query = select(Table).where(Table.id == table_id)
        table_result = await db.execute(table_query)
        db_table = table_result.scalar_one_or_none()
        
        if not db_table:
            continue

        # Overlap Check for each table in the event
        overlap_query = select(Booking).where(
            Booking.table_id == table_id,
            Booking.status.notin_([BookingStatus.CANCELLED, BookingStatus.HOLD, BookingStatus.COMPLETED]),
            Booking.start_time < booking_in.end_time,
            Booking.end_time > booking_in.start_time,
            Booking.end_time > now
        )
        overlap_result = await db.execute(overlap_query)
        if overlap_result.unique().scalars().first():
            continue # Skip this specific table if busy, or handle as error
        # Cancel ANY other HOLD bookings for this table to avoid lingering HOLDS
        all_holds_query = select(Booking).where(Booking.table_id == table_id, Booking.status == BookingStatus.HOLD)
        all_holds_result = await db.execute(all_holds_query)
        all_holds = all_holds_result.unique().scalars().all()
        
        db_booking = None
        for hold_b in all_holds:
            if hold_b.customer_id == db_customer.id and db_booking is None:
                db_booking = hold_b  # Reuse this one
            else:
                hold_b.status = BookingStatus.CANCELLED
                hold_b.cancel_reason = "Overwritten by event booking"
                db.add(hold_b)

        if db_booking:
            # Update existing hold to pending
            db_booking.pax = booking_in.pax
            db_booking.start_time = booking_in.start_time
            db_booking.end_time = booking_in.end_time
            db_booking.status = BookingStatus.PENDING
            db_booking.notes = f"[{booking_in.area_name or 'EVENT'}] {booking_in.notes or ''}"
            db_booking.tags = db_tags
        else:
            # Create new
            db_booking = Booking(
                table_id=table_id,
                customer_id=db_customer.id,
                pax=booking_in.pax,
                start_time=booking_in.start_time,
                end_time=booking_in.end_time,
                status=BookingStatus.PENDING,
                notes=f"[{booking_in.area_name or 'EVENT'}] {booking_in.notes or ''}",
                tags=db_tags,
            )
        
        if not db_booking:
            continue

        db.add(db_booking)
        
        db_table.status = TableStatus.BOOKED
        db_table.hold_until = None
        db_table.hold_by_customer_id = None
        db.add(db_table)
        
        bookings.append(db_booking)

    await db.flush()
    booking_ids = [b.id for b in bookings]
    await db.commit()
    
    stmt = select(Booking).options(
        selectinload(Booking.customer),
        selectinload(Booking.tags).selectinload(MasterTag.group)
    ).where(Booking.id.in_(booking_ids))
    result = await db.execute(stmt)
    return list(result.unique().scalars().all())

async def update_booking(db: AsyncSession, booking_id: int, booking_in: BookingUpdate) -> Optional[Booking]:
    db_booking = await get_booking_by_id(db, booking_id)
    if not db_booking:
        return None
    
    update_data = booking_in.model_dump(exclude_unset=True)
    
    # Handle direct booking fields
    for field in ["pax", "start_time", "end_time", "notes", "status", "billed_at", "billed_price", "cancel_reason"]:
        if field in update_data:
            setattr(db_booking, field, update_data[field])
            
    # Handle tags
    if "tag_ids" in update_data and update_data["tag_ids"] is not None:
        tag_query = select(MasterTag).where(MasterTag.id.in_(update_data["tag_ids"]))
        tag_result = await db.execute(tag_query)
        db_booking.tags = tag_result.scalars().all()
        
    # Handle customer updates
    if db_booking.customer_id:
        cust_query = select(Customer).where(Customer.id == db_booking.customer_id)
        cust_result = await db.execute(cust_query)
        db_customer = cust_result.scalar_one_or_none()
        if db_customer:
            if "customer_name" in update_data:
                db_customer.name = update_data["customer_name"]
            if "customer_phone" in update_data:
                db_customer.phone = update_data["customer_phone"]
            if "customer_age" in update_data:
                db_customer.age = update_data["customer_age"]
            if "customer_gender" in update_data:
                db_customer.gender = update_data["customer_gender"]
            if "customer_nat" in update_data:
                db_customer.nat = update_data["customer_nat"]
            db.add(db_customer)
            
    await db.commit()
    return await get_booking_by_id(db, booking_id)

