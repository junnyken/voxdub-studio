# Mini-spec V12 (docs/PLAN.md) — image RIÊNG cho worker Python (torch+demucs,
# ~1.5-2GB), tách khỏi control_server (Node) — guardrail 1: đổi gì bên
# Python không kéo theo build lại/redeploy control_server. Build context là
# gốc repo (docker-compose.yml context: .) để copy được cả
# autodub/media/demucs_worker.py lẫn control_server/worker/render_worker.py.
#
# CHỈ copy đúng 1 file cần từ autodub/ (demucs_worker.py tự nhận là KHÔNG
# import autodub — standalone) — không copy cả package autodub/autodub_gui
# (kéo theo PySide6 và hàng loạt phụ thuộc desktop không cần cho worker).

FROM python:3.12-slim AS runtime
WORKDIR /app

# soundfile bản wheel Linux (manylinux) đã gói sẵn libsndfile — không cần
# apt-get install libsndfile1 (đã xác nhận: pip install thành công và
# import soundfile chạy được trên image python-slim sạch, không cài thêm
# gì ở tầng hệ điều hành).
RUN pip install --no-cache-dir demucs>=4.0.0 soundfile>=0.13.0 requests>=2.31.0

COPY autodub/media/demucs_worker.py /app/autodub_media/demucs_worker.py
COPY control_server/worker/render_worker.py /app/render_worker.py

ENV DEMUCS_WORKER_SCRIPT=/app/autodub_media/demucs_worker.py
CMD ["python3", "render_worker.py"]
