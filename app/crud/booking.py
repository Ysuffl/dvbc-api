from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from sqlalchemy.orm import selectinload
from app.models.table_booking import Booking, Table, TableStatus, BookingStatus, Customer, compute_master_level_id, MasterTag
from app.schemas.table_booking import BookingCreate, BookingUpdate, EventBookingCreate
from typing import List, Optional
from datetime import datetime

async def get_bookings(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Booking]:
    query = select(Booking).options(selectinload(Booking.tags)).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.unique().scalars().all()

async def create_booking(db: AsyncSession, booking_in: BookingCreate) -> Optional[Booking]:
    # Check if table exists
    table_query = select(Table).where(Table.id == booking_in.table_id)
    table_result = await db.execute(table_query)
    db_table = table_result.scalar_one_or_none()
    
    if not db_table:
        return None

    # Check for overlapping bookings
    overlap_query = select(Booking).where(
        Booking.table_id == booking_in.table_id,
        Booking.status.notin_([BookingStatus.CANCELLED, BookingStatus.HOLD]),
        Booking.start_time < booking_in.end_time,
        Booking.end_time > booking_in.start_time
    )
    overlap_result = await db.execute(overlap_query)
    if overlap_result.unique().scalars().first():
        return None

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
        )
        db.add(db_customer)
        await db.flush()
    else:
        # Update age if provided and not yet set
        if booking_in.age is not None and db_customer.age is None:
            db_customer.age = booking_in.age
            db.add(db_customer)
        if booking_in.gender is not None and db_customer.gender is None:
            db_customer.gender = booking_in.gender
            db.add(db_customer)

    # Cancel ANY other HOLD bookings for this table to avoid lingering HOLDS
    all_holds_query = select(Booking).where(Booking.table_id == booking_in.table_id, Booking.status == BookingStatus.HOLD)
    all_holds_result = await db.execute(all_holds_query)
    all_holds = all_holds_result.unique().scalars().all()
    
    db_booking = None
    for hold_b in all_holds:
        if hold_b.customer_id == db_customer.id and db_booking is None:
            db_booking = hold_b  # Reuse this one
        else:
            hold_b.status = BookingStatus.CANCELLED
            hold_b.cancel_reason = "Overwritten by new booking"
            db.add(hold_b)

    if db_booking:
        # Update existing hold to pending
        db_booking.pax = booking_in.pax
        db_booking.start_time = booking_in.start_time
        db_booking.end_time = booking_in.end_time
        db_booking.status = BookingStatus.PENDING
        db_booking.category = booking_in.customer_category
        db_booking.notes = booking_in.notes
    else:
        # Create new
        db_booking = Booking(
            table_id=booking_in.table_id,
            customer_id=db_customer.id,
            pax=booking_in.pax,
            start_time=booking_in.start_time,
            end_time=booking_in.end_time,
            status=BookingStatus.PENDING,
            category=booking_in.customer_category,
            notes=booking_in.notes,
        )
    
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
    await db.commit()
    await db.refresh(db_booking)
    if db_table:
        await db.refresh(db_table)
    return db_booking

async def get_booking_by_id(db: AsyncSession, booking_id: int) -> Optional[Booking]:
    query = select(Booking).where(Booking.id == booking_id)
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
            # Update total_spending dan level saat billed
            if is_billed and billed_price is not None:
                db_customer.total_spending = (db_customer.total_spending or 0.0) + billed_price
                db_customer.master_level_id = compute_master_level_id(db_customer.total_spending)
            
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
        await db.commit()
        await db.refresh(db_booking)
        return db_booking
    
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

    await db.commit()
    await db.refresh(db_booking)
    return db_booking

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
    )
    db.add(db_customer)
    await db.commit()
    await db.refresh(db_customer)
    return db_customer

async def get_master_tags(db: AsyncSession) -> List[MasterTag]:
    result = await db.execute(select(MasterTag).order_by(MasterTag.group_name, MasterTag.name))
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
            
    # Pre-fetch Tags
    db_tags = []
    if booking_in.tag_ids:
        tag_query = select(MasterTag).where(MasterTag.id.in_(booking_in.tag_ids))
        tag_result = await db.execute(tag_query)
        db_tags = tag_result.scalars().all()

    bookings = []
    now = datetime.now()
    
    for table_id in booking_in.table_ids:
        table_query = select(Table).where(Table.id == table_id)
        table_result = await db.execute(table_query)
        db_table = table_result.scalar_one_or_none()
        
        if not db_table:
            continue

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
            db_booking.category = booking_in.customer_category
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
                category=booking_in.customer_category,
                notes=f"[{booking_in.area_name or 'EVENT'}] {booking_in.notes or ''}",
                # Tags are shared/copied to all bookings in the event
                tags=db_tags,
            )
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
        selectinload(Booking.tags)
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
            if "customer_category" in update_data:
                db_booking.category = update_data["customer_category"]
            if "customer_age" in update_data:
                db_customer.age = update_data["customer_age"]
            if "customer_gender" in update_data:
                db_customer.gender = update_data["customer_gender"]
            db.add(db_customer)
            
    db.add(db_booking)
    await db.commit()
    await db.refresh(db_booking)
    
    # Re-fetch with joined relations
    stmt = select(Booking).options(
        selectinload(Booking.customer),
        selectinload(Booking.tags)
    ).where(Booking.id == booking_id)
    result = await db.execute(stmt)
    return result.unique().scalar_one_or_none()

