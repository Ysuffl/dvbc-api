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

async def reset_table_status_task(table_id: int):
    """Fungsi ini berjalan di background, menunggu 5 menit sebelum reset table ke available"""
    await asyncio.sleep(5 * 60) # 5 menit
    async with SessionLocal() as db:
        db_table = await get_table_by_id(db, table_id)
        # Hanya reset jika statusnya masih BILLED
        if db_table and db_table.status == TableStatus.BILLED:
            db_table.status = TableStatus.AVAILABLE
            db.add(db_table)
            await db.commit()
            await db.refresh(db_table)
            
            # Broadcast the change
            await manager.broadcast({
                "type": "table_update",
                "data": TableResponse.model_validate(db_table).model_dump(mode="json")
            })

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
    db_booking = booking_result.scalar_one_or_none()
    if db_booking:
        db_booking.status = BookingStatus.CONFIRMED
        db.add(db_booking)
    
    await db.commit()
    await db.refresh(db_table)
    
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
    db.add(db_table)
    
    # Update active or recently active booking status to completed
    now = datetime.now()
    find_booking_query = select(Booking).where(Booking.table_id == table_id, Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.BILLED]))
    booking_result = await db.execute(find_booking_query)
    db_booking = booking_result.scalar_one_or_none()
    if db_booking:
        db_booking.status = BookingStatus.COMPLETED
        db.add(db_booking)
        
    await db.commit()
    await db.refresh(db_table)
    
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table

@router.patch("/{table_id}/billed", response_model=TableResponse)
async def mark_table_as_billed(table_id: int, background_tasks: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    db_table = await get_table_by_id(db, table_id)
    if not db_table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    # Update status to BILLED
    db_table.status = TableStatus.BILLED
    db.add(db_table)
    
    # Update active booking status to billed
    now = datetime.now()
    find_booking_query = select(Booking).where(Booking.table_id == table_id, Booking.start_time <= now, Booking.end_time >= now, Booking.status == BookingStatus.CONFIRMED)
    booking_result = await db.execute(find_booking_query)
    db_booking = booking_result.scalar_one_or_none()
    if db_booking:
        db_booking.status = BookingStatus.BILLED
        db.add(db_booking)
        
    await db.commit()
    await db.refresh(db_table)

    # Menjadwalkan reset setelah 5 menit
    background_tasks.add_task(reset_table_status_task, table_id)

    # Broadcast update
    await manager.broadcast({
        "type": "table_update",
        "data": TableResponse.model_validate(db_table).model_dump(mode="json")
    })
    return db_table
