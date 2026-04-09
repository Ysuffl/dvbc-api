from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, with_loader_criteria
from sqlalchemy import update, delete
from app.models.table_booking import Table, TableStatus, Booking, BookingStatus, Customer, MasterTag
from datetime import datetime, timedelta
from app.schemas.table_booking import TableCreate, TableUpdate
from typing import List, Optional

async def get_tables(db: AsyncSession, skip: int = 0, limit: int = 1000) -> List[Table]:
    query = select(Table).options(
        selectinload(Table.bookings).selectinload(Booking.customer),
        selectinload(Table.bookings).selectinload(Booking.tags).selectinload(MasterTag.group),
        selectinload(Table.hold_customer),
        with_loader_criteria(Booking, Booking.status.in_([
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
            BookingStatus.ARRIVED,
            BookingStatus.HOLD
        ]))
    ).order_by(Table.id).offset(skip).limit(limit)
    result = await db.execute(query)
    tables = list(result.scalars().all())
    
    now = datetime.now()
    updated = False
    for table in tables:
        if table.status == TableStatus.HOLD and table.hold_until and table.hold_until < now:
            table.status = TableStatus.AVAILABLE
            table.hold_until = None
            table.hold_by_customer_id = None
            db.add(table)
            updated = True
    
    if updated:
        await db.commit()
        result = await db.execute(query)
        tables = list(result.scalars().all())
    
    return tables

async def get_table_by_id(db: AsyncSession, table_id: int) -> Optional[Table]:
    query = select(Table).options(
        selectinload(Table.bookings).selectinload(Booking.customer),
        selectinload(Table.bookings).selectinload(Booking.tags).selectinload(MasterTag.group),
        selectinload(Table.hold_customer),
        with_loader_criteria(Booking, Booking.status.in_([
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
            BookingStatus.ARRIVED,
            BookingStatus.HOLD
        ]))
    ).where(Table.id == table_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_table(db: AsyncSession, table_in: TableCreate) -> Table:
    db_table = Table(**table_in.model_dump())
    db.add(db_table)
    table_id = db_table.id
    await db.commit()
    return await get_table_by_id(db, table_id)

async def update_table(db: AsyncSession, table_id: int, table_in: TableUpdate) -> Optional[Table]:
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        return None
    
    update_data = table_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_table, key, value)
    
    db.add(db_table)
    await db.commit()
    return await get_table_by_id(db, table_id)

async def delete_table(db: AsyncSession, table_id: int) -> bool:
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        return False
    db.delete(db_table)
    await db.commit()
    return True

async def hold_table(db: AsyncSession, table_id: int, customer_name: str, phone: Optional[str] = None, hold_until: Optional[datetime] = None) -> Optional[Table]:
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        return None
        
    # Upsert Customer for the hold
    cust_query = select(Customer).where(Customer.name == customer_name, Customer.phone == phone)
    cust_result = await db.execute(cust_query)
    db_customer = cust_result.scalars().first()
    if not db_customer:
        db_customer = Customer(name=customer_name, phone=phone)
        db.add(db_customer)
        await db.flush()
        
    db_table.status = TableStatus.HOLD
    db_table.hold_until = hold_until or (datetime.now() + timedelta(minutes=10))
    db_table.hold_by_customer_id = db_customer.id
    db.add(db_table)

    # Create a Hold Booking record for accountability/reports
    new_hold_booking = Booking(
        table_id=table_id,
        customer_id=db_customer.id,
        pax=0,
        start_time=datetime.now(),
        end_time=db_table.hold_until,
        status=BookingStatus.HOLD,
        notes=f"Table hold for customer: {customer_name}"
    )
    db.add(new_hold_booking)
    
    await db.commit()
    return await get_table_by_id(db, table_id)
