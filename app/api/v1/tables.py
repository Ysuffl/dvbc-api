from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db, SessionLocal
from app.crud.table import get_tables, create_table, get_table_by_id, update_table, delete_table
from app.schemas.table_booking import TableCreate, TableUpdate, TableResponse
from app.models.table_booking import TableStatus, Booking, BookingStatus
from sqlalchemy import select
from app.services.websocket_manager import manager
import asyncio
from datetime import datetime

router = APIRouter()

# DEPRECATED reset task as logic moved to immediate AVAILABLE on billed
async def reset_table_status_task(table_id: int):
    pass

@router.get("/", response_model=List[TableResponse])
async def list_tables(db: AsyncSession = Depends(get_db)):
    return await get_tables(db)

@router.post("/", response_model=TableResponse)
async def create_new_table(table_in: TableCreate, db: AsyncSession = Depends(get_db)):
    db_table = await create_table(db, table_in)
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table

@router.get("/{table_id}", response_model=TableResponse)
async def read_table(table_id: int, db: AsyncSession = Depends(get_db)):
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    return db_table

@router.put("/{table_id}", response_model=TableResponse)
async def update_existing_table(table_id: int, table_in: TableUpdate, db: AsyncSession = Depends(get_db)):
    db_table = await update_table(db, table_id, table_in)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table

@router.delete("/{table_id}")
async def remove_table(table_id: int, db: AsyncSession = Depends(get_db)):
    success = await delete_table(db, table_id)
    if not success:
        raise HTTPException(status_code=404, detail="Table not found")
    
    await manager.broadcast({
        "type": "table_deleted",
        "data": {"id": table_id}
    })
    return {"status": "ok"}

@router.patch("/{table_id}/occupied", response_model=TableResponse)
async def mark_table_as_occupied(table_id: int, db: AsyncSession = Depends(get_db)):
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    db_table.status = TableStatus.OCCUPIED
    db.add(db_table)
    
    # Update active booking status
    now = datetime.now()
    find_booking_query = select(Booking).where(Booking.table_id == table_id, Booking.start_time <= now, Booking.end_time >= now, Booking.status != BookingStatus.CANCELLED)
    booking_result = await db.execute(find_booking_query)
    db_booking = booking_result.unique().scalar_one_or_none()
    if db_booking:
        db_booking.status = BookingStatus.ARRIVED
        db.add(db_booking)
    
    await db.commit()
    db_table = await get_table_by_id(db, table_id)
    
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table

@router.patch("/{table_id}/available", response_model=TableResponse)
async def mark_table_as_available(table_id: int, db: AsyncSession = Depends(get_db)):
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    db_table.status = TableStatus.AVAILABLE
    db_table.hold_until = None
    db_table.hold_by_customer_id = None
    db.add(db_table)
    
    # Update active or recently active booking status to completed
    now = datetime.now()
    find_booking_query = select(Booking).where(
        Booking.table_id == table_id, 
        Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.ARRIVED, BookingStatus.BILLED])
    )
    booking_result = await db.execute(find_booking_query)
    db_booking = booking_result.unique().scalar_one_or_none()
    if db_booking:
        db_booking.status = BookingStatus.COMPLETED
        db.add(db_booking)
        
    await db.commit()
    db_table = await get_table_by_id(db, table_id)
    
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table

from app.schemas.table_booking import TableCreate, TableUpdate, TableResponse, TableBilled

# ... (keep other parts)

@router.patch("/{table_id}/billed", response_model=TableResponse)
async def mark_table_as_billed(table_id: int, billed_in: TableBilled, db: AsyncSession = Depends(get_db)):
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Update active booking status
    find_booking_query = select(Booking).where(
        Booking.table_id == table_id, 
        Booking.status == BookingStatus.ARRIVED
    )
    booking_result = await db.execute(find_booking_query)
    db_booking = booking_result.unique().scalar_one_or_none()
    if db_booking:
        from app.crud.booking import update_booking_status
        await update_booking_status(db, db_booking.id, BookingStatus.BILLED, None, billed_in.billed_price)
    
    # Set table status to AVAILABLE immediately
    db_table.status = TableStatus.AVAILABLE
    db_table.hold_until = None
    db_table.hold_by_customer_id = None
    db.add(db_table)
    await db.commit()
    
    db_table = await get_table_by_id(db, table_id)
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table

from typing import Optional

@router.patch("/{table_id}/hold", response_model=TableResponse)
async def hold_table_route(table_id: int, customer_name: str, phone: Optional[str] = None, hold_until: Optional[datetime] = None, db: AsyncSession = Depends(get_db)):
    from app.crud.table import hold_table
    db_table = await hold_table(db, table_id, customer_name, phone, hold_until)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
        
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table
