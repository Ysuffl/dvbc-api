from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Union
from app.db.session import get_db
from app.crud.booking import (
    get_bookings, create_booking, get_booking_by_id, 
    update_booking_status, create_event_bookings, get_master_tags,
    update_booking
)
from app.crud.table import get_table_by_id
from app.schemas.table_booking import (
    BookingCreate, BookingUpdate, BookingResponse, TableResponse, 
    EventBookingCreate, BookingStatus, TagResponse
)
from app.services.websocket_manager import manager

router = APIRouter()

@router.post("/event", response_model=List[BookingResponse])
async def create_event_booking_route(booking_in: EventBookingCreate, db: AsyncSession = Depends(get_db)):
    db_bookings = await create_event_bookings(db, booking_in)
    
    # Notify all clients about multiple table updates
    for db_booking in db_bookings:
        db_table = await get_table_by_id(db, db_booking.table_id)
        if db_table:
            await manager.broadcast({
                "type": "table_update",
                "data": TableResponse.model_validate(db_table).model_dump(mode="json")
            })
    
    return db_bookings

@router.get("/", response_model=List[BookingResponse])
async def list_bookings(db: AsyncSession = Depends(get_db)):
    return await get_bookings(db)

@router.get("/tags", response_model=List[TagResponse])
async def list_tags(db: AsyncSession = Depends(get_db)):
    return await get_master_tags(db)

@router.post("/", response_model=BookingResponse)
async def create_new_booking(booking_in: BookingCreate, db: AsyncSession = Depends(get_db)):
    try:
        db_booking = await create_booking(db, booking_in)
        if not db_booking:
            raise HTTPException(status_code=404, detail="Table not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Notify all clients about table status change
    db_table = await get_table_by_id(db, db_booking.table_id)
    if db_table:
        await manager.broadcast({
            "type": "table_update",
            "data": TableResponse.model_validate(db_table).model_dump(mode="json")
        })
    
    return db_booking

@router.get("/{booking_id}", response_model=BookingResponse)
async def read_booking(booking_id: int, db: AsyncSession = Depends(get_db)):
    db_booking = await get_booking_by_id(db, booking_id)
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    return db_booking

@router.patch("/{booking_id}/status")
async def update_booking_status_route(booking_id: int, booking_update: BookingUpdate, db: AsyncSession = Depends(get_db)):
    # Get current booking to know the table_id (in case it gets deleted)
    db_booking_initial = await get_booking_by_id(db, booking_id)
    if not db_booking_initial:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    table_id = db_booking_initial.table_id
    
    # Perform status update (and potential deletion)
    db_booking = await update_booking_status(db, booking_id, booking_update.status, booking_update.cancel_reason, booking_update.billed_price)
    
    # Handle the table status broadcast even if booking is gone
    db_table = await get_table_by_id(db, table_id)
    if db_table:
        await manager.broadcast({
            "type": "table_update",
            "data": TableResponse.model_validate(db_table).model_dump(mode="json")
        })
    
    if not db_booking:
        # If status was COMPLETED/CANCELLED, the record is gone
        if booking_update.status in [BookingStatus.COMPLETED, BookingStatus.CANCELLED]:
            return {"status": "success", "message": f"Booking {booking_id} has been processed and archived."}
        raise HTTPException(status_code=404, detail="Booking record not found after update")
    
    
    return BookingResponse.model_validate(db_booking)

@router.patch("/{booking_id}", response_model=BookingResponse)
async def patch_booking(booking_id: int, booking_in: BookingUpdate, db: AsyncSession = Depends(get_db)):
    db_booking = await update_booking(db, booking_id, booking_in)
    if not db_booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Notify all clients about possible table/booking update
    db_table = await get_table_by_id(db, db_booking.table_id)
    if db_table:
        await manager.broadcast({
            "type": "table_update",
            "data": TableResponse.model_validate(db_table).model_dump(mode="json")
        })
        
    return db_booking

