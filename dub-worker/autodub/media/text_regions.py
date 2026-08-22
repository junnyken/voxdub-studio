"""Tự động phát hiện vùng chữ overlay trên video (mini-spec V5, xem
docs/PLAN.md) — CHỈ thay đổi NGUỒN toạ độ rectangle (từ "người dùng tự vẽ"
sang "OCR đề xuất"), KHÔNG đổi cách áp dụng blur (vẫn ffmpeg boxblur qua
``media.subtitle.build_filter_complex``, nhận đúng format
``{"x","y","w","h"}`` chuẩn hoá 0..1 mà style_dialog.py đã dùng từ trước —
không phải định dạng mới).

OCR chạy 100% local (RapidOCR, ONNX Runtime — cùng họ công nghệ VieNeu/
Paraformer đã dùng, không torch/paddlepaddle) — không gửi frame ra ngoài.
"""
from __future__ import annotations

from autodub.utils import setup_logging

logger = setup_logging("autodub.text_regions")

#: Gộp 2 vùng lại làm 1 khi độ chồng lấn (IoU) vượt ngưỡng này — chữ overlay
#: tĩnh (watermark, tiêu đề kênh) xuất hiện gần như nguyên vị trí qua nhiều
#: frame, chỉ lệch nhẹ do OCR không tuyệt đối ổn định.
_MERGE_IOU_THRESHOLD = 0.3
#: Biên nới thêm quanh mỗi box chữ phát hiện được (theo tỉ lệ w/h) — che
#: trọn cả phần đổ bóng/viền chữ mà OCR đôi khi cắt sát quá.
_PADDING_RATIO = 0.15


def _iou(a: dict, b: dict) -> float:
    """Intersection-over-union của 2 rectangle chuẩn hoá {x,y,w,h}."""
    ax1, ay1, ax2, ay2 = a["x"], a["y"], a["x"] + a["w"], a["y"] + a["h"]
    bx1, by1, bx2, by2 = b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    if ix2 <= ix1 or iy2 <= iy1:
        return 0.0
    inter = (ix2 - ix1) * (iy2 - iy1)
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def _union(a: dict, b: dict) -> dict:
    x1 = min(a["x"], b["x"])
    y1 = min(a["y"], b["y"])
    x2 = max(a["x"] + a["w"], b["x"] + b["w"])
    y2 = max(a["y"] + a["h"], b["y"] + b["h"])
    return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1,
            "confidence": max(a.get("confidence", 0), b.get("confidence", 0))}


def merge_regions(boxes: list[dict]) -> list[dict]:
    """Gộp các box chồng lấn (xuất hiện lặp lại qua nhiều frame) thành ít
    rectangle hơn, mỗi rectangle là hợp (union) của các box góp vào nó.

    Thuật toán đơn giản, đủ dùng cho vài chục box mỗi lượt quét (3 frame ×
    ~10 dòng chữ mỗi frame là trần thực tế): lặp gộp cặp có IoU cao nhất
    tới khi không còn cặp nào vượt ngưỡng.
    """
    regions = [dict(b) for b in boxes]
    changed = True
    while changed and len(regions) > 1:
        changed = False
        for i in range(len(regions)):
            for j in range(i + 1, len(regions)):
                if _iou(regions[i], regions[j]) >= _MERGE_IOU_THRESHOLD:
                    regions[i] = _union(regions[i], regions[j])
                    del regions[j]
                    changed = True
                    break
            if changed:
                break
    return regions


def _pad(region: dict) -> dict:
    pad_w = region["w"] * _PADDING_RATIO
    pad_h = region["h"] * _PADDING_RATIO
    x = max(0.0, region["x"] - pad_w / 2)
    y = max(0.0, region["y"] - pad_h / 2)
    w = min(1.0 - x, region["w"] + pad_w)
    h = min(1.0 - y, region["h"] + pad_h)
    return {"x": round(x, 4), "y": round(y, 4),
            "w": round(w, 4), "h": round(h, 4),
            "confidence": round(region.get("confidence", 0), 3)}


