"""
database.py – Cấu hình kết nối PostgreSQL (async) cho Flower Note 🌸
=====================================================================
Dùng SQLAlchemy 2.x với asyncpg driver.
"""

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Đọc .env
load_dotenv()

DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:123456@localhost:5432/flowernote",
)

# Engine async – echo=False để tắt SQL log trong production
engine = create_async_engine(DATABASE_URL, echo=False, future=True)

# Session factory
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    """Base class cho tất cả SQLAlchemy models."""
    pass


async def init_db() -> None:
    """Tạo tất cả bảng nếu chưa tồn tại (CREATE TABLE IF NOT EXISTS)."""
    # Import ở đây để tránh circular import
    from db_models import Plant, RecognitionHistory  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # 🛠️ Tự động cập nhật Schema (Migration)
        # Thêm các cột mới nếu bảng đã tồn tại từ phiên bản cũ
        try:
            from sqlalchemy import text
            await conn.execute(text("ALTER TABLE recognition_history ADD COLUMN IF NOT EXISTS all_detections JSON"))
            await conn.execute(text("ALTER TABLE recognition_history ADD COLUMN IF NOT EXISTS image_base64 TEXT"))
            # Không thực hiện ALTER cho các bảng phụ (banana/papaya) ở đây
        except Exception:
            pass # Bỏ qua nếu có lỗi (ví dụ: đang dùng SQLite hoặc cột đã có)


@asynccontextmanager
async def get_db():
    """Dependency / context manager để lấy AsyncSession."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
