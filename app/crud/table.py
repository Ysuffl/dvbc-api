from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy import update, delete
from app.models.table_booking import Table, TableStatus, Booking
from app.schemas.table_booking import TableCreate, TableUpdate
from typing import List, Optional

async def get_tables(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Table]:
    query = select(Table).options(
        selectinload(Table.bookings).selectinload(Booking.customer)
    ).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

async def get_table_by_id(db: AsyncSession, table_id: int) -> Optional[Table]:
    query = select(Table).options(
        selectinload(Table.bookings).selectinload(Booking.customer)
    ).where(Table.id == table_id)
    result = await db.execute(query)
    return result.scalar_one_or_none()

async def create_table(db: AsyncSession, table_in: TableCreate) -> Table:
    db_table = Table(**table_in.model_dump())
    db.add(db_table)
    await db.flush()
    await db.refresh(db_table)
    return db_table

async def update_table(db: AsyncSession, table_id: int, table_in: TableUpdate) -> Optional[Table]:
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        return None
    
    update_data = table_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_table, key, value)
    
    db.add(db_table)
    await db.flush()
    await db.refresh(db_table)
    return db_table

async def delete_table(db: AsyncSession, table_id: int) -> bool:
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        return False
    await db.delete(db_table)
    await db.flush()
    return True
