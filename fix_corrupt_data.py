"""
Script untuk memperbaiki data Booking/Table yang korup (meja hilang).
Error ini terjadi karena sisa-sisa percobaan error Event Booking tadi
yang mana tersimpan ke database namun tidak memenuhi syarat schema 
(contoh: customer_id null atau relasi kosong) sehingga menyebabkan
API gagal mengirim data ke Flutter.

Jalankan script ini di lokal (dan jika perlu di VPS):
  python3 fix_corrupt_data.py
"""
import asyncio
from app.db.session import SessionLocal
from app.models.table_booking import Booking, Table, TableStatus
from sqlalchemy import select, text
import sys

async def fix_missing_tables():
    print("=== Mencari data korup yang menyebabkan meja hilang ===")
    async with SessionLocal() as db:
        # 1. Cari booking yang customer_id-nya null / tidak ada di tabel customers
        result = await db.execute(text("""
            SELECT b.id, b.table_id
            FROM bookings b
            LEFT JOIN customers c ON b.customer_id = c.id
            WHERE c.id IS NULL OR b.customer_id IS NULL
        """))
        corrupt_bookings = result.fetchall()
        
        if corrupt_bookings:
            print(f"Ditemukan {len(corrupt_bookings)} booking korup/tanpa customer.")
            for row in corrupt_bookings:
                booking_id = row[0]
                table_id = row[1]
                print(f"  - Menghapus Booking ID: {booking_id} memulihkan Meja ID: {table_id}")
                
                # Hapus booking yang korup
                await db.execute(text(f"DELETE FROM bookings WHERE id = {booking_id}"))
                
                # Kembalikan meja ke statu AVAILABLE
                if table_id:
                    await db.execute(text(f"UPDATE tables SET status = 'available' WHERE id = {table_id}"))
            
            await db.commit()
            print("✅ Booking korup berhasil dibersihkan.")
        else:
            print("Tidak ditemukan booking tanpa customer.")

        # 2. Cek meja yang mungkin statusnya tidak dikenal oleh Flutter
        result2 = await db.execute(text("""
            SELECT id, code, status FROM tables
            WHERE status NOT IN ('available', 'booked', 'occupied', 'billed', 'out_of_service')
            OR status IS NULL
        """))
        corrupt_tables = result2.fetchall()
        
        if corrupt_tables:
            print(f"Ditemukan {len(corrupt_tables)} meja dengan status salah.")
            for row in corrupt_tables:
                print(f"  - Reset status meja {row[1]} (id={row[0]}) ke 'available'")
                await db.execute(text(f"UPDATE tables SET status = 'available' WHERE id = {row[0]}"))
            
            await db.commit()
            print("✅ Status meja berhasil direset.")
        else:
            print("Tidak ditemukan meja dengan status salah.")
            
        print("\nSelesai! Silakan Reload aplikasi Flutter Anda.")

if __name__ == "__main__":
    asyncio.run(fix_missing_tables())
