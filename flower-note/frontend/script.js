/**
 * script.js – Flower Note Frontend Logic 🌸 v3.0
 * =================================================
 * Xử lý:
 *   • Drag & Drop ảnh + file input + clipboard paste
 *   • Preview ảnh ngay lập tức
 *   • Gửi ảnh lên FastAPI /api/predict bằng Fetch API
 *   • Hiển thị loading spinner với progress bar giả
 *   • Render kết quả: tên cây, confidence bar, tab chi tiết, bounding boxes
 *   • Tab switching: Mô tả / Đặc điểm / Công dụng / Chăm sóc / Cảnh báo
 *   • Lịch sử nhận diện từ PostgreSQL (/api/history)
 *   • Heart burst animation khi hover nút Nhận diện
 *   • Health check khi tải trang
 *   • Toast notification (thành công & lỗi)
 *   • Keyboard accessibility
 */

'use strict';

/* ════════════════════════════════════════════════
   CONFIGURATION
════════════════════════════════════════════════ */
// Auto-detect API base URL (localhost or ngrok)
const getAPIBase = () => {
  const url = new URL(window.location.href);
  // If accessing via ngrok or custom domain, use it as base
  if (url.hostname !== 'localhost' && url.hostname !== '127.0.0.1') {
    return `${url.protocol}//${url.host}`;
  }
  // Otherwise use localhost:8000
  return 'http://localhost:8000';
};

const API_BASE = getAPIBase();

const CONFIG = {
  API_BASE:    API_BASE,
  API_PREDICT: `${API_BASE}/api/predict`,
  API_HEALTH:  `${API_BASE}/api/health`,
  API_HISTORY: `${API_BASE}/api/history`,
  MAX_FILE_MB: 10,
  CONF_DEFAULT: 0.25,
  HEALTH_INTERVAL_MS: 30_000,
  FETCH_TIMEOUT: 60_000,  // 60 seconds for slower ngrok connections
};

/* ════════════════════════════════════════════════
   THEME CONFIGURATION
════════════════════════════════════════════════ */
const THEME_CONFIG = {
  flower: {
    mainEmoji: '🌸',
    bgParticles: ['🌸', '🌺', '🌼', '🌹', '🌷', '🏵️'],
    burstEmojis: ['❤️', '🩷', '💕', '💖', '💗', '🌸']
  },
  leaf: {
    mainEmoji: '🌿',
    bgParticles: ['🌿', '🍃', '🌱', '🍀', '🪴', '🍂'],
    burstEmojis: ['🌿', '🌱', '🍃', '🪴', '🍀', '✨']
  },
  fruit: {
    mainEmoji: '🍊',
    bgParticles: ['🍎', '🍏', '🍊', '🍋', '🍇', '🍓', '🍑', '🥭'],
    burstEmojis: ['🍎', '🍊', '🍋', '🍐', '🍓', '✨'],
    boxColor: '#FF9800',
    boxFill: 'rgba(255, 152, 0, 0.14)'
  }
};

const THEME_COLORS = {
  flower: { stroke: '#FF6B8B', fill: 'rgba(255, 107, 139, 0.14)', label: '#FF6B8B' },
  leaf:   { stroke: '#8BC34A', fill: 'rgba(139, 195, 74, 0.14)',  label: '#8BC34A' },
  fruit:  { stroke: '#FF9800', fill: 'rgba(255, 152, 0, 0.14)',  label: '#FF9800' }
};

let currentTheme = 'leaf';

function getThemeByPlantName(name) {
  const n = name.toLowerCase();
  if (n.includes('hoa') || n.includes('hồ') || n.includes('lan') || n.includes('cúc')) return 'flower';
  if (n.includes('quả') || n.includes('cam') || n.includes('bưởi') || n.includes('xoài') || n.includes('ổi')) return 'fruit';
  return 'leaf';
}

function getPlantEmoji(plantName) {
  const theme = getThemeByPlantName(plantName);
  return THEME_CONFIG[theme].mainEmoji;
}

function updateTheme(themeType) {
  if (themeType === currentTheme) return;
  currentTheme = themeType;
  document.body.setAttribute('data-theme', themeType);
  
  const config = THEME_CONFIG[themeType];
  
  // Update static icons (skip main-logo-emoji as it's now an image)
  const loadingEmoji = $('loading-emoji');
  if (loadingEmoji) loadingEmoji.textContent = config.mainEmoji;
  
  const footerLogo = $('footer-logo-emoji');
  if (footerLogo) footerLogo.textContent = config.mainEmoji;

  const dropZoneEmoji = $('drop-zone-emoji');
  if (dropZoneEmoji) dropZoneEmoji.textContent = config.mainEmoji;

  // Update background particles
  updateBackgroundParticles(themeType);
}

