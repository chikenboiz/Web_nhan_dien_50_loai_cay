# 🌸 Flower Note – Ứng dụng Nhận diện Cây Xanh

> **Flower Note** là ứng dụng web nhận diện **50 loài cây** thông minh bằng mô hình **YOLOv8** (GREENIE Model), được xây dựng với FastAPI (Backend) và HTML/CSS/JS thuần (Frontend).

---

## 📁 Cấu trúc dự án

```
flower-note/
├── backend/
│   ├── app.py              # FastAPI application – endpoints chính
│   ├── models.py           # PlantPredictor – load & inference YOLOv8
│   ├── labels.txt          # 50 tên loài cây (index 0–49)
│   ├── best.pt             # ← Bạn tự đặt file trọng số vào đây
│   └── requirements.txt    # Dependencies Python
├── frontend/
│   ├── index.html          # Giao diện – Cute Pig Pink Pastel Theme
│   ├── style.css           # Design system đầy đủ
│   └── script.js           # Logic: Drag & Drop, Fetch, Canvas, Animation
└── README.md
```

---

## ⚙️ Cài đặt & Khởi chạy

### 1. Backend (FastAPI)

```bash
# Di chuyển vào thư mục backend
cd backend

# (Khuyến nghị) Tạo virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux

# Cài dependencies
pip install -r requirements.txt

# Đặt file trọng số vào đúng vị trí
# → Copy file best.pt của bạn vào: flower-note/backend/best.pt

# Khởi động server
uvicorn app:app --reload --port 8000
```

Sau khi khởi động, server sẽ chạy tại: `http://127.0.0.1:8000`

API Docs tự động: `http://127.0.0.1:8000/docs`

### 2. Frontend

**Cách đơn giản nhất** – mở file trực tiếp:
```
flower-note/frontend/index.html  →  Mở bằng trình duyệt (Double click)
```

**Hoặc dùng Live Server** (VS Code extension) để tự động reload khi chỉnh sửa.

> ⚠️ Frontend gọi API tại `http://127.0.0.1:8000` – hãy đảm bảo backend đang chạy!

---

## 🌿 Hướng dẫn sử dụng

1. **Mở** `frontend/index.html` trong trình duyệt.
2. **Upload ảnh** bằng cách:
   - Kéo & thả ảnh vào vùng drop zone, hoặc
   - Click vào drop zone để chọn file, hoặc
   - **Dán ảnh** từ clipboard (Ctrl+V)
3. Nhấn nút **"Nhận diện ngay"** 🔍
4. Xem kết quả:
   - Tên loài cây + emoji đặc trưng
   - Độ tự tin (confidence %) + thanh tiến trình
   - Mô tả chi tiết về loài cây
   - Bounding box khoanh vùng cây trên ảnh
   - Danh sách tất cả detections xếp hạng

---

## 🔌 API Endpoints

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| `GET`  | `/` | Kiểm tra server |
| `GET`  | `/api/health` | Trạng thái model |
| `POST` | `/api/predict` | Nhận diện cây từ ảnh |
| `GET`  | `/docs` | Swagger UI tự động |

### Ví dụ gọi `/api/predict`

**Request:**
```bash
curl -X POST http://127.0.0.1:8000/api/predict \
  -F "file=@my_plant.jpg" \
  -F "conf=0.25"
```

**Response:**
```json
{
  "plant_name": "Hoa hồng (Rosa)",
  "confidence": 0.9213,
  "description_placeholder": "Nữ hoàng các loài hoa với hương thơm...",
  "bbox": [0.12, 0.08, 0.88, 0.92],
  "all_detections": [
    {
      "class_id": 9,
      "plant_name": "Hoa hồng (Rosa)",
      "confidence": 0.9213,
      "bbox": [0.12, 0.08, 0.88, 0.92]
    }
  ]
}
```

---

## 🎨 Đặc điểm Frontend

| Tính năng | Mô tả |
|-----------|-------|
| **Chủ đề** | Pink Pastel "Cute Pig" 🐷 – bo tròn mọi element |
| **Logo heo** | Animation wiggle 3D liên tục |
| **Background** | 4 animated orbs + floating petals |
| **Drop zone** | Rings pulse animation, drag overlay |
| **Nút Nhận diện** | Shimmer effect + hearts burst khi hover |
| **Loading** | Pig bounce + 5-dot wave + fake progress bar |
| **Kết quả** | Slide reveal + confidence bar animation |
| **Bounding box** | Canvas overlay với label tag |
| **Health check** | Tự động kiểm tra backend mỗi 30 giây |
| **Responsive** | Mobile-first, 3 breakpoints: 480/768/1024px |
| **Accessibility** | ARIA labels, keyboard nav, reduced-motion |
| **Paste** | Ctrl+V để dán ảnh từ clipboard |