_engine = None  # RapidOCR instance, nạp lười — chỉ dùng ở đường in-process


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _detect_in_process(image_paths: list[str]) -> list[dict]:
    """Đường dự phòng: chạy OCR ngay trong tiến trình chính (dev, hoặc khi
    chưa cài .venv-ocr). Cần rapidocr-onnxruntime có sẵn trong venv hiện tại.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.warning("Thiếu Pillow — không đọc được kích thước ảnh để "
                       "chuẩn hoá toạ độ OCR")
        return []

    try:
        engine = _get_engine()
    except ImportError as e:
        logger.info(f"Chưa cài OCR ({e}) — chạy scripts/setup_ocr.py để bật "
                    "quét chữ tự động")
        return []

    boxes: list[dict] = []
    for image_path in image_paths:
        try:
            with Image.open(image_path) as im:
                width, height = im.size
        except OSError as e:
            logger.warning(f"Không đọc được ảnh để quét chữ ({e})")
            continue
        try:
            result, _elapse = engine(image_path)
        except Exception as e:  # noqa: BLE001 — OCR hỏng không được chặn cả lượt
            logger.warning(f"OCR lỗi ({e}) — bỏ qua, người dùng vẫn tự vẽ tay được")
            continue
        if not result:
            continue
        for box, text, confidence in result:
            if not text.strip():
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x1, x2 = min(xs), max(xs)
            y1, y2 = min(ys), max(ys)
            boxes.append({
                "x": x1 / width, "y": y1 / height,
                "w": (x2 - x1) / width, "h": (y2 - y1) / height,
                "confidence": float(confidence),
            })
    return boxes


def _detect_via_subprocess(image_paths: list[str], settings) -> list[dict] | None:
    """Đường chính: chạy OCR trong .venv-ocr cô lập (đúng convention của dự
    án — mọi engine nặng chạy subprocess riêng, xem docs/ARCH.md). Trả về
    None (không phải []) khi subprocess không dùng được, để caller biết mà
    rơi về đường in-process thay vì hiểu nhầm thành "quét xong, không thấy
    chữ".
    """
    import json
    import subprocess

    from autodub.utils import bundled_file

    if not settings.ocr_configured():
        return None
    cmd = [settings.ocr_venv_python_path(),
          bundled_file("autodub", "media", "text_regions_worker.py")]
    for path in image_paths:
        cmd += ["--image", path]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Worker OCR không chạy được ({e}) — thử in-process")
        return None
    if proc.returncode != 0:
        logger.warning(f"Worker OCR lỗi ({proc.stderr.strip()[:300]}) — "
                       "thử in-process")
        return None
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Worker OCR trả kết quả sai định dạng ({e})")
        return None
    if not data.get("ok"):
        logger.warning(f"Worker OCR báo lỗi: {data.get('error')}")
        return None
    return data.get("boxes") or []


def detect_text_regions(image_paths: list[str], settings=None) -> list[dict]:
    """Quét nhiều frame đại diện, gộp kết quả, trả về rectangle sẵn dùng
    trực tiếp cho ``blur_regions`` (cùng format style_dialog.py đã dùng).

    Ưu tiên chạy trong ``.venv-ocr`` (cô lập, đúng convention dự án);
    ``settings=None`` hoặc chưa cài .venv-ocr thì rơi về in-process (cần
    rapidocr-onnxruntime có sẵn trong venv hiện tại — dev/test).

    Trả về rỗng nếu không phát hiện chữ nào — KHÔNG tự bật tính năng blur
    khi video sạch (guardrail 4, mini-spec V5).
    """
    all_boxes = _detect_via_subprocess(image_paths, settings) if settings else None
    if all_boxes is None:
        all_boxes = _detect_in_process(image_paths)
    if not all_boxes:
        return []
    merged = merge_regions(all_boxes)
    return [_pad(r) for r in merged]