function updateBackgroundParticles(themeType) {
  const container = $('floating-particles');
  if (!container) return;
  
  const config = THEME_CONFIG[themeType];
  const particles = container.querySelectorAll('.particle');
  
  particles.forEach(p => {
    p.textContent = config.bgParticles[Math.floor(Math.random() * config.bgParticles.length)];
  });
}

/* ════════════════════════════════════════════════
   DOM REFERENCES
════════════════════════════════════════════════ */
const $ = (id) => document.getElementById(id);

const dropZone         = $('drop-zone');
const fileInput        = $('file-input');
const previewContainer = $('preview-container');
const previewImg       = $('preview-img');
const previewCanvas    = $('preview-canvas');
const removeImgBtn     = $('remove-img-btn');
const previewFileName  = $('preview-file-name');
const previewFileSize  = $('preview-file-size');

const btnPredict       = $('btn-predict');
const btnHintText      = $('btn-hint-text');

const loadingOverlay   = $('loading-overlay');
const loadingBar       = $('loading-bar');

const resultCard       = $('result-card');
const resultImg        = $('result-img');
const resultCanvas     = $('result-canvas');
const detectionBadge   = $('detection-badge');
const detectionCount   = $('detection-count');

const resName          = $('res-name');
const resPlantEmoji    = $('res-plant-emoji');
const resConfText      = $('res-conf-text');
const resConfBar       = $('res-conf-bar');
const resConfGrade     = $('res-conf-grade');
const resScientific    = $('res-scientific-name');
const processingTime   = $('processing-time');

// Tab panels
const resDesc          = $('res-desc');
const resChars         = $('res-chars');
const resUses          = $('res-uses');
const resCare          = $('res-care');
const resWarnText      = $('res-warn-text');
const tabWarn          = $('tab-warn');

const detectionsList   = $('detections-list');
const allDetectionsWrap= $('all-detections-wrap');

const btnRetry         = $('btn-retry');
const btnRepredict     = $('btn-repredict');

const statusDot        = $('status-dot');
const statusText       = $('status-text');
const toast            = $('toast');

const historyList      = $('history-list');
const historyEmpty     = $('history-empty');
const btnClearHistory  = $('btn-clear-history');

/* ════════════════════════════════════════════════
   STATE & DOM MỚI (TABS, WEBCAM, URL)
════════════════════════════════════════════════ */
let currentInputMode = 'file'; // 'file' | 'webcam' | 'url'
let webcamStream     = null;
let currentFile      = null;
let lastResult       = null;
let selectedIndex    = 0;
let toastTimer       = null;
let healthTimer      = null;

const uploadTabBtns = document.querySelectorAll('.upload-tab-btn');
const uploadPanels  = document.querySelectorAll('.upload-panel');

const webcamVideo   = $('webcam-video');
const webcamOverlay = $('webcam-overlay');
const btnCapture    = $('btn-capture');
const webcamCanvas  = $('webcam-canvas');
const urlInput      = $('url-input');

async function startWebcam() {
  try {
    webcamStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
    webcamVideo.srcObject = webcamStream;
    webcamOverlay.classList.add('hidden');
  } catch (err) {
    console.error('Lỗi Webcam:', err);
    let errorMsg = 'Không thể bật camera';
    let toastMsg = '❌ Vui lòng cấp quyền truy cập Camera!';
    
    // Better error messages based on error type
    if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
      errorMsg = 'Quyền truy cập bị từ chối';
      toastMsg = '❌ Bạn đã từ chối quyền truy cập camera. Vui lòng cho phép trong cài đặt!';
    } else if (err.name === 'NotFoundError' || err.name === 'DevicesNotFoundError') {
      errorMsg = 'Không tìm thấy camera';
      toastMsg = '❌ Thiết bị không có camera hoặc camera bị sử dụng bởi ứng dụng khác!';
    } else if (err.name === 'NotReadableError') {
      errorMsg = 'Camera đang bị sử dụng';
      toastMsg = '❌ Camera đang được ứng dụng khác sử dụng. Hãy tắt nó và thử lại!';
    } else if (err.name === 'SecurityError') {
      errorMsg = 'Vấn đề bảo mật';
      toastMsg = '❌ Truy cập camera bị chặn do vấn đề bảo mật. Hãy dùng HTTPS hoặc localhost!';
    }
    
    webcamOverlay.innerHTML = `<i class="fa-solid fa-triangle-exclamation fa-2x"></i><p>${errorMsg}</p>`;
    showToast(toastMsg, 'error');
  }
}

function stopWebcam() {
  if (webcamStream) {
    webcamStream.getTracks().forEach(track => track.stop());
    webcamStream = null;
  }
  if (webcamVideo) webcamVideo.srcObject = null;
  if (webcamOverlay) {
    webcamOverlay.classList.remove('hidden');
    webcamOverlay.innerHTML = '<i class="fa-solid fa-camera fa-2x"></i><p>Đang bật camera...</p>';
  }
}

