"""  # noqa – reload trigger: 2026-04-22T22:17
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
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import select, text

from database import init_db, AsyncSessionLocal, engine
from db_models import Plant, RecognitionHistory, BananaPlant, BananaRecognitionHistory, PapayaPlant, PapayaRecognitionHistory
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
BANANA_DATA_FILE = Path(__file__).parent / "banana_data.json"
PAPAYA_DATA_FILE = Path(__file__).parent / "papaya_data.json"
PLANTS_DETAILED_DATA = {}
BANANA_DETAILED_DATA = {}
PAPAYA_DETAILED_DATA = {}

def load_plants_data():
    """Load dữ liệu chi tiết cây từ file JSON."""
    global PLANTS_DETAILED_DATA
    if PLANTS_DATA_FILE.exists():
        try:
            with open(PLANTS_DATA_FILE, "r", encoding="utf-8") as f:
                PLANTS_DETAILED_DATA = json.load(f)
            logger.info(f"✅ Đã load dữ liệu {len(PLANTS_DETAILED_DATA)} loài cây từ plants_data.json")
            logger.info(f"📋 Keys loaded: {sorted(list(PLANTS_DETAILED_DATA.keys()))}")
            if '15' in PLANTS_DETAILED_DATA:
                logger.info(f"✅ Plant 15 loaded: {PLANTS_DETAILED_DATA['15'].get('common_name')}")
            else:
                logger.warning(f"⚠️ Plant 15 NOT found in loaded data!")
        except Exception as e:
            logger.error(f"❌ Lỗi load plants_data.json: {e}")
    else:
        logger.warning(f"⚠️ File plants_data.json không tìm thấy tại {PLANTS_DATA_FILE}")


def load_banana_data():
    """Load dữ liệu chi tiết chuối từ file JSON."""
    global BANANA_DETAILED_DATA
    if BANANA_DATA_FILE.exists(): 
        try:
            with open(BANANA_DATA_FILE, "r", encoding="utf-8") as f:
                BANANA_DETAILED_DATA = json.load(f)
            logger.info(f"✅ Đã load dữ liệu chuối từ banana_data.json")
            logger.info(f"📋 Chuối entries: {list(BANANA_DETAILED_DATA.keys())}")
        except Exception as e:
            logger.error(f"❌ Lỗi load banana_data.json: {e}")
    else:
        logger.warning(f"⚠️ File banana_data.json không tìm thấy tại {BANANA_DATA_FILE}")


def load_papaya_data():
    """Load dữ liệu chi tiết đu dủ từ file JSON."""
    global PAPAYA_DETAILED_DATA
    if PAPAYA_DATA_FILE.exists(): 
        try:
            with open(PAPAYA_DATA_FILE, "r", encoding="utf-8") as f:
                PAPAYA_DETAILED_DATA = json.load(f)
            logger.info(f"✅ Đã load dữ liệu đu dủ từ papaya_data.json")
            logger.info(f"📋 Đu dủ entries: {list(PAPAYA_DETAILED_DATA.keys())}")
        except Exception as e:
            logger.error(f"❌ Lỗi load papaya_data.json: {e}")
    else:
        logger.warning(f"⚠️ File papaya_data.json không tìm thấy tại {PAPAYA_DATA_FILE}")


# ─────────────────────── App Lifespan ────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model + khởi tạo DB khi server khởi động."""
    logger.info("🌸 Flower Note server đang khởi động …")

    # ── Load dữ liệu cây chi tiết ─────────────────────────────────────────────
    load_plants_data()
    # Chỉ load dữ liệu phụ khi file tồn tại
    if BANANA_DATA_FILE.exists():
        load_banana_data()
    if PAPAYA_DATA_FILE.exists():
        load_papaya_data()

    # ── Tạo bảng DB (nếu chưa có) ────────────────────────────────────────────
    try:
        await init_db()
        logger.info("✅ Database tables sẵn sàng.")
        await _seed_plants_if_empty()
        # Chỉ seed các bảng phụ khi có dữ liệu chi tiết tương ứng
        if BANANA_DETAILED_DATA:
            await _seed_bananas_if_empty()
        if PAPAYA_DETAILED_DATA:
            await _seed_papayas_if_empty()
        # Kiểm tra tồn tại bảng phụ trong DB và lưu flag vào app.state
        def _inspect_tables(sync_conn):
            from sqlalchemy import inspect
            insp = inspect(sync_conn)
            return insp.has_table("banana_plants"), insp.has_table("papaya_plants")

        async with engine.begin() as conn:
            banana_exists, papaya_exists = await conn.run_sync(_inspect_tables)
        app.state.banana_enabled = banana_exists
        app.state.papaya_enabled = papaya_exists
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


