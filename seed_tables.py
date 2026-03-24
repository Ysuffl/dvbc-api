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
    
    elif floor_name == "MOON AREA": # New requested layout (BS and D series)
        # Top Row: BS10 to BS1
        for i in range(1, 11):
            tables.append({"code": f"BS{11-i}", "x": 250 + (i * 100), "y": 150, "shape": "rectangle"})
        
        # Row D1 to D8
        for i in range(1, 9):
            tables.append({"code": f"D{i}", "x": 50 + (i * 80), "y": 320, "shape": "rectangle"})
            
        # Circle/Scattered D9 to D16
        scattered = [
            {"code": "D10", "x": 150, "y": 500, "shape": "rectangle"},
            {"code": "D11", "x": 300, "y": 500, "shape": "rectangle"},
            {"code": "D12", "x": 380, "y": 650, "shape": "rectangle"},
            {"code": "D13", "x": 300, "y": 800, "shape": "rectangle"},
            {"code": "D14", "x": 150, "y": 800, "shape": "rectangle"},
            {"code": "D15", "x": 30, "y": 800, "shape": "rectangle"},
            {"code": "D9", "x": 100, "y": 650, "shape": "rectangle"},
            {"code": "D16", "x": 30, "y": 650, "shape": "rectangle"},
        ]
        tables.extend(scattered)
        
        # Grid D20 to D30 (Right side)
        grid_x_start = 1000
        for r in range(4):
            cols = 3 if r < 3 else 2
            for c in range(cols):
                idx = 20 + (r * 3) + c
                if idx > 30: continue
                tables.append({"code": f"D{idx}", "x": grid_x_start + (c * 120), "y": 420 + (r * 150), "shape": "rectangle"})
    
    elif floor_name == "POOL AREA": # New requested layout (S and PB series)
        # S1 and S2
        tables.append({"code": "S1", "x": 100, "y": 100, "shape": "rectangle"})
        tables.append({"code": "S2", "x": 220, "y": 100, "shape": "rectangle"})
        
        # Row S3 to S7
        for i in range(3, 8):
            tables.append({"code": f"S{i}", "x": 100 + ((i-3) * 120), "y": 280, "shape": "rectangle"})
            
        # Row S14 to S8 (Reverse order shown in image)
        s8_row = ["S14", "S13", "S12", "S11", "S10", "S9", "S8"]
        for i, code in enumerate(s8_row):
            tables.append({"code": code, "x": 100 + (i * 80), "y": 450, "shape": "rectangle"})
            
        # Bottom Row S20 to S26
        for i in range(20, 27):
            tables.append({"code": f"S{i}", "x": 100 + ((i-20) * 80), "y": 580, "shape": "rectangle"})
            
        # PB Series (Right Side)
        for i in range(1, 5):
            tables.append({"code": f"PB{i}", "x": 750 + ((i-1) * 60), "y": 480, "shape": "rectangle"})
        for i in range(5, 9):
            tables.append({"code": f"PB{i}", "x": 750 + ((i-5) * 60), "y": 580, "shape": "rectangle"})
    
    elif floor_name == "CUP ARENA": # New requested layout (CB and W series)
        # Vertical Row CB9 to CB1 on the left
        for i in range(1, 10):
            tables.append({"code": f"CB{10-i}", "x": 120, "y": 100 + (i * 80), "shape": "rectangle"})
            
        # Diamond shape W1 to W4 in the center
        tables.append({"code": "W1", "x": 450, "y": 300, "shape": "rectangle"}) # Right
        tables.append({"code": "W2", "x": 415, "y": 400, "shape": "rectangle"}) # Bottom
        tables.append({"code": "W3", "x": 380, "y": 300, "shape": "rectangle"}) # Left
        tables.append({"code": "W4", "x": 415, "y": 200, "shape": "rectangle"}) # Top
            
    elif floor_name == "VIP CABANA & STAR":
        # Mapping from the provided floor plan image (Adjusted with more spacing)
        
        # VIP CABANA (VC Series - Top Row) - More spread out
        tables.append({"code": "VC1", "x": 200, "y": 80, "shape": "rectangle"})
        tables.append({"code": "VC2", "x": 650, "y": 80, "shape": "rectangle"})
        tables.append({"code": "VC3", "x": 1200, "y": 80, "shape": "rectangle"})
        tables.append({"code": "VC4", "x": 1650, "y": 80, "shape": "rectangle"})
        
        # STAR (P Series - Circles)
        # Left side
        tables.append({"code": "P10", "x": 50, "y": 250, "shape": "circle"})
        tables.append({"code": "P9", "x": 50, "y": 550, "shape": "circle"})
        # Bottom Left
        tables.append({"code": "P8", "x": 180, "y": 950, "shape": "circle"})
        tables.append({"code": "P7", "x": 350, "y": 950, "shape": "circle"})
        # Bottom Row (P6 to P1) - More spacing (200px)
        for i in range(1, 7):
            tables.append({"code": f"P{7-i}", "x": 400 + (i * 220), "y": 950, "shape": "circle"})
            
        # TG Series (Blue Boxes - Top Left) - More spacing (130px)
        for i in range(8, 13):
            tables.append({"code": f"TG{i}", "x": 100 + ((13-i) * 130), "y": 300, "shape": "rectangle"})
        for i in range(3, 7):
            tables.append({"code": f"TG{i}", "x": 100 + ((7-i) * 130), "y": 480, "shape": "rectangle"})
        tables.append({"code": "TG7", "x": 750, "y": 300, "shape": "rectangle"})
        tables.append({"code": "TG1", "x": 750, "y": 480, "shape": "rectangle"})
        tables.append({"code": "TG2", "x": 620, "y": 480, "shape": "rectangle"})
        
        # SB Series (Blue Columns - Middle) - More spacing
        for i in range(1, 9):
            row = (i-1) % 4
            col = 0 if i <= 4 else 1
            tables.append({"code": f"SB{i}", "x": 950 + (col * 150), "y": 150 + (row * 180), "shape": "rectangle"})
            
        # G Series (Red Boxes - Center)
        tables.append({"code": "G9", "x": 830, "y": 300, "shape": "rectangle"})
        tables.append({"code": "G8", "x": 830, "y": 480, "shape": "rectangle"})
        tables.append({"code": "G1", "x": 1250, "y": 380, "shape": "rectangle"})
        tables.append({"code": "G2", "x": 1250, "y": 580, "shape": "rectangle"})
        tables.append({"code": "G3", "x": 1250, "y": 780, "shape": "rectangle"})
        tables.append({"code": "G4", "x": 1050, "y": 780, "shape": "rectangle"})
        tables.append({"code": "G5", "x": 830, "y": 700, "shape": "rectangle"})
        tables.append({"code": "G6", "x": 620, "y": 700, "shape": "rectangle"})
        tables.append({"code": "G7", "x": 410, "y": 700, "shape": "rectangle"})
        
        # B Series (Red Grid - Right) - More spacing and shifted right to avoid P series overlap
        # Start B series at x=1900 instead of 1500
        for i in range(1, 11):
            row = (i-1) // 3
            col = (i-1) % 3
            if i == 10: # B10
                tables.append({"code": "B10", "x": 1900, "y": 320, "shape": "rectangle"})
            else:
                tables.append({"code": f"B{i}", "x": 1900 + (col * 220), "y": 320 + (row * 320), "shape": "rectangle"})
                
        # CB Series (Blue Column - Far Right) - Shifted further right (x=2700)
        for i in range(10, 14):
            tables.append({"code": f"CB{i}", "x": 2700, "y": 600 + ((13-i) * 180), "shape": "rectangle"})

    return tables

async def seed_tables():
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    floors = ["VIP_OTIC", "MOON AREA", "POOL AREA", "CUP ARENA", "VIP CABANA & STAR"]

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
