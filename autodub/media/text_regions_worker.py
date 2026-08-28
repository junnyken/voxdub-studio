"""OCR worker — chạy TRONG venv riêng .venv-ocr (mini-spec V5, xem
docs/PLAN.md). Standalone script: KHÔNG import gì từ ``autodub`` (venv
khác) — đúng quy ước của asr_whisper_worker.py/vieneu_worker.py.

CLI:
    python text_regions_worker.py --image frame1.png --image frame2.png

stdout: 1 dòng JSON duy nhất
    {"ok": true, "boxes": [{"x":..,"y":..,"w":..,"h":..,"confidence":..}, ...]}
  | {"ok": false, "error": "..."}
"""
import argparse
import json
import sys

# Windows mặc định cho tiến trình con dùng bảng mã cp1252 khi ghi ra ống —
# in một chữ Việt có dấu là chết ngay giữa chừng với UnicodeEncodeError, và
# tiến trình cha chỉ thấy "worker kết thúc bất thường". Lỗi thật, xảy ra với
# người dùng 26/8/2026: chữ "Đ" làm hỏng cả lượt dịch ngoại tuyến.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")



def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", action="append", required=True,
                        dest="images")
    args = parser.parse_args()

    try:
        from PIL import Image
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        print(json.dumps({"ok": False, "error": f"Thiếu thư viện OCR ({e})"}))
        sys.exit(1)

    engine = RapidOCR()
    boxes = []
    for chi_so_anh, path in enumerate(args.images):
        try:
            with Image.open(path) as im:
                width, height = im.size
            result, _elapse = engine(path)
        except Exception as e:  # noqa: BLE001 — 1 ảnh hỏng không chặn cả lượt
            print(f"[ocr-worker] bỏ qua {path}: {e}", file=sys.stderr)
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
                # C50: box thuộc KHUNG HÌNH nào — để phía app biết chữ đó xuất
                # hiện ở khoảng thời gian nào, thay vì che cả video.
                "anh": chi_so_anh,
                "x": x1 / width, "y": y1 / height,
                "w": (x2 - x1) / width, "h": (y2 - y1) / height,
                "confidence": float(confidence),
            })

    print(json.dumps({"ok": True, "boxes": boxes}, ensure_ascii=False))


if __name__ == "__main__":
    main()
