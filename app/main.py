from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import tables, bookings, auth, customers
from app.core.config import settings
from app.services.websocket_manager import manager
from app.db.session import engine
from app.db.base import Base # This Base has all models imported
import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup: Create database tables (now managed by Laravel)
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown logic if any goes here

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API for DreamVille Table Reservation System",
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# CORS Middleware config
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health-check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include API Routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Auth"])
app.include_router(tables.router, prefix=f"{settings.API_V1_STR}/tables", tags=["Tables"])
app.include_router(bookings.router, prefix=f"{settings.API_V1_STR}/bookings", tags=["Bookings"])
app.include_router(customers.router, prefix=f"{settings.API_V1_STR}/customers", tags=["Customers"])

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Listening for messages if necessary (e.g., pong or updates from client)
            data = await websocket.receive_text()
            # Handle incoming data if needed
    except WebSocketDisconnect:
        manager.disconnect(websocket)