/* ════════════════════════════════════════════════
   HEALTH CHECK
════════════════════════════════════════════════ */
async function checkHealth() {
  try {
    const res   = await fetch(CONFIG.API_HEALTH, { signal: AbortSignal.timeout(CONFIG.FETCH_TIMEOUT) });
    const data  = await res.json();
    const ready = res.ok && data.status === 'ready';
    statusDot.className   = ready ? 'fa-solid fa-circle online' : 'fa-solid fa-circle offline';
    statusText.textContent = ready
      ? `Sẵn sàng · ${data.num_classes ?? 50} loài`
      : 'Model chưa load';
  } catch {
    statusDot.className   = 'fa-solid fa-circle offline';
    statusText.textContent = 'Không kết nối được';
  }
}

function startHealthCheck() {
  checkHealth();
  healthTimer = setInterval(checkHealth, CONFIG.HEALTH_INTERVAL_MS);
}

/* ════════════════════════════════════════════════
   DRAG & DROP + FILE SELECTION
════════════════════════════════════════════════ */
dropZone.addEventListener('click', () => fileInput.click());

dropZone.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
});

dropZone.addEventListener('dragenter', (e) => { e.preventDefault(); });
dropZone.addEventListener('dragover',  (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', (e) => {
  if (!dropZone.contains(e.relatedTarget)) dropZone.classList.remove('dragover');
});
dropZone.addEventListener('drop', (e) => {
  e.preventDefault();
  dropZone.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFile(fileInput.files[0]);
});

document.addEventListener('paste', (e) => {
  const items = e.clipboardData?.items;
  if (!items) return;
  for (const item of items) {
    if (item.kind === 'file' && item.type.startsWith('image/')) { handleFile(item.getAsFile()); break; }
  }
});

function handleFile(file) {
  const ALLOWED = ['image/jpeg', 'image/png', 'image/webp', 'image/jpg'];
  if (!ALLOWED.includes(file.type)) { showToast('⚠️ Chỉ hỗ trợ JPG, PNG và WEBP!', 'error'); return; }

  const maxBytes = CONFIG.MAX_FILE_MB * 1024 * 1024;
  if (file.size > maxBytes) { showToast(`⚠️ Ảnh phải nhỏ hơn ${CONFIG.MAX_FILE_MB} MB!`, 'error'); return; }

  currentFile = file;
  previewFileName.textContent = file.name;
  previewFileSize.textContent = formatFileSize(file.size);

  const reader = new FileReader();
  reader.onload = (ev) => {
    previewImg.src = ev.target.result;
    previewContainer.style.display = 'block';
    clearCanvas(previewCanvas);
    hideResult();
  };
  reader.readAsDataURL(file);

  btnHintText.textContent = '✅ Ảnh sẵn sàng – nhấn nút để nhận diện!';
  btnHintText.style.color = 'var(--c-green-500)';
}

function formatFileSize(bytes) {
  if (bytes < 1024)       return `${bytes} B`;
  if (bytes < 1024*1024)  return `${(bytes/1024).toFixed(1)} KB`;
  return `${(bytes/1024/1024).toFixed(2)} MB`;
}

/* ════════════════════════════════════════════════
   PREDICT BUTTON – HEART ANIMATION
════════════════════════════════════════════════ */
const HEARTS = ['❤️', '🩷', '💕', '💖', '💗', '🌸'];

btnPredict.addEventListener('mouseenter', spawnHearts);

function spawnHearts() {
  const wrapper = btnPredict.parentElement;
  const config = THEME_CONFIG[currentTheme];
  const burstPool = config.burstEmojis;

  for (let i = 0; i < 8; i++) {
    setTimeout(() => {
      const heart      = document.createElement('span');
      heart.className  = 'heart-burst';
      heart.textContent = burstPool[Math.floor(Math.random() * burstPool.length)];
      heart.style.setProperty('--duration', `${0.7 + Math.random() * 0.4}s`);
      const angle = Math.random() * 2 * Math.PI;
      const dist  = 50 + Math.random() * 80;
      heart.style.setProperty('--tx', `${(Math.cos(angle) * dist).toFixed(0)}px`);
      heart.style.setProperty('--ty', `${(Math.sin(angle) * dist - 20).toFixed(0)}px`);
      const btnRect     = btnPredict.getBoundingClientRect();
      const wrapperRect = wrapper.getBoundingClientRect();
      heart.style.left     = `${btnRect.left - wrapperRect.left + btnRect.width  * (0.3 + Math.random() * 0.4)}px`;
      heart.style.top      = `${btnRect.top  - wrapperRect.top  + btnRect.height * (0.2 + Math.random() * 0.6)}px`;
      heart.style.position = 'absolute';
      heart.style.zIndex   = '50';
      wrapper.appendChild(heart);
      const dur = parseFloat(heart.style.getPropertyValue('--duration').replace('s','')) * 1000;
      setTimeout(() => heart.remove(), dur + 50);
    }, i * 70);
  }
}

