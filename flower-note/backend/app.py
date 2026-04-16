"""
app.py – FastAPI application chính cho Flower Note 🌸
======================================================
Khởi động:
    cd backend
    uvicorn app:app --reload --port 8000
"""

import logging
import time
import uuid
import json
from contextlib import asynccontextmanager
from pathlib import Path
import base64
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from database import init_db, AsyncSessionLocal
from db_models import Plant, RecognitionHistory
from models import get_predictor, PlantPredictor, PLANT_DATABASE

# ──────────────────────────── Logging ────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s – %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────── Load Plants Data ───────────────────────────────────
PLANTS_DATA_FILE = Path(__file__).parent / "plants_data.json"
PLANTS_DETAILED_DATA = {}

def load_plants_data():
    """Load dữ liệu chi tiết cây từ file JSON."""
    global PLANTS_DETAILED_DATA
    if PLANTS_DATA_FILE.exists():
        try:
            with open(PLANTS_DATA_FILE, "r", encoding="utf-8") as f:
                PLANTS_DETAILED_DATA = json.load(f)
            logger.info(f"✅ Đã load dữ liệu {len(PLANTS_DETAILED_DATA)} loài cây từ plants_data.json")
        except Exception as e:
            logger.error(f"❌ Lỗi load plants_data.json: {e}")
    else:
        logger.warning(f"⚠️ File plants_data.json không tìm thấy tại {PLANTS_DATA_FILE}")


# ─────────────────────── App Lifespan ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model + khởi tạo DB khi server khởi động."""
    logger.info("🌸 Flower Note server đang khởi động …")

    # ── Load dữ liệu cây chi tiết ─────────────────────────────────────────────
    load_plants_data()

    # ── Tạo bảng DB (nếu chưa có) ────────────────────────────────────────────
    try:
        await init_db()
        logger.info("✅ Database tables sẵn sàng.")
        await _seed_plants_if_empty()
    except Exception as e:
        logger.error("❌ Lỗi khởi tạo database: %s", e)

    # ── Load YOLOv8 model ─────────────────────────────────────────────────────
    try:
        predictor = get_predictor()
        app.state.predictor = predictor
        logger.info("✅ Model YOLOv8 sẵn sàng! Số lớp: %d", len(predictor.labels))
    except FileNotFoundError as e:
        logger.error("❌ %s", e)
        app.state.predictor = None

    yield
    logger.info("🌸 Server đang tắt …")


