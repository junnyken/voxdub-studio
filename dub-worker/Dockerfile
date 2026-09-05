# =============================================================
# FILE SINH TỰ ĐỘNG cho nhánh deploy/vays-dub-worker — KHÔNG sửa tay.
# Nguồn thật: control_server/worker-dub/Dockerfile trên main +
# scripts/gen_vays_dub_worker_branch.sh. Sửa ở đó rồi chạy lại script.
# Thư mục này (dub-worker/, GỐC repo) chỉ tồn tại trên nhánh
# deploy/vays-dub-worker — VAYS subdir chỉ nhận thư mục con Ở NGAY GỐC repo, không
# nhận đường dẫn lồng như control_server/worker-dub (xác nhận thật
# lúc deploy 2026-08-17).
# =============================================================

# Mini-spec V34a (docs/PLAN.md) — PoC hạ tầng API lồng tiếng đầy đủ
# (ASR+dịch+TTS+mux) chạy server-side, gọi thẳng `autodub.cli`/`DubPipeline`
# headless (V22) — KHÔNG viết lại pipeline riêng cho server (Design Choice).
#
# Image MỚI HOÀN TOÀN, TÁCH HẲN `control_server/worker/` (Demucs, V12) —
# Constraint 2 của V34a: 1 lỗi ở pipeline nặng không ảnh hưởng build/deploy
# control_server hay render_worker.
#
# Cài đủ autodub package + 3 venv riêng (đúng kiến trúc "mỗi engine nặng 1
# venv qua subprocess" đã có sẵn của app desktop, xem CLAUDE.md) — TÁI DÙNG
# NGUYÊN VĂN scripts/setup_whisper.py / setup_vieneu.py /
# setup_translate_local.py (KHÔNG viết lại logic cài đặt model):
#   .venv-whisper  ASR (faster-whisper, CPU)
#   .venv-vieneu   TTS tiếng Việt (VieNeu, ONNX, CPU)
#   .venv-mt       Dịch local/offline (NLLB-200-distilled-600M, CPU — dùng
#                  thay cho dịch qua máy chủ vì worker này KHÔNG có identity
#                  Device để gọi /v1/ai/*, và Constraint 1 của V34a cấm
#                  billing thật ở PoC — dịch local không tốn Vox nào)
#
# Mini-spec V34b (docs/PLAN.md): `bg-mode=demucs` (tách nhạc nền) giờ là
# tham số THẬT của API — đã live-verify thật ở audit V34b (video 77.7s có
# nhạc nền, 204.8s xử lý, CPU-only, không cần GPU — xem docs/TEST_LOG.md).
# demucs chạy TRỰC TIẾP trong venv chính (không phải venv con riêng — khớp
# đúng requirements.txt mục "BGM separation", app desktop cũng chạy demucs
# ở venv chính, không có `.venv-demucs` nào trong danh sách venv của
# autodub/config.py) nên cần torch ở ĐÂY, không phải venv phụ.
#
# Build context là gốc repo (docker-compose.yml context: .) để copy được cả
# autodub/ lẫn control_server/worker-dub/dub_worker.py.

FROM python:3.12-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# --- Core pipeline (main venv — nơi autodub.cli chạy trực tiếp) ---
# Đúng tập requirements.txt mục "Core pipeline", TRỪ PySide6 (cli.py tự
# đảm bảo không import GUI, xem test cách ly tests/test_cli.py) và TRỪ
# yt-dlp/playwright (không cần — input là file upload sẵn, không phải URL;
# autodub/media/downloader.py là nơi DUY NHẤT import yt_dlp ở top-level,
# không nằm trên đường gọi của CLI này). demucs+soundfile CÓ cài (V34b —
# xem ghi chú trên) dù mặc định API vẫn `bg-mode=none` (không đổi giá/hành
# vi cũ nếu caller không truyền bgMode).
#
# Bug thật tìm+sửa lúc build image cho V34b: `pip install demucs` mặc định
# kéo theo bản torch CÓ CUDA (~2.5 GB thư viện nvidia-*/triton hoàn toàn
# không dùng tới — container này đã live-verify chạy CPU-only, xem
# docs/TEST_LOG.md mục V34b). Cài torch bản CPU-ONLY TRƯỚC qua index riêng
# của PyTorch để demucs thấy đã thỏa mãn dependency, không tự kéo bản CUDA.
RUN pip install --no-cache-dir --retries 5 --timeout 180 \
    --index-url https://download.pytorch.org/whl/cpu \
    "torch>=2.0.0,<3.0"
RUN pip install --no-cache-dir --retries 5 --timeout 180 \
    "pydub>=0.25.1,<2.0" "numpy>=1.24,<3.0" "python-dotenv>=1.0.1,<2.0" \
    "requests>=2.31.0,<3.0" "cryptography>=42.0.0" \
    "demucs>=4.0.0,<5.0" "soundfile>=0.13.0,<0.14"

COPY autodub/ /app/autodub/
# `_python_ho_tro.py` là module dùng chung của ba script trên (V80) —
# liệt kê tay mà quên nó thì build chết ngay dòng import, đã sập thật
# hai lượt deploy liên tiếp 20-08.
COPY scripts/setup_whisper.py scripts/setup_vieneu.py \
     scripts/setup_translate_local.py scripts/_python_ho_tro.py \
     /app/scripts/

# Cài 3 engine nặng vào venv riêng NGAY lúc build (không phải lúc container
# khởi động) — image tự chứa, container chạy được không cần mạng lúc
# runtime. Mỗi script resume-safe + tự smoke-test (raise nếu cài sai).
RUN python3 scripts/setup_whisper.py
RUN python3 scripts/setup_translate_local.py
RUN python3 scripts/setup_vieneu.py

COPY dub_worker.py /app/dub_worker.py

# Dịch local/offline (path C, autodub/text/translate_local.py) — worker
# này không có identity Device để dùng path B (SaaS qua control_server),
# và Constraint 1 của V34a cấm billing thật nên không thể dùng CreditHold
# của path B dù có identity. Model NLLB đã tải sẵn ở bước setup_translate_local.
ENV TRANSLATE_LOCAL_ENABLED=true
ENV PYTHONUNBUFFERED=1

# Không phục vụ nghiệp vụ gì trên port này — chỉ để platform hosting
# (Vibe Host) health-check thấy container lắng nghe, xem HEALTH_PORT trong
# dub_worker.py.
EXPOSE 3000

CMD ["python3", "dub_worker.py"]
