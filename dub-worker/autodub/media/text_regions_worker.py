"""OCR worker — chạy TRONG venv riêng .venv-ocr (mini-spec V5, xem
docs/PLAN.md). Standalone script: KHÔNG import gì từ ``autodub`` (venv
khác) — đúng quy ước của asr_whisper_worker.py/vieneu_worker.py.

CLI:
    python text_regions_worker.py --image frame1.png --image frame2.png
    python text_regions_worker.py --image frame1.png --doc-chu   # + nội dung chữ

stdout: 1 dòng JSON duy nhất
    {"ok": true, "boxes": [{"x":..,"y":..,"w":..,"h":..,"confidence":..}, ...],
     "anh_loi": 0}
  | {"ok": false, "error": "..."}

``--doc-chu`` (mini-spec H2a, 08/09/2026): mặc định TẮT — giữ nguyên hành
vi cũ (vứt nội dung chữ, chỉ trả vùng) cho caller cũ
(`text_regions.detect_text_regions`, dùng cho tính năng làm mờ/xoá chữ).
Chỉ `text_regions.read_text_regions()` bật cờ này để mỗi box có thêm khoá
``"text"``. Không tính "status" (ok/unconfirmed) ở đây — worker không biết
ngưỡng tin cậy của phía gọi, tính tập trung ở `text_regions.py` cho cả
đường subprocess lẫn in-process, tránh hai nơi định nghĩa hai ngưỡng khác
nhau.
"""
import argparse
import json
import time
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
    parser.add_argument("--doc-chu", action="store_true", dest="doc_chu",
                        help="Giữ nội dung chữ đã đọc (mini-spec H2a)")
    args, _thua = parser.parse_known_args()
    if _thua:
        # C53 — tiến trình cha đời MỚI gửi tham số worker này chưa biết thì bỏ
        # qua và nói ra, KHÔNG chết. Lỗi thật 28/08: cha mới gửi `--ram-trong-gb`
        # xuống worker cũ, argparse sys.exit(2) và giết cả lượt lồng tiếng.
        print(f"Bỏ qua tham số không nhận ra: {' '.join(_thua)}",
              file=sys.stderr, flush=True)

    try:
        from PIL import Image
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as e:
        print(json.dumps({"ok": False, "error": f"Thiếu thư viện OCR ({e})"}))
        sys.exit(1)

    # E6 — đo RIÊNG hai phần. Nạp mô hình RapidOCR là chi phí CỐ ĐỊNH, không
    # nhúc nhích khi giảm số khung; phần quét thì co theo tỉ lệ. Gộp làm một
    # con số là không trả lời được câu quyết định của mini-spec E6: "cắt bớt
    # khung có làm nhanh lên không".
    _t0 = time.monotonic()
    engine = RapidOCR()
    khoi_dong_s = time.monotonic() - _t0

    _t1 = time.monotonic()
    boxes = []
    anh_loi = 0
    for chi_so_anh, path in enumerate(args.images):
        try:
            with Image.open(path) as im:
                width, height = im.size
            result, _elapse = engine(path)
        except Exception as e:  # noqa: BLE001 — 1 ảnh hỏng không chặn cả lượt
            print(f"[ocr-worker] bỏ qua {path}: {e}", file=sys.stderr)
            anh_loi += 1
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
            muc = {
                # C50: box thuộc KHUNG HÌNH nào — để phía app biết chữ đó xuất
                # hiện ở khoảng thời gian nào, thay vì che cả video.
                "anh": chi_so_anh,
                "x": x1 / width, "y": y1 / height,
                "w": (x2 - x1) / width, "h": (y2 - y1) / height,
                "confidence": float(confidence),
            }
            if args.doc_chu:
                # H2a: caller đặc biệt (read_text_regions) mới nhận trường
                # này — caller cũ (detect_text_regions, tính năng làm mờ/
                # xoá chữ) không bật cờ --doc-chu nên không thấy khoá này,
                # giữ nguyên contract cũ.
                muc["text"] = text.strip()
            boxes.append(muc)

    print(json.dumps({"ok": True, "boxes": boxes, "anh_loi": anh_loi,
                      "khoi_dong_s": round(khoi_dong_s, 3),
                      "quet_s": round(time.monotonic() - _t1, 3)},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