async def _seed_bananas_if_empty():
    """Seed bảng banana_plants từ BANANA_DETAILED_DATA nếu bảng còn trống."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BananaPlant).limit(1))
        if result.scalar_one_or_none() is not None:
            logger.info("📋 Bảng banana_plants đã có dữ liệu, bỏ qua seed.")
            return

        logger.info("🍌 Seeding bảng banana_plants …")
        for banana_key, banana_info in BANANA_DETAILED_DATA.items():
            banana = BananaPlant(
                common_name=banana_info.get("common_name"),
                english_name=banana_info.get("english_name"),
                scientific_name=banana_info.get("scientific_name"),
                family=banana_info.get("family"),
                description=banana_info.get("description"),
                characteristics=banana_info.get("characteristics"),
                uses=banana_info.get("uses"),
                care=banana_info.get("care"),
                toxicity=banana_info.get("toxicity"),
                benefits=banana_info.get("benefits"),
                light_requirement=banana_info.get("light_requirement"),
                water_requirement=banana_info.get("water_requirement"),
                ideal_temp=banana_info.get("ideal_temp"),
                humidity=banana_info.get("humidity"),
                soil_type=banana_info.get("soil_type"),
                growth_rate=banana_info.get("growth_rate"),
                lifespan=banana_info.get("lifespan"),
                propagation=banana_info.get("propagation"),
                extra_data={
                    "varieties": banana_info.get("varieties", []),
                    "ripeness_stages": banana_info.get("ripeness_stages", []),
                    "pest_diseases": banana_info.get("pest_diseases", []),
                    "harvest_tips": banana_info.get("harvest_tips", []),
                }
            )
            session.add(banana)
        await session.commit()
        logger.info("✅ Seed xong %d dữ liệu chuối.", len(BANANA_DETAILED_DATA))


async def _seed_papayas_if_empty():
    """Seed bảng papaya_plants từ PAPAYA_DETAILED_DATA nếu bảng còn trống."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(PapayaPlant).limit(1))
        if result.scalar_one_or_none() is not None:
            logger.info("📋 Bảng papaya_plants đã có dữ liệu, bỏ qua seed.")
            return

        logger.info("🧡 Seeding bảng papaya_plants …")
        for papaya_key, papaya_info in PAPAYA_DETAILED_DATA.items():
            papaya = PapayaPlant(
                common_name=papaya_info.get("common_name"),
                english_name=papaya_info.get("english_name"),
                scientific_name=papaya_info.get("scientific_name"),
                family=papaya_info.get("family"),
                description=papaya_info.get("description"),
                characteristics=papaya_info.get("characteristics"),
                uses=papaya_info.get("uses"),
                care=papaya_info.get("care"),
                toxicity=papaya_info.get("toxicity"),
                benefits=papaya_info.get("benefits"),
                light_requirement=papaya_info.get("light_requirement"),
                water_requirement=papaya_info.get("water_requirement"),
                ideal_temp=papaya_info.get("ideal_temp"),
                humidity=papaya_info.get("humidity"),
                soil_type=papaya_info.get("soil_type"),
                growth_rate=papaya_info.get("growth_rate"),
                lifespan=papaya_info.get("lifespan"),
                propagation=papaya_info.get("propagation"),
                extra_data={
                    "varieties": papaya_info.get("varieties", []),
                    "ripeness_stages": papaya_info.get("ripeness_stages", []),
                    "pest_diseases": papaya_info.get("pest_diseases", []),
                    "harvest_tips": papaya_info.get("harvest_tips", []),
                }
            )
            session.add(papaya)
        await session.commit()
        logger.info("✅ Seed xong %d dữ liệu đu dủ.", len(PAPAYA_DETAILED_DATA))


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
# ✅ CORS lật lá (*) cho phép tất cả domain, bao gồm ngrok. 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Nỗ làm cho ngrok hoàt động
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ FRONTEND_PATH sẽ được mount VÀO CUỐI (sau tất cả API endpoints)
FRONTEND_PATH = Path(__file__).parent.parent / "frontend"

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

