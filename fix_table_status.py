"""
Script untuk memperbaiki status tabel yang ada di database.
Tabel yang punya booking aktif (pending/confirmed/arrived) akan diubah ke 'booked'.

Jalankan sekali di VPS:
  python3 fix_table_status.py
"""
import asyncio
import sys
from app.db.session import SessionLocal
from app.models.table_booking import Table, Booking, TableStatus, BookingStatus
from app.services.websocket_manager import manager
from app.schemas.table_booking import TableResponse
from sqlalchemy import select, text

async def fix_table_statuses():
    print("=== Fix Table Status Script ===")
    async with SessionLocal() as db:
        # Cari semua tabel yang masih 'available' tapi punya booking aktif
        result = await db.execute(text("""
            SELECT DISTINCT t.id, t.code, t.status
            FROM tables t
            JOIN bookings b ON t.id = b.table_id
            WHERE b.status IN ('pending', 'confirmed', 'arrived')
            AND t.status = 'available'
        """))
        rows = result.fetchall()
        
        print(f"Ditemukan {len(rows)} tabel yang perlu diperbaiki:")
        for row in rows:
            print(f"  - Tabel {row[1]} (id={row[0]}): status={row[2]} -> akan diubah ke 'booked'")
        
        if not rows:
            print("Tidak ada tabel yang perlu diperbaiki. Semua sudah benar!")
            return
        
        # Update status semua tabel yang bermasalah
        await db.execute(text("""
            UPDATE tables 
            SET status = 'booked'
            WHERE id IN (
                SELECT DISTINCT t.id FROM tables t
                JOIN bookings b ON t.id = b.table_id
                WHERE b.status IN ('pending', 'confirmed', 'arrived')
                AND t.status = 'available'
            )
        """))
        await db.commit()
        print(f"\n✅ Berhasil memperbaiki {len(rows)} tabel!")
        print("Silakan restart Flutter app atau tunggu WebSocket update.")

if __name__ == "__main__":
    asyncio.run(fix_table_statuses())