async def _seed_plants_if_empty():
    """Seed bảng plants từ PLANT_DATABASE nếu bảng còn trống."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plant).limit(1))
        if result.scalar_one_or_none() is not None:
            logger.info("📋 Bảng plants đã có dữ liệu, bỏ qua seed.")
            return

        logger.info("🌱 Seeding bảng plants …")
        for name, info in PLANT_DATABASE.items():
            plant = Plant(
                name=name,
                scientific_name=info.get("scientific_name"),
                description=info.get("description"),
                characteristics=info.get("characteristics"),
                uses=info.get("uses"),
                care=info.get("care"),
                warning=info.get("warning"),
            )
            session.add(plant)
        await session.commit()
        logger.info("✅ Seed xong %d loài cây.", len(PLANT_DATABASE))


# ────────────────────────── FastAPI App ──────────────────────────────────────
app = FastAPI(
    title="Flower Note API",
    description=(
        "🌸 **Flower Note** – API nhận diện 50 loài cây bằng YOLOv8.\n\n"
        "Upload một ảnh và nhận kết quả nhận diện kèm bounding box ngay lập tức."
    ),
    version="3.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ────────────────────────── Pydantic Schemas ─────────────────────────────────
class Detection(BaseModel):
    class_id:   int        = Field(..., description="Chỉ số lớp (0-49)")
    plant_name: str        = Field(..., description="Tên loài cây")
    confidence: float      = Field(..., ge=0.0, le=1.0)
    bbox:       list[float]= Field(..., description="[x1,y1,x2,y2] chuẩn hóa 0–1")


class PredictResponse(BaseModel):
    plant_name:              str
    confidence:              float
    description_placeholder: str
    scientific_name:         str | None = None
    characteristics:         str | None = None
    uses:                    str | None = None
    care:                    str | None = None
    warning:                 str | None = None
    processing_time_ms:      float      = 0.0
    bbox:                    list[float] | None = None
    all_detections:          list[Detection] = []


class HistoryItem(BaseModel):
    id:                  str
    plant_name:          str
    scientific_name:     str | None
    confidence:          float
    processing_time_ms:  float
    timestamp:           str

class HistoryDetail(HistoryItem):
    bbox:                list[float] | None = None
    all_detections:      list[dict] = []
    image_base64:        str | None = None


# ──────────────────────────── Endpoints ──────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "message": "🌸 Flower Note API v3 đang hoạt động!"}


@app.get("/api/health", tags=["Health"])
async def health():
    predictor: PlantPredictor | None = getattr(app.state, "predictor", None)
    if predictor is None:
        return JSONResponse(
            status_code=503,
            content={"status": "model_not_loaded",
                     "message": "❌ File best.pt chưa tồn tại hoặc không load được."},
        )
    return {
        "status": "ready",
        "num_classes": len(predictor.labels),
        "labels_sample": predictor.labels[:5],
    }


@app.post("/api/predict", response_model=PredictResponse, tags=["Inference"])
async def predict(
    file: UploadFile = File(...),
    conf: float = Query(default=0.25, ge=0.01, le=1.0),
):
    """Nhận ảnh, chạy YOLOv8, lưu lịch sử và trả về kết quả đầy đủ."""
    predictor: PlantPredictor | None = getattr(app.state, "predictor", None)
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model chưa được load.")

    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
    ct = (file.content_type or "").lower()
    if ct not in ALLOWED_TYPES:
        raise HTTPException(status_code=415, detail=f"Định dạng không hỗ trợ: '{file.content_type}'.")

    MAX_FILE_SIZE = 10 * 1024 * 1024
    image_bytes = await file.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File quá lớn (tối đa 10 MB).")

    # ── Đo thời gian inference ────────────────────────────────────────────────
    t_start = time.perf_counter()
    try:
        result = predictor.predict(image_bytes, conf_threshold=conf)
    except Exception as exc:
        logger.exception("❌ Lỗi inference: %s", exc)
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý ảnh: {str(exc)}") from exc
    processing_time_ms = round((time.perf_counter() - t_start) * 1000, 1)

    result["processing_time_ms"] = processing_time_ms

    # ── Lưu lịch sử vào PostgreSQL ────────────────────────────────────────────
    try:
        # Encode image to base64 for storage
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        mime_type = file.content_type or "image/jpeg"
        full_base64 = f"data:{mime_type};base64,{image_base64}"

        async with AsyncSessionLocal() as session:
            history = RecognitionHistory(
                id=str(uuid.uuid4()),
                plant_name=result["plant_name"],
                scientific_name=result.get("scientific_name"),
                confidence=result["confidence"],
                processing_time_ms=processing_time_ms,
                bbox=result.get("bbox"),
                all_detections=result.get("all_detections", []),
                image_base64=full_base64,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(history)
            await session.commit()
    except Exception as e:
        logger.warning("⚠️ Không lưu được lịch sử: %s", e)

    logger.info(
        "✅ %s (%.1f%%) | %.1f ms",
        result["plant_name"], result["confidence"] * 100, processing_time_ms
    )
    return result


@app.post("/api/predict-url", response_model=PredictResponse, tags=["Inference"])
async def predict_from_url(
    url: str = Body(..., embed=True),
    conf: float = Query(default=0.25, ge=0.01, le=1.0),
):
    """Nhận URL ảnh, tải xuống, chạy YOLOv8 và trả về kết quả."""
    predictor: PlantPredictor | None = getattr(app.state, "predictor", None)
    if predictor is None:
        raise HTTPException(status_code=503, detail="Model chưa được load.")

    # Validate URL
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="URL không hợp lệ. Chỉ hỗ trợ http/https.")

    # Fetch image from URL
    MAX_FILE_SIZE = 10 * 1024 * 1024
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=400, detail=f"Không tải được ảnh: HTTP {e.response.status_code}") from e
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Không tải được ảnh từ URL: {str(e)}") from e

    image_bytes = resp.content
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="Ảnh tải xuống quá lớn (tối đa 10 MB).")

    # Kiểm tra content type
    ct = (resp.headers.get("content-type", "")).lower().split(";")[0].strip()
    ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp", "image/jpg", "image/gif"}
    # Nếu server không trả content-type hình ảnh, vẫn thử (một số CDN không trả đúng)

    # Inference
    t_start = time.perf_counter()
    try:
        result = predictor.predict(image_bytes, conf_threshold=conf)
    except Exception as exc:
        logger.exception("❌ Lỗi inference từ URL: %s", exc)
        raise HTTPException(status_code=500, detail=f"Lỗi khi xử lý ảnh: {str(exc)}") from exc
    processing_time_ms = round((time.perf_counter() - t_start) * 1000, 1)
    result["processing_time_ms"] = processing_time_ms

    # Lưu lịch sử
    try:
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        full_base64 = f"data:image/jpeg;base64,{image_base64}" # Default to jpeg

        async with AsyncSessionLocal() as session:
            history = RecognitionHistory(
                id=str(uuid.uuid4()),
                plant_name=result["plant_name"],
                scientific_name=result.get("scientific_name"),
                confidence=result["confidence"],
                processing_time_ms=processing_time_ms,
                bbox=result.get("bbox"),
                all_detections=result.get("all_detections", []),
                image_base64=full_base64,
                timestamp=datetime.now(timezone.utc),
            )
            session.add(history)
            await session.commit()
    except Exception as e:
        logger.warning("⚠️ Không lưu được lịch sử: %s", e)

    logger.info(
        "✅ [URL] %s (%.1f%%) | %.1f ms",
        result["plant_name"], result["confidence"] * 100, processing_time_ms
    )
    return result


@app.get("/api/history", response_model=list[HistoryItem], tags=["History"])
async def get_history(limit: int = Query(default=20, ge=1, le=100)):
    """Lấy danh sách lịch sử nhận diện gần nhất từ PostgreSQL."""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(RecognitionHistory)
                .order_by(RecognitionHistory.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
    except Exception as e:
        logger.error("❌ Lỗi đọc lịch sử: %s", e)
        raise HTTPException(status_code=500, detail="Lỗi đọc lịch sử từ database.")

    return [
        {
            "id":                 row.id,
            "plant_name":         row.plant_name,
            "scientific_name":    row.scientific_name,
            "confidence":         row.confidence,
            "processing_time_ms": row.processing_time_ms,
            "timestamp":          row.timestamp.isoformat(),
        }
        for row in rows
    ]


@app.get("/api/history/{item_id}", response_model=HistoryDetail, tags=["History"])
async def get_history_detail(item_id: str):
    """Lấy chi tiết một mục lịch sử (bao gồm ảnh và tất cả detections)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RecognitionHistory).where(RecognitionHistory.id == item_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử.")
        
        return {
            "id":                 row.id,
            "plant_name":         row.plant_name,
            "scientific_name":    row.scientific_name,
            "confidence":         row.confidence,
            "processing_time_ms": row.processing_time_ms,
            "timestamp":          row.timestamp.isoformat(),
            "bbox":               row.bbox,
            "all_detections":     row.all_detections or [],
            "image_base64":       row.image_base64,
        }


@app.delete("/api/history/{item_id}", tags=["Admin"])
async def delete_history_item(item_id: str):
    """Xóa một mục lịch sử (Dành cho Admin)."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(RecognitionHistory).where(RecognitionHistory.id == item_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử.")
        
        await session.delete(row)
        await session.commit()
        return {"status": "success", "message": f"Đã xóa lịch sử {item_id}"}


@app.get("/api/plants", tags=["Plants"])
async def get_plants():
    """Lấy toàn bộ danh sách cây từ bảng plants."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Plant).order_by(Plant.name))
        plants = result.scalars().all()
    return [
        {
            "id": p.id, "name": p.name, "scientific_name": p.scientific_name,
            "description": p.description, "characteristics": p.characteristics,
            "uses": p.uses, "care": p.care, "warning": p.warning,
        }
        for p in plants
    ]


@app.get("/api/plants/detail/{plant_id}", tags=["Plants"])
async def get_plant_detail(plant_id: str):
    """Lấy dữ liệu chi tiết một loài cây từ plants_data.json."""
    logger.info(f"📌 Request plant detail: plant_id={plant_id}, type={type(plant_id)}")
    logger.info(f"📌 Available keys in PLANTS_DETAILED_DATA: {list(PLANTS_DETAILED_DATA.keys())}")
    
    if plant_id in PLANTS_DETAILED_DATA:
        return PLANTS_DETAILED_DATA[plant_id]
    else:
        logger.warning(f"⚠️ Plant detail not found for: {plant_id}")
        raise HTTPException(status_code=404, detail=f"Không tìm thấy dữ liệu cho loài cây id: {plant_id}")