@app.get("/api/", tags=["Health"])
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
        "frontend_available": FRONTEND_PATH.exists(),
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
            
            # ── Nếu phát hiện chuối, tự động lưu vào banana_recognition_history ──
            if result["plant_name"].lower() == "cây chuối" or "chuối" in result["plant_name"].lower():
                logger.info("🍌 Phát hiện chuối! Lưu vào bảng banana_recognition_history")
                try:
                    # Lấy banana plant (thường chỉ có 1)
                    banana_result = await session.execute(
                        select(BananaPlant).limit(1)
                    )
                    banana_plant = banana_result.scalar_one_or_none()
                    
                    if banana_plant:
                        banana_history = BananaRecognitionHistory(
                            id=str(uuid.uuid4()),
                            banana_plant_id=banana_plant.id,
                            confidence=result["confidence"],
                            processing_time_ms=processing_time_ms,
                            bbox=result.get("bbox"),
                            all_detections=result.get("all_detections", []),
                            image_base64=full_base64,
                            ripeness_stage=None,  # Could be detected by additional ML model
                            estimated_quantity=None,  # Could be counted by additional ML model
                            timestamp=datetime.now(timezone.utc),
                        )
                        session.add(banana_history)
                        await session.commit()
                        logger.info("✅ Đã lưu chuối vào bảng banana_recognition_history")
                except Exception as e:
                    logger.warning("⚠️ Lỗi lưu lịch sử chuối: %s", e)
            
            # ── Nếu phát hiện đu dủ, tự động lưu vào papaya_recognition_history ──
            if result["plant_name"].lower() == "cây đu dủ" or "đu dủ" in result["plant_name"].lower():
                logger.info("🧡 Phát hiện đu dủ! Lưu vào bảng papaya_recognition_history")
                try:
                    # Lấy papaya plant (thường chỉ có 1)
                    papaya_result = await session.execute(
                        select(PapayaPlant).limit(1)
                    )
                    papaya_plant = papaya_result.scalar_one_or_none()
                    
                    if papaya_plant:
                        papaya_history = PapayaRecognitionHistory(
                            id=str(uuid.uuid4()),
                            papaya_plant_id=papaya_plant.id,
                            confidence=result["confidence"],
                            processing_time_ms=processing_time_ms,
                            bbox=result.get("bbox"),
                            all_detections=result.get("all_detections", []),
                            image_base64=full_base64,
                            ripeness_stage=None,  # Could be detected by additional ML model
                            estimated_quantity=None,  # Could be counted by additional ML model
                            timestamp=datetime.now(timezone.utc),
                        )
                        session.add(papaya_history)
                        await session.commit()
                        logger.info("✅ Đã lưu đu dủ vào bảng papaya_recognition_history")
                except Exception as e:
                    logger.warning("⚠️ Lỗi lưu lịch sử đu dủ: %s", e)
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
            
            # ── Nếu phát hiện chuối, tự động lưu vào banana_recognition_history ──
            if result["plant_name"].lower() == "cây chuối" or "chuối" in result["plant_name"].lower():
                logger.info("🍌 Phát hiện chuối! Lưu vào bảng banana_recognition_history")
                try:
                    # Lấy banana plant (thường chỉ có 1)
                    banana_result = await session.execute(
                        select(BananaPlant).limit(1)
                    )
                    banana_plant = banana_result.scalar_one_or_none()
                    
                    if banana_plant:
                        banana_history = BananaRecognitionHistory(
                            id=str(uuid.uuid4()),
                            banana_plant_id=banana_plant.id,
                            confidence=result["confidence"],
                            processing_time_ms=processing_time_ms,
                            bbox=result.get("bbox"),
                            all_detections=result.get("all_detections", []),
                            image_base64=full_base64,
                            ripeness_stage=None,
                            estimated_quantity=None,
                            timestamp=datetime.now(timezone.utc),
                        )
                        session.add(banana_history)
                        await session.commit()
                        logger.info("✅ Đã lưu chuối vào bảng banana_recognition_history")
                except Exception as e:
                    logger.warning("⚠️ Lỗi lưu lịch sử chuối: %s", e)
            
            # ── Nếu phát hiện đu dủ, tự động lưu vào papaya_recognition_history ──
            if result["plant_name"].lower() == "cây đu dủ" or "đu dủ" in result["plant_name"].lower():
                logger.info("🧡 Phát hiện đu dủ! Lưu vào bảng papaya_recognition_history")
                try:
                    # Lấy papaya plant (thường chỉ có 1)
                    papaya_result = await session.execute(
                        select(PapayaPlant).limit(1)
                    )
                    papaya_plant = papaya_result.scalar_one_or_none()
                    
                    if papaya_plant:
                        papaya_history = PapayaRecognitionHistory(
                            id=str(uuid.uuid4()),
                            papaya_plant_id=papaya_plant.id,
                            confidence=result["confidence"],
                            processing_time_ms=processing_time_ms,
                            bbox=result.get("bbox"),
                            all_detections=result.get("all_detections", []),
                            image_base64=full_base64,
                            ripeness_stage=None,
                            estimated_quantity=None,
                            timestamp=datetime.now(timezone.utc),
                        )
                        session.add(papaya_history)
                        await session.commit()
                        logger.info("✅ Đã lưu đu dủ vào bảng papaya_recognition_history")
                except Exception as e:
                    logger.warning("⚠️ Lỗi lưu lịch sử đu dủ: %s", e)
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
        # Return empty list instead of error
        return []

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


