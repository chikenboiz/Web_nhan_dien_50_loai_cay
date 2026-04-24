"""
db_models.py – Định nghĩa bảng SQLAlchemy cho Flower Note 🌸
=============================================================
Bảng:
    - plants                       : Thông tin tĩnh về 50 loài cây
    - recognition_history         : Lịch sử nhận diện của người dùng
    - banana_plants                : Cơ sở dữ liệu riêng cho cây chuối (Musa spp.)
    - banana_recognition_history   : Lịch sử nhận diện cây chuối
    - papaya_plants                : Cơ sở dữ liệu riêng cho cây đu dủ (Carica papaya)
    - papaya_recognition_history   : Lịch sử nhận diện cây đu dủ
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


# ───────────────────────────── Bảng banana_plants ───────────────────────────
class BananaPlant(Base):
    """Cơ sở dữ liệu riêng cho cây chuối với thông tin chi tiết hơn."""

    __tablename__ = "banana_plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Thông tin cơ bản
    common_name: Mapped[str] = mapped_column(String(200), nullable=False)
    english_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scientific_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Nội dung chi tiết
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    characteristics: Mapped[str | None] = mapped_column(Text, nullable=True)
    uses: Mapped[str | None] = mapped_column(Text, nullable=True)
    care: Mapped[str | None] = mapped_column(Text, nullable=True)
    toxicity: Mapped[str | None] = mapped_column(String(500), nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Điều kiện trồng
    light_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    water_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ideal_temp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    humidity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Thông tin phát triển
    growth_rate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lifespan: Mapped[str | None] = mapped_column(String(100), nullable=True)
    propagation: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Dữ liệu bổ sung
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


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


# ────────── Bảng banana_recognition_history (Lịch sử nhận diện chuối) ────────
class BananaRecognitionHistory(Base):
    """Lịch sử nhận diện cây chuối – tự động kết nối khi phát hiện chuối."""

    __tablename__ = "banana_recognition_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Tham chiếu đến bảng banana_plants
    banana_plant_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Thông tin nhận diện
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    all_detections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Thông tin bổ sung
    ripeness_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)  # green, yellow, ripe, etc.
    estimated_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # số chuối trong nải

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ───────────────────────────── Bảng papaya_plants ───────────────────────────
class PapayaPlant(Base):
    """Cơ sở dữ liệu riêng cho cây đu dủ với thông tin chi tiết hơn."""

    __tablename__ = "papaya_plants"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Thông tin cơ bản
    common_name: Mapped[str] = mapped_column(String(200), nullable=False)
    english_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scientific_name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    family: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Nội dung chi tiết
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    characteristics: Mapped[str | None] = mapped_column(Text, nullable=True)
    uses: Mapped[str | None] = mapped_column(Text, nullable=True)
    care: Mapped[str | None] = mapped_column(Text, nullable=True)
    toxicity: Mapped[str | None] = mapped_column(String(500), nullable=True)
    benefits: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Điều kiện trồng
    light_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    water_requirement: Mapped[str | None] = mapped_column(String(300), nullable=True)
    ideal_temp: Mapped[str | None] = mapped_column(String(100), nullable=True)
    humidity: Mapped[str | None] = mapped_column(String(100), nullable=True)
    soil_type: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Thông tin phát triển
    growth_rate: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lifespan: Mapped[str | None] = mapped_column(String(100), nullable=True)
    propagation: Mapped[str | None] = mapped_column(String(300), nullable=True)

    # Dữ liệu bổ sung
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ────────── Bảng papaya_recognition_history (Lịch sử nhận diện đu dủ) ────────
class PapayaRecognitionHistory(Base):
    """Lịch sử nhận diện cây đu dủ – tự động kết nối khi phát hiện đu dủ."""

    __tablename__ = "papaya_recognition_history"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Tham chiếu đến bảng papaya_plants
    papaya_plant_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Thông tin nhận diện
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    processing_time_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    bbox: Mapped[list | None] = mapped_column(JSON, nullable=True)
    all_detections: Mapped[list | None] = mapped_column(JSON, nullable=True)
    image_base64: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Thông tin bổ sung
    ripeness_stage: Mapped[str | None] = mapped_column(String(100), nullable=True)  # green, yellow, ripe, etc.
    estimated_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)  # số quả đu dủ

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