/* ════════════════════════════════════════════════
   MAIN PREDICT FLOW
════════════════════════════════════════════════ */

// Add touch feedback for mobile users
function addTouchFeedback(btn) {
  if (!btn) {
    console.warn('[addTouchFeedback] Button is null!');
    return;
  }
  console.log('[addTouchFeedback] Adding feedback to:', btn.id);
  btn.addEventListener('touchstart', () => {
    console.log('[touch] touchstart on', btn.id);
    btn.style.opacity = '0.7';
  });
  btn.addEventListener('touchend', () => {
    console.log('[touch] touchend on', btn.id);
    btn.style.opacity = '1';
  });
}

async function runPrediction() {
  setLoading(true);
  
  let fetchPromise;
  if (currentInputMode === 'url') {
    const urlValue = urlInput.value.trim();
    previewImg.src = urlValue; // Set tạm preview để resultImg lấy được src
    fetchPromise = fetch(`${CONFIG.API_BASE}/api/predict-url?conf=${CONFIG.CONF_DEFAULT}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: urlValue })
    });
  } else {
    const formData = new FormData();
    formData.append('file', currentFile);
    fetchPromise = fetch(`${CONFIG.API_PREDICT}?conf=${CONFIG.CONF_DEFAULT}`, {
      method: 'POST',
      body: formData
    });
  }

  try {
    clearResults();
    // Wrap fetchPromise with timeout
    const timeoutPromise = new Promise((_, reject) => 
      setTimeout(() => reject(new Error('Timeout: Server phản hồi quá lâu (>60s). Kiểm tra kết nối mạng!')), CONFIG.FETCH_TIMEOUT)
    );
    const response = await Promise.race([fetchPromise, timeoutPromise]);
    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `Lỗi HTTP ${response.status}`);
    }
    const data = await response.json();
    lastResult = data;
    selectedIndex = 0; // Luôn mặc định chọn kết quả tốt nhất khi mới nhận diện
    renderResult(data);
    await loadHistory();    // Tải lại lịch sử sau mỗi lần nhận diện
  } catch (err) {
    console.error('[Flower Note] Predict error:', err);
    if (err.name === 'TypeError' && err.message.includes('fetch')) {
      showToast('❌ Không kết nối được server. Kiểm tra backend đã chạy và ngrok URL đúng chưa?', 'error');
    } else if (err.message.includes('Timeout')) {
      showToast(`❌ ${err.message}`, 'error');
    } else {
      showToast(`❌ ${err.message}`, 'error');
    }
  } finally {
    setLoading(false);
  }
}

/* ════════════════════════════════════════════════
   LOAD PLANT DETAIL DATA FROM API
════════════════════════════════════════════════ */
async function loadPlantDetailData(plantId) {
  try {
    // Chuyển class_id thành string để khớp với key trong JSON
    const plantIdStr = String(plantId);
    console.log(`🔍 Loading plant detail for plantId: ${plantId} (type: ${typeof plantId}) -> plantIdStr: ${plantIdStr}`);
    
    const url = `${CONFIG.API_BASE}/api/plants/detail/${plantIdStr}`;
    console.log(`📡 Fetching from: ${url}`);
    
    const response = await fetch(url);
    console.log(`📊 Response status: ${response.status}`);
    
    if (!response.ok) {
      const errorText = await response.text();
      console.warn(`⚠️ Không load được dữ liệu chi tiết cho loài cây ${plantId} - Status: ${response.status}, Error: ${errorText}`);
      return;
    }
    
    const data = await response.json();
    console.log(`✅ Dữ liệu chi tiết nhận được:`, data);
    
    // Cập nhật các trường thông tin
    if (data.description) resDesc.textContent = data.description;
    if (data.benefits) resUses.textContent = data.benefits;
    if (data.light_requirement) resChars.textContent = `☀️ ${data.light_requirement}`;
    if (data.water_requirement) resCare.textContent = `💧 ${data.water_requirement}`;
    if (data.toxicity) resWarnText.textContent = data.toxicity;
    
    // Nếu có thông tin độc tính cảnh báo, hiển thị tab cảnh báo
    if (data.toxicity && data.toxicity.toLowerCase().includes('độc')) {
      tabWarn.classList.remove('hidden');
    }
    
    console.log(`✅ Đã load dữ liệu chi tiết cho loài: ${data.common_name}`);
  } catch (error) {
    console.error(`❌ Lỗi load dữ liệu chi tiết:`, error);
  }
}

/* ════════════════════════════════════════════════
   RENDER RESULT
════════════════════════════════════════════════ */
function renderResult(data) {
  if (!data || !data.all_detections || data.all_detections.length === 0) {
    showToast('🔍 Không phát hiện cây nào. Thử ảnh khác nhé!', 'error');
    return;
  }

  /* ── Đồng bộ ảnh gốc sang kết quả ── */
  resultImg.src = previewImg.src;

  /* ── Chọn kết quả hiển thị mặc định (index 0) ── */
  selectDetection(0);

  /* ── Scroll ── */
  setTimeout(() => { resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' }); }, 120);

  /* ── Toast ── */
  showToast(`✅ Nhận diện thành công: ${data.plant_name}!`);
}

function selectDetection(index) {
  if (!lastResult || !lastResult.all_detections[index]) return;
  
  selectedIndex = index;
  const det = lastResult.all_detections[index];
  const {
    plant_name,
    class_id,
    confidence,
    description_placeholder,
    scientific_name,
    characteristics,
    uses,
    care,
    warning
  } = det;

  /* ── Cập nhật theme ── */
  const theme = getThemeByPlantName(plant_name);
  updateTheme(theme);

  /* ── Tên cây + emoji ── */
  resName.textContent       = plant_name;
  resPlantEmoji.textContent = getPlantEmoji(plant_name);

  /* ── Tên khoa học ── */
  resScientific.textContent = scientific_name ? `✦ ${scientific_name}` : '';

  /* ── Confidence bar ── */
  const pct = Math.round(confidence * 100);
  resConfText.textContent = `${pct}%`;
  resConfBar.style.width = `${pct}%`;

  resConfGrade.className = 'conf-grade';
  if (pct >= 75) {
    resConfGrade.textContent = '✅ Độ tin cao';
    resConfGrade.classList.add('grade-high');
  } else if (pct >= 45) {
    resConfGrade.textContent = '⚠️ Trung bình';
    resConfGrade.classList.add('grade-medium');
  } else {
    resConfGrade.textContent = '❓ Không chắc';
    resConfGrade.classList.add('grade-low');
  }

  /* ── Tab nội dung ── */
  resDesc.textContent  = description_placeholder || '–';
  resChars.textContent = characteristics || 'Chưa có thông tin đặc điểm nhận dạng.';
  resUses.textContent  = uses  || 'Chưa có thông tin công dụng.';
  resCare.textContent  = care  || 'Chưa có thông tin chăm sóc.';

  /* ── Cảnh báo ── */
  if (warning) {
    resWarnText.textContent = warning;
    tabWarn.classList.remove('hidden');
  } else {
    tabWarn.classList.add('hidden');
  }

  /* ── Tải dữ liệu chi tiết từ API ── */
  if (class_id !== undefined && class_id !== null) {
    loadPlantDetailData(class_id);
  }

  /* ── Refresh UI components ── */
  renderDetectionsList(lastResult.all_detections, det.bbox);
  
  const drawBoxes = () => {
    drawBoundingBoxes(resultCanvas, resultImg, lastResult.all_detections, det.bbox);
  };
  
  if (resultImg.complete && resultImg.naturalWidth > 0) drawBoxes();
  else resultImg.onload = drawBoxes;

  /* ── Sync processing time ── */
  if (lastResult.processing_time_ms != null) {
    processingTime.textContent = lastResult.processing_time_ms < 1000
      ? `${lastResult.processing_time_ms} ms`
      : `${(lastResult.processing_time_ms / 1000).toFixed(2)} s`;
  }

  // Detection badge
  detectionCount.textContent = lastResult.all_detections.length;
  detectionBadge.style.display = lastResult.all_detections.length > 0 ? 'flex' : 'none';

  // Card visibility
  resultCard.style.display = 'block';
  requestAnimationFrame(() => resultCard.classList.add('visible'));
}

/* ════════════════════════════════════════════════
   TAB SWITCHING
════════════════════════════════════════════════ */
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    const isActive = btn.dataset.tab === tabId;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive);
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `panel-${tabId}`);
  });
}

// Gắn click cho tất cả tab buttons
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => switchTab(btn.dataset.tab));
});

/* ════════════════════════════════════════════════
   RENDER DETECTIONS LIST
════════════════════════════════════════════════ */
function renderDetectionsList(detections, bestBbox) {
  detectionsList.innerHTML = '';

  if (detections.length === 0) {
    allDetectionsWrap.classList.remove('show');
    return;
  }

  const sorted = [...detections].sort((a, b) => b.confidence - a.confidence);
  sorted.forEach((det, idx) => {
    const isSelected = bestBbox && arrEqual(det.bbox, bestBbox);
    const item   = document.createElement('div');
    item.className = `detection-item${isSelected ? ' is-best active' : ''}`;
    item.style.animationDelay = `${idx * 60}ms`;
    item.innerHTML = `
      <span class="detection-rank">${idx + 1}</span>
      <span class="detection-name">${det.plant_name}</span>
      <span class="detection-conf">${Math.round(det.confidence * 100)}%</span>
    `;
    item.addEventListener('click', () => {
      // Tìm index gốc trong detections để gọi selectDetection
      const originalIdx = detections.findIndex(d => arrEqual(d.bbox, det.bbox));
      if (originalIdx !== -1) selectDetection(originalIdx);
    });
    detectionsList.appendChild(item);
  });

  allDetectionsWrap.classList.add('show');
}

/* ════════════════════════════════════════════════
   HISTORY – LOAD FROM API
════════════════════════════════════════════════ */
async function loadHistory() {
  try {
    const res  = await fetch(CONFIG.API_HISTORY, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) return;
    const data = await res.json();
    renderHistory(data);
  } catch (e) {
    console.warn('[History] Không tải được lịch sử:', e);
  }
}

function renderHistory(items) {
  // Xóa cards cũ (giữ lại historyEmpty)
  Array.from(historyList.children).forEach(child => {
    if (child !== historyEmpty) child.remove();
  });

  if (!items || items.length === 0) {
    historyEmpty.style.display = 'flex';
    return;
  }
  historyEmpty.style.display = 'none';

  items.forEach((item, idx) => {
    const card = document.createElement('div');
    card.className = 'history-card';
    card.style.animationDelay = `${idx * 40}ms`;

    const ts = new Date(item.timestamp);
    const timeStr = ts.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
    const dateStr = ts.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit' });

    card.innerHTML = `
      <div class="history-card-name">${getPlantEmoji(item.plant_name)} ${item.plant_name}</div>
      <div class="history-card-sci">${item.scientific_name || 'Chưa có tên khoa học'}</div>
      <div class="history-card-meta">
        <span class="history-card-conf">${Math.round(item.confidence * 100)}%</span>
        <span class="history-card-time">⚡${item.processing_time_ms}ms · ${timeStr} ${dateStr}</span>
      </div>
    `;

    // Click to re-view history
    card.addEventListener('click', async () => {
      try {
        const res = await fetch(`${CONFIG.API_BASE}/api/history/${item.id}`);
        if (!res.ok) throw new Error('Không tải được chi tiết lịch sử');
        const detail = await res.json();
        
        // Restore state
        lastResult = {
          plant_name: detail.plant_name,
          scientific_name: detail.scientific_name,
          confidence: detail.confidence,
          all_detections: detail.all_detections,
          bbox: detail.bbox,
          processing_time_ms: detail.processing_time_ms
        };
        
        resultImg.src = detail.image_base64;
        selectedIndex = 0;
        
        // Render again
        renderResult(lastResult);
        
        // Scroll to result
        resultCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      } catch (err) {
        showToast('❌ Lỗi: ' + err.message, 'error');
      }
    });

    historyList.appendChild(card);
  });
}

// Nút ẩn history section
btnClearHistory.addEventListener('click', () => {
  $('history-section').style.display = 'none';
});

/* ════════════════════════════════════════════════
   BOUNDING BOX CANVAS
════════════════════════════════════════════════ */
function drawBoundingBoxes(canvas, img, detections, bestBbox) {
  const rect  = img.getBoundingClientRect();
  const dispW = rect.width;
  const dispH = rect.height;
  const natW  = img.naturalWidth;
  const natH  = img.naturalHeight;

  if (!dispW || !dispH || !natW || !natH) return;

  const scale    = Math.min(dispW / natW, dispH / natH);
  const imgRendW = natW * scale;
  const imgRendH = natH * scale;
  const offsetX  = (dispW - imgRendW) / 2;
  const offsetY  = (dispH - imgRendH) / 2;

  canvas.width  = dispW;
  canvas.height = dispH;

  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, dispW, dispH);

  const sorted = [...detections].sort((a, b) => {
    const aB = bestBbox && arrEqual(a.bbox, bestBbox);
    const bB = bestBbox && arrEqual(b.bbox, bestBbox);
    return aB - bB;
  });

  sorted.forEach((det) => {
    const isBest = bestBbox && arrEqual(det.bbox, bestBbox);
    const [x1n, y1n, x2n, y2n] = det.bbox;
    const x1 = offsetX + x1n * imgRendW;
    const y1 = offsetY + y1n * imgRendH;
    const x2 = offsetX + x2n * imgRendW;
    const y2 = offsetY + y2n * imgRendH;
    const bw = x2 - x1;
    const bh = y2 - y1;

    if (isBest) {
      ctx.fillStyle = THEME_COLORS[currentTheme].fill;
      ctx.beginPath(); ctx.roundRect(x1, y1, bw, bh, 10); ctx.fill();
      ctx.strokeStyle = THEME_COLORS[currentTheme].stroke; ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.setLineDash([]);
      ctx.beginPath(); ctx.roundRect(x1, y1, bw, bh, 10); ctx.stroke();
      drawLabel(ctx, det, x1, y1, y2, dispW, true);
    } else {
      ctx.fillStyle   = 'rgba(100, 100, 100, 0.05)';
      ctx.strokeStyle = 'rgba(100, 100, 100, 0.3)';
      ctx.lineWidth   = 1.5; ctx.lineJoin = 'round'; ctx.setLineDash([5, 4]);
      ctx.beginPath(); ctx.roundRect(x1, y1, bw, bh, 8); ctx.fill(); ctx.stroke();
      ctx.setLineDash([]);
    }
  });
}

function drawLabel(ctx, det, x1, y1, y2, dispW) {
  const label    = `${det.plant_name}  ${Math.round(det.confidence * 100)}%`;
  const fontSize = Math.max(11, Math.min(14, dispW / 40));
  ctx.font = `bold ${fontSize}px "Nunito", sans-serif`;
  const textW = ctx.measureText(label).width + 14;
  const tagH  = fontSize + 12;
  const tagY  = y1 - tagH - 6 < 0 ? y2 + 6 : y1 - tagH - 6;
  const tagX  = Math.max(0, Math.min(x1, dispW - textW));
  ctx.fillStyle = THEME_COLORS[currentTheme].label;
  ctx.beginPath(); ctx.roundRect(tagX, tagY, textW, tagH, 7); ctx.fill();
  ctx.fillStyle = '#FFFFFF'; ctx.textBaseline = 'top';
  ctx.fillText(label, tagX + 7, tagY + 6);
}

/* ════════════════════════════════════════════════
   HELPERS
════════════════════════════════════════════════ */
function arrEqual(a, b) {
  if (!a || !b || a.length !== b.length) return false;
  return a.every((v, i) => Math.abs(v - b[i]) < 1e-4);
}

function clearCanvas(canvas) {
  if (!canvas) return;
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

function setLoading(active) {
  btnPredict.disabled = active;
  if (active) {
    loadingOverlay.classList.add('active');
    hideResult();
    loadingBar.style.animation = 'none';
    loadingBar.offsetHeight;   // reflow
    loadingBar.style.animation = '';
  } else {
    loadingOverlay.classList.remove('active');
  }
}

function hideResult() {
  resultCard.classList.remove('visible');
  resultCard.style.display = 'none';
}

function resetState() {
  currentFile = null;
  previewImg.src = ''; previewContainer.style.display = 'none';
  clearCanvas(previewCanvas); fileInput.value = '';
  clearResults();
  btnHintText.textContent = '💡 Chọn ảnh trước để bắt đầu nhận diện';
  btnHintText.style.color = '';
}

function clearResults() {
  lastResult = null;
  selectedIndex = 0;
  
  if (resultImg) resultImg.src = '';
  clearCanvas(resultCanvas);
  
  if (resName) resName.textContent = '...';
  if (resScientific) resScientific.textContent = '';
  if (resConfText) resConfText.textContent = '0%';
  if (resConfBar) resConfBar.style.width = '0%';
  
  // Clear tabs
  [resDesc, resChars, resUses, resCare, resWarnText].forEach(el => {
    if (el) el.textContent = '';
  });
  
  if (detectionsList) detectionsList.innerHTML = '';
  if (allDetectionsWrap) allDetectionsWrap.classList.remove('show');
  if (detectionBadge) detectionBadge.style.display = 'none';
  
  hideResult();
}

function showToast(message, type = 'normal') {
  toast.textContent = message;
  toast.className   = type === 'error' ? 'show error' : 'show';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toast.classList.remove('show', 'error'); }, 3500);
}

let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    if (lastResult?.all_detections?.length > 0 && resultCard.classList.contains('visible')) {
      const currentBbox = lastResult.all_detections[selectedIndex].bbox;
      drawBoundingBoxes(resultCanvas, resultImg, lastResult.all_detections, currentBbox);
    }
    clearCanvas(previewCanvas);
  }, 200);
});

/* ════════════════════════════════════════════════
   INIT
════════════════════════════════════════════════ */

function setupEventListeners() {
  console.log('[setupEventListeners] Starting...');
  
  // ── PREDICT BUTTONS ──
  if (btnPredict) {
    btnPredict.addEventListener('click', async () => {
      console.log('[Event] btnPredict clicked');
      if (currentInputMode === 'url') {
        if (!urlInput.value.trim()) { showToast('🔗 Vui lòng dán đường dẫn ảnh!', 'error'); urlInput.focus(); return; }
      } else {
        if (!currentFile) { showToast('🌸 Vui lòng chọn ảnh trước nhé!', 'error'); return; }
      }
      console.log('[Event] Starting prediction...');
      await runPrediction();
    });
    addTouchFeedback(btnPredict);
    console.log('✅ btnPredict listeners attached');
  }

  if (btnRepredict) {
    btnRepredict.addEventListener('click', async () => {
      console.log('[Event] btnRepredict clicked');
      if (currentInputMode === 'url' && urlInput.value.trim()) await runPrediction();
      else if (currentFile) await runPrediction();
    });
    addTouchFeedback(btnRepredict);
    console.log('✅ btnRepredict listeners attached');
  }

  if (btnRetry) {
    btnRetry.addEventListener('click', () => {
      console.log('[Event] btnRetry clicked');
      resetState();
      if (currentInputMode === 'file') {
        dropZone.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(() => dropZone.focus(), 400);
      } else if (currentInputMode === 'url') {
        urlInput.value = '';
        urlInput.focus();
      }
    });
    addTouchFeedback(btnRetry);
    console.log('✅ btnRetry listeners attached');
  }

  // ── TAB BUTTONS ──
  console.log('[setupEventListeners] uploadTabBtns found:', uploadTabBtns.length);
  uploadTabBtns.forEach(btn => {
    console.log('[setupEventListeners] Adding click listener to tab:', btn.dataset.upmode);
    btn.addEventListener('click', () => {
      console.log('[Event] Tab clicked:', btn.dataset.upmode);
      const mode = btn.dataset.upmode;
      if (mode === currentInputMode) return;
      currentInputMode = mode;

      uploadTabBtns.forEach(b => {
        const active = b.dataset.upmode === mode;
        b.classList.toggle('active', active);
        b.setAttribute('aria-selected', active);
      });

      uploadPanels.forEach(p => {
        p.classList.toggle('active', p.id === `upanel-${mode}`);
      });

      if (mode === 'webcam') {
        console.log('[Event] Starting webcam...');
        startWebcam();
      } else {
        console.log('[Event] Stopping webcam...');
        stopWebcam();
      }

      resetState();
      if (mode === 'url') {
        btnHintText.textContent = '💡 Dán địa chỉ hình ảnh (URL) và nhấn Nhận diện ngay';
      } else if (mode === 'webcam') {
        btnHintText.textContent = '💡 Hãy cười lên và chụp một bức ảnh nào!';
      }
    });
    addTouchFeedback(btn);
  });
  console.log('✅ Tab buttons listeners attached');

  // ── CAPTURE BUTTON ──
  if (btnCapture) {
    btnCapture.addEventListener('click', () => {
      console.log('[Event] btnCapture clicked');
      if (!webcamStream) return;
      webcamCanvas.width = webcamVideo.videoWidth;
      webcamCanvas.height = webcamVideo.videoHeight;
      const ctx = webcamCanvas.getContext('2d');
      
      ctx.translate(webcamCanvas.width, 0);
      ctx.scale(-1, 1);
      ctx.drawImage(webcamVideo, 0, 0, webcamCanvas.width, webcamCanvas.height);
      
      webcamCanvas.toBlob(blob => {
        const file = new File([blob], `webcam_${Date.now()}.jpg`, { type: 'image/jpeg' });
        handleFile(file);
        showToast('📸 Đã chụp xong, nhấn "Nhận diện ngay" nhé!');
      }, 'image/jpeg', 0.9);
    });
    addTouchFeedback(btnCapture);
    console.log('✅ btnCapture listeners attached');
  }

  // ── OTHER BUTTONS ──
  if (removeImgBtn) {
    removeImgBtn.addEventListener('click', (e) => { 
      console.log('[Event] removeImgBtn clicked');
      e.stopPropagation(); 
      resetState(); 
    });
    addTouchFeedback(removeImgBtn);
    console.log('✅ removeImgBtn listeners attached');
  }

  console.log('[setupEventListeners] ✅ ALL EVENT LISTENERS ATTACHED');
}

(function init() {
  console.log('%c🌸 FLOWER NOTE INITIALIZING...', 'color: #FF6B8B; font-weight: bold; font-size: 14px;');
  
  console.log('✅ Setting up event listeners...');
  setupEventListeners();
  
  startHealthCheck();
  console.log('✅ Health check started');
  
  previewContainer.style.display = 'none';
  hideResult();
  console.log('✅ UI initialized');
  
  loadHistory();   // Tải lịch sử khi mở trang
  console.log('✅ History loaded');
  
  updateTheme('leaf'); // Mặc định chuyển sang nature theme khi bắt đầu
  console.log('✅ Theme updated');

  console.info(
    `%c${THEME_CONFIG[currentTheme].mainEmoji} Flower Note v3.0 %c– Dynamic Nature Themes`,
    `background:${THEME_COLORS[currentTheme].stroke};color:#fff;padding:4px 10px;border-radius:6px;font-weight:800;`,
    'color:var(--c-theme-600);font-weight:600;'
  );
  
  console.log('%c✅ ALL SYSTEMS READY! Use your browser console for debugging.', 'color: #4CAF50; font-weight: bold; font-size: 12px;');
  console.log('Buttons ready:', {
    btnPredict: !!btnPredict,
    btnRepredict: !!btnRepredict,
    btnRetry: !!btnRetry,
    btnCapture: !!btnCapture,
    uploadTabBtns: uploadTabBtns.length
  });
})();