# ──────────────────────── Banana Endpoints ───────────────────────────────────
@app.get("/api/bananas", tags=["Bananas"])
async def get_bananas():
    """Lấy toàn bộ danh sách chuối từ bảng banana_plants."""
    if not getattr(app.state, "banana_enabled", False):
        raise HTTPException(status_code=404, detail="Banana database not available.")
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BananaPlant).order_by(BananaPlant.common_name))
        bananas = result.scalars().all()
    
    return [
        {
            "id": b.id,
            "common_name": b.common_name,
            "english_name": b.english_name,
            "scientific_name": b.scientific_name,
            "family": b.family,
            "description": b.description,
            "characteristics": b.characteristics,
            "uses": b.uses,
            "care": b.care,
            "toxicity": b.toxicity,
            "benefits": b.benefits,
            "light_requirement": b.light_requirement,
            "water_requirement": b.water_requirement,
            "ideal_temp": b.ideal_temp,
            "humidity": b.humidity,
            "soil_type": b.soil_type,
            "growth_rate": b.growth_rate,
            "lifespan": b.lifespan,
            "propagation": b.propagation,
            "extra_data": b.extra_data,
        }
        for b in bananas
    ]


@app.get("/api/bananas/{banana_id}", tags=["Bananas"])
async def get_banana_detail(banana_id: int):
    """Lấy dữ liệu chi tiết của một loài chuối."""
    if not getattr(app.state, "banana_enabled", False):
        raise HTTPException(status_code=404, detail="Banana database not available.")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BananaPlant).where(BananaPlant.id == banana_id)
        )
        banana = result.scalar_one_or_none()
        if not banana:
            raise HTTPException(status_code=404, detail="Không tìm thấy chuối.")
        
        return {
            "id": banana.id,
            "common_name": banana.common_name,
            "english_name": banana.english_name,
            "scientific_name": banana.scientific_name,
            "family": banana.family,
            "description": banana.description,
            "characteristics": banana.characteristics,
            "uses": banana.uses,
            "care": banana.care,
            "toxicity": banana.toxicity,
            "benefits": banana.benefits,
            "light_requirement": banana.light_requirement,
            "water_requirement": banana.water_requirement,
            "ideal_temp": banana.ideal_temp,
            "humidity": banana.humidity,
            "soil_type": banana.soil_type,
            "growth_rate": banana.growth_rate,
            "lifespan": banana.lifespan,
            "propagation": banana.propagation,
            "extra_data": banana.extra_data,
        }


