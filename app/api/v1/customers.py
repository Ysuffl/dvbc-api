from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.db.session import get_db
from app.crud.booking import get_customers, create_customer
from app.schemas.table_booking import CustomerResponse, CustomerCreate

router = APIRouter()

@router.get("/", response_model=List[CustomerResponse])
async def list_customers(db: AsyncSession = Depends(get_db)):
    return await get_customers(db)

@router.post("/", response_model=CustomerResponse)
async def add_customer(customer_in: CustomerCreate, db: AsyncSession = Depends(get_db)):
    from app.services.websocket_manager import manager
    db_customer = await create_customer(db, customer_in)
    
    # Notify all clients about new customer
    if db_customer:
        await manager.broadcast({
            "type": "customer_update",
            "data": CustomerResponse.model_validate(db_customer).model_dump(mode="json")
        })
        
    return db_customer
