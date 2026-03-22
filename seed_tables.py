import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.table_booking import Table, TableStatus, Booking
from app.db.base import Base
import sqlalchemy as sa
import random
import math

def generate_floor_data(floor_name):
    tables = []
    
    if floor_name == "VIP_OTIC":
        # Original hardcoded VIP OTIC data from image mapping
        otic_tables = [
            {"code": "09", "x": 150, "y": 200, "shape": "rectangle"},
            {"code": "010", "x": 260, "y": 200, "shape": "rectangle"},
            {"code": "011", "x": 370, "y": 200, "shape": "rectangle"},
            {"code": "08", "x": 260, "y": 350, "shape": "rectangle"},
            {"code": "06", "x": 150, "y": 400, "shape": "rectangle"},
            {"code": "07", "x": 260, "y": 480, "shape": "rectangle"},
            {"code": "05", "x": 150, "y": 530, "shape": "rectangle"},
            {"code": "R5", "x": 450, "y": 480, "shape": "rectangle"},
            {"code": "R6", "x": 750, "y": 480, "shape": "rectangle"},
            {"code": "R7", "x": 860, "y": 480, "shape": "rectangle"},
            {"code": "R4", "x": 500, "y": 590, "shape": "rectangle"},
            {"code": "R3", "x": 610, "y": 590, "shape": "rectangle"},
            {"code": "R2", "x": 750, "y": 590, "shape": "rectangle"},
            {"code": "R1", "x": 860, "y": 590, "shape": "rectangle"},
            {"code": "M1", "x": 1020, "y": 200, "shape": "rectangle"},
            {"code": "M2", "x": 1020, "y": 300, "shape": "rectangle"},
            {"code": "M3", "x": 1020, "y": 400, "shape": "rectangle"},
            {"code": "M4", "x": 1020, "y": 500, "shape": "rectangle"},
            {"code": "M5", "x": 1020, "y": 600, "shape": "rectangle"},
            {"code": "01", "x": 1150, "y": 450, "shape": "rectangle"},
            {"code": "02", "x": 1260, "y": 450, "shape": "rectangle"},
            {"code": "03", "x": 1350, "y": 360, "shape": "circle"},
            {"code": "04", "x": 1330, "y": 550, "shape": "rectangle"},
        ]
        return otic_tables

    elif floor_name == "Grand Ballroom": # Massive Grid 6x10
        for r in range(1, 7):
            for c in range(1, 11):
                tables.append({"code": f"B{r}{c:02d}", "x": 180 * c, "y": 150 * r, "shape": "rectangle"})
    
    elif floor_name == "VIP Penthouse": # Large VIP / Sofas
        for i in range(1, 6):
            tables.append({"code": f"V-{i}", "x": 350 * i, "y": 250, "shape": "vip"})
            tables.append({"code": f"L-{i}", "x": 350 * i, "y": 550, "shape": "sofa"})

    elif floor_name == "Sunset Rooftop": # Circular / Star layout
        radius = 400
        center_x, center_y = 960, 540
        for i in range(6):
            angle = (i / 6) * 2 * math.pi
            tables.append({"code": f"R-IN{i+1}", "x": center_x + radius * 0.5 * math.cos(angle), "y": center_y + radius * 0.5 * math.sin(angle), "shape": "circle"})
        for i in range(12):
            angle = (i / 12) * 2 * math.pi
            tables.append({"code": f"R-OUT{i+1}", "x": center_x + radius * math.cos(angle), "y": center_y + radius * math.sin(angle), "shape": "circle"})
    
    elif floor_name == "Garden Terrace": # Organic moon shapes
        for i in range(1, 13):
            tables.append({"code": f"G-{i}", "x": random.randint(200, 1600), "y": random.randint(200, 800), "shape": "moon"})

    elif floor_name == "Private Chambers": # Symmetrical isolated pods
        for i in range(1, 9):
            row = (i-1) // 4
            col = (i-1) % 4
            tables.append({"code": f"P-{i}", "x": 400 * col + 300, "y": 400 * row + 300, "shape": "rectangle"})
            
    return tables

async def seed_tables():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    floors = ["VIP_OTIC", "Grand Ballroom", "VIP Penthouse", "Sunset Rooftop", "Garden Terrace", "Private Chambers"]

    async with async_session() as session:
        # Clear existing data
        await session.execute(sa.delete(Booking))
        await session.execute(sa.delete(Table))
        
        for floor in floors:
            floor_tables = generate_floor_data(floor)
            for td in floor_tables:
                table = Table(
                    code=td["code"],
                    x_pos=td["x"],
                    y_pos=td["y"],
                    shape=td["shape"],
                    status=TableStatus.AVAILABLE,
                    area_id=floor
                )
                session.add(table)
        
        await session.commit()
    
    print("Database seeding completed for DreamVille Luxury Floors + VIP_OTIC!")

if __name__ == "__main__":
    asyncio.run(seed_tables())