@app.get("/api/banana-history", tags=["Bananas"])
async def get_banana_history(limit: int = Query(default=20, ge=1, le=100)):
    """Lấy danh sách lịch sử nhận diện chuối gần nhất."""
    if not getattr(app.state, "banana_enabled", False):
        return []
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BananaRecognitionHistory)
            .order_by(BananaRecognitionHistory.timestamp.desc())
            .limit(limit)
        )
        rows = result.scalars().all()
    
    return [
        {
            "id": row.id,
            "banana_plant_id": row.banana_plant_id,
            "confidence": row.confidence,
            "processing_time_ms": row.processing_time_ms,
            "ripeness_stage": row.ripeness_stage,
            "estimated_quantity": row.estimated_quantity,
            "timestamp": row.timestamp.isoformat(),
        }
        for row in rows
    ]


@app.get("/api/banana-history/{history_id}", tags=["Bananas"])
async def get_banana_history_detail(history_id: str):
    """Lấy chi tiết lịch sử nhận diện chuối (bao gồm ảnh)."""
    if not getattr(app.state, "banana_enabled", False):
        raise HTTPException(status_code=404, detail="Banana database not available.")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BananaRecognitionHistory).where(BananaRecognitionHistory.id == history_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử chuối.")
        
        return {
            "id": row.id,
            "banana_plant_id": row.banana_plant_id,
            "confidence": row.confidence,
            "processing_time_ms": row.processing_time_ms,
            "bbox": row.bbox,
            "all_detections": row.all_detections or [],
            "image_base64": row.image_base64,
            "ripeness_stage": row.ripeness_stage,
            "estimated_quantity": row.estimated_quantity,
            "timestamp": row.timestamp.isoformat(),
        }


@app.post("/api/banana-history", tags=["Bananas"])
async def create_banana_history(
    banana_plant_id: int = Body(...),
    confidence: float = Body(...),
    processing_time_ms: float = Body(default=0.0),
    bbox: list[float] | None = Body(default=None),
    ripeness_stage: str | None = Body(default=None),
    estimated_quantity: int | None = Body(default=None),
):
    """Tạo bản ghi lịch sử chuối mới (thường được gọi tự động khi phát hiện chuối)."""
    if not getattr(app.state, "banana_enabled", False):
        raise HTTPException(status_code=404, detail="Banana database not available.")
    async with AsyncSessionLocal() as session:
        # Kiểm tra chuối tồn tại
        banana_result = await session.execute(
            select(BananaPlant).where(BananaPlant.id == banana_plant_id)
        )
        if banana_result.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Không tìm thấy chuối ID.")
        
        history = BananaRecognitionHistory(
            id=str(uuid.uuid4()),
            banana_plant_id=banana_plant_id,
            confidence=confidence,
            processing_time_ms=processing_time_ms,
            bbox=bbox,
            ripeness_stage=ripeness_stage,
            estimated_quantity=estimated_quantity,
            timestamp=datetime.now(timezone.utc),
        )
        session.add(history)
        await session.commit()
        
        return {
            "id": history.id,
            "banana_plant_id": history.banana_plant_id,
            "confidence": history.confidence,
            "processing_time_ms": history.processing_time_ms,
            "timestamp": history.timestamp.isoformat(),
        }


@app.delete("/api/banana-history/{history_id}", tags=["Bananas"])
async def delete_banana_history(history_id: str):
    """Xóa một bản ghi lịch sử chuối."""
    if not getattr(app.state, "banana_enabled", False):
        raise HTTPException(status_code=404, detail="Banana database not available.")
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(BananaRecognitionHistory).where(BananaRecognitionHistory.id == history_id)
        )
        row = result.scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy lịch sử chuối.")
        
        await session.delete(row)
        await session.commit()
        return {"status": "success", "message": f"Đã xóa lịch sử chuối {history_id}"}


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


# ── STATIC FILES (Frontend) - MOUNT VÀO CUỐI sau tất cả API endpoints ────────
# ✅ Mount frontend folder để serve HTML/CSS/JS qua ngrok
# ⚠️ PHẢI đặt CUỐI cùng vì static files mount sẽ intercept tất cả requests không match endpoints
if FRONTEND_PATH.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_PATH), html=True), name="frontend")
    logger.info(f"✅ Frontend mounted tại {FRONTEND_PATH}")
else:
    logger.warning(f"⚠️ Frontend folder không tìm thấy tại {FRONTEND_PATH}")

