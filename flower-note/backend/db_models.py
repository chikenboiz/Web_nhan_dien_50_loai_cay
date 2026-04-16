"""
db_models.py – Định nghĩa bảng SQLAlchemy cho Flower Note 🌸
=============================================================
Bảng:
    - plants              : Thông tin tĩnh về 50 loài cây
    - recognition_history : Lịch sử nhận diện của người dùng
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, Float, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# ─────────────────────────────── Bảng plants ────────────────────────────────
class Plant(Base):
    """Thông tin chi tiết về từng loài cây."""

    __tablename__ = "plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Tên tra cứu (khớp với nhãn YOLOv8)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)

    # Thông tin khoa học
    scientific_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Nội dung hiển thị
    description:     Mapped[str | None] = mapped_column(Text, nullable=True)
    characteristics: Mapped[str | None] = mapped_column(Text, nullable=True)
    uses:            Mapped[str | None] = mapped_column(Text, nullable=True)
    care:            Mapped[str | None] = mapped_column(Text, nullable=True)
    warning:         Mapped[str | None] = mapped_column(Text, nullable=True)   # NULL = an toàn


# ─────────────────────── Bảng recognition_history ───────────────────────────
class RecognitionHistory(Base):
    """Lịch sử mỗi lần người dùng nhận diện ảnh."""

    __tablename__ = "recognition_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    plant_name:      Mapped[str]   = mapped_column(String(200), nullable=False)
    scientific_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    confidence:      Mapped[float] = mapped_column(Float, nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox:            Mapped[list | None] = mapped_column(JSON,  nullable=True)   # [x1,y1,x2,y2]
    all_detections:  Mapped[list | None] = mapped_column(JSON,  nullable=True)
    image_base64:    Mapped[str | None]  = mapped_column(Text,  nullable=True)

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