---

## 🧠 Chi tiết ML Pipeline

```
Ảnh input (JPG/PNG/WEBP)
    ↓
PIL.Image.open() → convert RGB
    ↓
ultralytics YOLO.predict()
    ├── Auto resize → 640×640
    ├── Normalize pixels → [0, 1]
    ├── CHW batching
    └── NMS (IoU=0.45, conf=0.25)
    ↓
Post-processing
    ├── boxes.xyxyn → tọa độ chuẩn hóa 0–1
    ├── argmax(conf) → detection tốt nhất
    └── Map class_id → plant_name (labels.txt)
    ↓
JSON response → Frontend render
```

---

## 📋 Danh sách 50 loài cây (labels.txt)

| # | Tên cây | # | Tên cây |
|---|---------|---|---------|
| 0 | Lô hội (Aloe Vera) | 25 | Cây ráy (Alocasia) |
| 1 | Bạch tuộc (Monstera) | 26 | Cây sung trưởng (Ficus Benjamina) |
| 2 | Sen đá (Echeveria) | 27 | Thiết mộc lan (Pandanus) |
| 3 | Xương rồng tai thỏ | 28 | Cây đơn đỏ (Syzygium) |
| 4 | Kim tiền (ZZ Plant) | 29 | Cây sung (Ficus Carica) |
| 5 | Trầu bà (Pothos) | 30 | Húng quế (Basil) |
| 6 | Đa búp đỏ (Rubber Tree) | 31 | Húng lủi (Spearmint) |
| 7 | Lưỡi hổ (Snake Plant) | 32 | Rau má (Centella) |
| 8 | Cây bơ (Avocado) | 33 | Sả chanh (Lemongrass) |
| 9 | Hoa hồng (Rose) | 34 | Gừng (Ginger) |
| 10 | Cúc vạn thọ (Marigold) | 35 | Nghệ (Turmeric) |
| 11 | Hướng dương (Sunflower) | 36 | Tía tô (Perilla) |
| 12 | Hoa lan (Orchid) | 37 | Lá lốt (Piper) |
| 13 | Cẩm tú cầu (Hydrangea) | 38 | Nha đam biển (Aloe Barbadensis) |
| 14 | Hoa anh đào (Sakura) | 39 | Cây diếp cá (Houttuynia) |
| 15 | Hoa tulip (Tulip) | 40 | Trà xanh (Green Tea) |
| 16 | Hoa huệ (Lily) | 41 | Cây cà phê (Coffee) |
| 17 | Hoa lavender (Lavender) | 42 | Cây mít (Jackfruit) |
| 18 | Hoa mai (Vietnamese Mai) | 43 | Cây nhãn (Longan) |
| 19 | Hoa đào (Peach Blossom) | 44 | Cây xoài (Mango) |
| 20 | Cây xanh tre (Bamboo) | 45 | Cây bưởi (Pomelo) |
| 21 | Cây dừa cảnh (Cycas) | 46 | Cây cam (Orange) |
| 22 | Cây phát tài (Lucky Bamboo) | 47 | Cây ổi (Guava) |
| 23 | Ngũ gia bì (Schefflera) | 48 | Cây khế (Starfruit) |
| 24 | Cây đuôi công (Peace Lily) | 49 | Cây sapô (Sapodilla) |

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| **ML Framework** | YOLOv8 (Ultralytics) |
| **Backend** | FastAPI + Uvicorn |
| **Image Processing** | Pillow + NumPy + OpenCV |
| **Frontend** | Vanilla HTML5 + CSS3 + JS (ES2022) |
| **Fonts** | Pacifico + Nunito + DM Sans (Google Fonts) |
| **Icons** | FontAwesome 6 |

---

## 💡 Tips & Troubleshooting

**❓ Server báo 503 – Model not loaded:**
→ Đảm bảo file `best.pt` nằm trong thư mục `backend/` và khởi động lại server.

**❓ Frontend không kết nối được:**
→ Kiểm tra backend đang chạy tại `http://127.0.0.1:8000`
→ Nếu dùng port khác, sửa `API_BASE` trong `script.js`.

**❓ Kết quả không chính xác:**
→ Dùng ảnh rõ nét, đủ ánh sáng, chụp gần cây hơn.
→ Thử giảm ngưỡng `conf` xuống `0.15` trong `CONFIG.CONF_DEFAULT`.

**❓ CORS error trên browser:**
→ Backend đã cấu hình `allow_origins=["*"]` – nếu vẫn lỗi thì dùng Live Server thay vì mở file trực tiếp.

---

Made with 💕 by **Flower Note** · Powered by YOLOv8 & FastAPI · © 2025
