from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete
from sqlalchemy.orm import selectinload
from app.models.table_booking import Booking, Table, TableStatus, BookingStatus, Customer, compute_master_level
from app.schemas.table_booking import BookingCreate, BookingUpdate
from typing import List, Optional
from datetime import datetime

async def get_bookings(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Booking]:
    query = select(Booking).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

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
        Booking.status != BookingStatus.CANCELLED,
        Booking.start_time < booking_in.end_time,
        Booking.end_time > booking_in.start_time
    )
    overlap_result = await db.execute(overlap_query)
    if overlap_result.scalars().first():
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
            category=booking_in.customer_category,
            age=booking_in.age,
        )
        db.add(db_customer)
        await db.flush()
    else:
        # Update age if provided and not yet set
        if booking_in.age is not None and db_customer.age is None:
            db_customer.age = booking_in.age
            db.add(db_customer)

    db_booking = Booking(
        table_id=booking_in.table_id,
        customer_id=db_customer.id,
        pax=booking_in.pax,
        start_time=booking_in.start_time,
        end_time=booking_in.end_time,
        status=BookingStatus.PENDING,
        notes=booking_in.notes,
    )
    db.add(db_booking)
    
    db_table.status = TableStatus.BOOKED
    db.add(db_table)
    
    await db.commit()
    await db.refresh(db_booking)
    if db_table:
        await db.refresh(db_table)
    return db_booking

async def get_booking_by_id(db: AsyncSession, booking_id: int) -> Optional[Booking]:
    query = select(Booking).where(Booking.id == booking_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def update_booking_status(db: AsyncSession, booking_id: int, status: BookingStatus, cancel_reason: Optional[str] = None, billed_price: Optional[float] = None) -> Optional[Booking]:
    db_booking = await get_booking_by_id(db, booking_id)
    if not db_booking:
        return None
    
    db_booking.status = status
    if cancel_reason is not None:
        db_booking.cancel_reason = cancel_reason
    
    if status == BookingStatus.BILLED:
        now = datetime.now()
        db_booking.billed_at = now
        if billed_price is not None:
            db_booking.billed_price = billed_price
        
        # Update Customer total_spending + master_level
        if billed_price and db_booking.customer_id:
            cust_query = select(Customer).where(Customer.id == db_booking.customer_id)
            cust_result = await db.execute(cust_query)
            db_customer = cust_result.scalar_one_or_none()
            if db_customer:
                db_customer.total_spending = (db_customer.total_spending or 0.0) + billed_price
                db_customer.master_level = compute_master_level(db_customer.total_spending)
                db_customer.last_status = status
                db_customer.last_visit = now
                db.add(db_customer)
    
    # Update Customer History (for non-billed statuses)
    cust_query = select(Customer).where(Customer.id == db_booking.customer_id)
    cust_result = await db.execute(cust_query)
    db_customer = cust_result.scalar_one_or_none()
    if db_customer:
        db_customer.last_status = status
        db_customer.last_visit = datetime.now()
        db.add(db_customer)

    table_query = select(Table).where(Table.id == db_booking.table_id)
    table_result = await db.execute(table_query)
    db_table = table_result.scalar_one_or_none()

    if status in [BookingStatus.CANCELLED, BookingStatus.COMPLETED]:
        if db_table:
            db_table.status = TableStatus.AVAILABLE
            db.add(db_table)
        db.add(db_booking)
        await db.commit()
        await db.refresh(db_booking)
        return db_booking
    
    elif status == BookingStatus.CONFIRMED:
        if db_table:
            db_table.status = TableStatus.BOOKED
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
    result = await db.execute(select(Customer).order_by(Customer.name))
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
            category=booking_in.customer_category,
            age=booking_in.age,
        )
        db.add(db_customer)
        await db.flush()
    else:
        if booking_in.age is not None and db_customer.age is None:
            db_customer.age = booking_in.age
            db.add(db_customer)

    bookings = []
    now = datetime.now()
    
    for table_id in booking_in.table_ids:
        table_query = select(Table).where(Table.id == table_id)
        table_result = await db.execute(table_query)
        db_table = table_result.scalar_one_or_none()
        
        if not db_table:
            continue

        db_booking = Booking(
            table_id=table_id,
            customer_id=db_customer.id,
            pax=booking_in.pax,
            start_time=booking_in.start_time,
            end_time=booking_in.end_time,
            status=BookingStatus.PENDING,
            notes=f"[{booking_in.area_name or 'EVENT'}] {booking_in.notes or ''}",
        )
        db.add(db_booking)
        
        db_table.status = TableStatus.BOOKED
        db.add(db_table)
        
        bookings.append(db_booking)

    await db.flush()
    booking_ids = [b.id for b in bookings]
    await db.commit()
    
    stmt = select(Booking).options(selectinload(Booking.customer)).where(Booking.id.in_(booking_ids))
    result = await db.execute(stmt)
    return list(result.scalars().all())
