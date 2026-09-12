"""Tự động phát hiện vùng chữ overlay trên video (mini-spec V5, xem
docs/PLAN.md) — CHỈ thay đổi NGUỒN toạ độ rectangle (từ "người dùng tự vẽ"
sang "OCR đề xuất"), KHÔNG đổi cách áp dụng blur (vẫn ffmpeg boxblur qua
``media.subtitle.build_filter_complex``, nhận đúng format
``{"x","y","w","h"}`` chuẩn hoá 0..1 mà style_dialog.py đã dùng từ trước —
không phải định dạng mới).

OCR chạy 100% local (RapidOCR, ONNX Runtime — cùng họ công nghệ VieNeu/
Paraformer đã dùng, không torch/paddlepaddle) — không gửi frame ra ngoài.

``read_text_regions()`` (mini-spec H2a, 08/09/2026) là lớp ĐỌC nội dung chữ
— khác hẳn ``detect_text_regions()`` ở trên, hàm đó CỐ Ý vứt bỏ nội dung
chữ đã đọc được (chỉ cần vùng để làm mờ/xoá, đúng mục tiêu V5). H2a thêm
đường đọc SONG SONG, tái dùng đúng engine/worker/subprocess hiện có, không
đổi contract của ``detect_text_regions()`` cho caller cũ (`style_dialog.py`)
— xem cờ ``doc_chu`` xuyên suốt tệp này: mặc định ``False`` giữ nguyên hành
vi cũ, chỉ khi gọi từ ``read_text_regions()`` mới bật lên.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

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
            "confidence": max(a.get("confidence", 0), b.get("confidence", 0)),
            # C50: gộp cả DANH SÁCH khung hình đã nhìn thấy vùng này — mất nó
            # là mất luôn thông tin "chữ xuất hiện lúc nào".
            "_anh": _tap_anh(a) | _tap_anh(b)}


def _tap_anh(box: dict) -> set:
    """Tập chỉ số khung hình mà box này đến từ đó."""
    if "_anh" in box:
        return set(box["_anh"])
    return {box["anh"]} if "anh" in box else set()


def merge_regions(boxes: list[dict]) -> list[dict]:
    """Gộp các box chồng lấn (xuất hiện lặp lại qua nhiều frame) thành ít
    rectangle hơn, mỗi rectangle là hợp (union) của các box góp vào nó.

    Thuật toán đơn giản, đủ dùng cho vài chục box mỗi lượt quét (3 frame ×
    ~10 dòng chữ mỗi frame là trần thực tế): lặp gộp cặp có IoU cao nhất
    tới khi không còn cặp nào vượt ngưỡng.
    """
    regions = []
    for b in boxes:
        r = dict(b)
        r["_anh"] = _tap_anh(b)
        regions.append(r)
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


#: Số khung tối thiểu một vùng phải xuất hiện thì mới coi là "chữ nằm lì".
#:
#: Bằng 2 chứ không cao hơn: quét chỉ lấy vài khung rải đều cả video, mà phụ đề
#: cháy thì mỗi câu chỉ sống vài giây nên rất dễ chỉ rơi vào một khung. Đòi
#: nhiều hơn là bỏ sót đúng thứ cần che.
KHUNG_TOI_THIEU = 2


def loc_theo_lap_lai(regions: list[dict], so_khung: int,
                     toi_thieu: int = KHUNG_TOI_THIEU) -> tuple[list[dict], int]:
    """Giữ vùng chữ NẰM LÌ qua nhiều khung; bỏ chữ chỉ trôi qua một khung.

    C63 — bằng chứng thật từ lượt chạy của chủ dự án (05-09): quét một cảnh
    phố đêm Trung Quốc đề xuất ~15 vùng, phần lớn là biển hiệu neon và cả mặt
    diễn viên. Bật "xoá chữ" rồi xuất ra thì nguyên mảng người bị kéo nhoè —
    tệ hơn hẳn mấy dòng chữ gốc.

    Phân biệt được hai loại bằng một dấu hiệu rẻ: **watermark và phụ đề cháy
    NẰM YÊN một chỗ**, nên khung nào cũng thấy ở cùng vị trí và được
    `merge_regions` gộp lại; **biển hiệu, chữ trên tường thì TRÔI QUA** theo
    máy quay, mỗi khung một chỗ, không gộp với ai.

    Trả về ``(vùng giữ lại, số vùng đã bỏ)``. Quét dưới 2 khung thì KHÔNG lọc:
    không có gì để so, lọc lúc đó chỉ là đoán bừa.
    """
    if so_khung < toi_thieu:
        return regions, 0
    giu = [r for r in regions if len(_tap_anh(r)) >= toi_thieu]
    return giu, len(regions) - len(giu)


def _pad(region: dict) -> dict:
    pad_w = region["w"] * _PADDING_RATIO
    pad_h = region["h"] * _PADDING_RATIO
    x = max(0.0, region["x"] - pad_w / 2)
    y = max(0.0, region["y"] - pad_h / 2)
    w = min(1.0 - x, region["w"] + pad_w)
    h = min(1.0 - y, region["h"] + pad_h)
    ra = {"x": round(x, 4), "y": round(y, 4),
          "w": round(w, 4), "h": round(h, 4),
          "confidence": round(region.get("confidence", 0), 3)}
    for khoa in ("t_start", "t_end"):
        if region.get(khoa) is not None:
            ra[khoa] = round(float(region[khoa]), 2)
    return ra


class ChuaCaiOcr(RuntimeError):
    """Không có bộ quét chữ nào chạy được — KHÁC HẲN "quét xong, không thấy chữ".

    C56, lỗi thật: trước đây cả hai ca đều trả `[]`, nên giao diện báo *"Không
    phát hiện chữ overlay nào trong video này"* cho người chưa cài OCR. Người
    dùng kết luận video mình sạch chữ rồi đi tiếp, trong khi tính năng đơn giản
    là chưa được cài. Bản `.exe` không bundle rapidocr nên đây là ca của **mọi
    người dùng chưa chạy bộ cài** — không phải ca hiếm.
    """


_engine = None  # RapidOCR instance, nạp lười — chỉ dùng ở đường in-process


def _get_engine():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _engine = RapidOCR()
    return _engine


def _detect_in_process(image_paths: list[str], *, doc_chu: bool = False,
                       thong_ke: dict | None = None) -> list[dict]:
    """Đường dự phòng: chạy OCR ngay trong tiến trình chính (dev, hoặc khi
    chưa cài .venv-ocr). Cần rapidocr-onnxruntime có sẵn trong venv hiện tại.

    ``doc_chu`` (mini-spec H2a): mặc định ``False`` — giữ NGUYÊN hành vi cũ
    cho `detect_text_regions()` (vứt nội dung chữ). Chỉ `read_text_regions()`
    gọi với ``doc_chu=True`` để mỗi box có thêm khoá ``"text"``. ``thong_ke``
    (nếu có) nhận đếm ``"anh_loi"`` — số ảnh OCR gọi lỗi, để bên gọi phân
    biệt "chạy xong, không thấy chữ" với "toàn bộ ảnh đều gọi lỗi".
    """
    try:
        from PIL import Image
    except ImportError as e:
        logger.warning("Thiếu Pillow — không đọc được kích thước ảnh để "
                       "chuẩn hoá toạ độ OCR")
        raise ChuaCaiOcr("Thiếu thư viện Pillow nên không quét chữ được") from e

    _bat_dau_khoi_dong = time.monotonic()
    try:
        engine = _get_engine()
    except ImportError as e:
        logger.info(f"Chưa cài OCR ({e}) — chạy scripts/setup_ocr.py để bật "
                    "quét chữ tự động")
        raise ChuaCaiOcr(
            "Chưa cài bộ quét chữ. Chạy «Cai dat nhan dien vung chu.bat» "
            "(hoặc scripts/setup_ocr.py) rồi quét lại") from e

    _giay_khoi_dong = time.monotonic() - _bat_dau_khoi_dong
    _bat_dau_quet = time.monotonic()
    boxes: list[dict] = []
    anh_loi = 0
    for chi_so_anh, image_path in enumerate(image_paths):
        try:
            with Image.open(image_path) as im:
                width, height = im.size
        except OSError as e:
            logger.warning(f"Không đọc được ảnh để quét chữ ({e})")
            anh_loi += 1
            continue
        try:
            result, _elapse = engine(image_path)
        except Exception as e:  # noqa: BLE001 — OCR hỏng không được chặn cả lượt
            logger.warning(f"OCR lỗi ({e}) — bỏ qua, người dùng vẫn tự vẽ tay được")
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
                "anh": chi_so_anh,   # C50 — xem chú thích ở worker
                "x": x1 / width, "y": y1 / height,
                "w": (x2 - x1) / width, "h": (y2 - y1) / height,
                "confidence": float(confidence),
            }
            if doc_chu:
                muc["text"] = text.strip()
            boxes.append(muc)
    if thong_ke is not None:
        thong_ke["anh_loi"] = anh_loi
        # E6 — tách khởi động engine khỏi phần quét từng khung. Hai phần này
        # phản ứng NGƯỢC nhau khi giảm số khung: phần mỗi-khung co theo tỉ
        # lệ, phần khởi động không nhúc nhích. Gộp làm một con số là không
        # trả lời được câu quyết định của cả mini-spec: "cắt khung có nhanh
        # lên không".
        thong_ke["khoi_dong_s"] = round(_giay_khoi_dong, 3)
        thong_ke["quet_s"] = round(time.monotonic() - _bat_dau_quet, 3)
    return boxes


#: Giây cho MỖI khung hình, cộng phần dư để nạp model lần đầu. Mốc 60 giây
#: cứng trước đây (mini-spec C49) là con số của một khung hình duy nhất: quét
#: 3 khung trên máy chậm là hết giờ oan, mà lời báo lại nói "worker không chạy
#: được" — sai hẳn nguyên nhân.
GIAY_MOI_KHUNG = 25.0
GIAY_DU_NAP_MODEL = 40.0


def _han_gio(so_khung: int) -> float:
    return GIAY_DU_NAP_MODEL + GIAY_MOI_KHUNG * max(1, so_khung)


def _detect_via_subprocess(image_paths: list[str], settings,
                           cancel_event=None, *, doc_chu: bool = False,
                           thong_ke: dict | None = None) -> list[dict] | None:
    """Đường chính: chạy OCR trong .venv-ocr cô lập (đúng convention của dự
    án — mọi engine nặng chạy subprocess riêng, xem docs/ARCH.md). Trả về
    None (không phải []) khi subprocess không dùng được, để caller biết mà
    rơi về đường in-process thay vì hiểu nhầm thành "quét xong, không thấy
    chữ".

    ``doc_chu``/``thong_ke``: xem chú thích ở `_detect_in_process` — cùng
    quy ước, mini-spec H2a.
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
    if doc_chu:
        cmd += ["--doc-chu"]
    han = _han_gio(len(image_paths))
    try:
        if cancel_event is None:
            proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                  timeout=han)
        else:
            # Có đường huỷ thì KHÔNG dùng subprocess.run: nó chặn cứng tới khi
            # xong hoặc hết giờ, bấm Dừng không có tác dụng gì (C49).
            proc = _chay_co_the_huy(cmd, han, cancel_event)
            if proc is None:
                logger.info("Người dùng dừng lượt quét chữ")
                return []
    except subprocess.TimeoutExpired:
        logger.warning("Worker OCR quá %.0f giây cho %d khung hình — bỏ qua",
                       han, len(image_paths))
        return None
    except OSError as e:
        logger.warning(f"Worker OCR không chạy được ({e}) — thử in-process")
        return None
    # `stdout`/`stderr` có thể là None: luồng đọc của subprocess chết giữa
    # chừng thì `communicate()` trả None cho luồng đó. Lỗi thật 11/09/2026
    # trên Windows — worker in chữ tiếng Việt, còn `text=True` KHÔNG kèm
    # `encoding` nên Python giải mã bằng bảng mã vùng (cp1252) và ném
    # `UnicodeDecodeError` trong luồng đọc. Hậu quả người dùng thấy:
    #
    #     'NoneType' object has no attribute 'strip'
    #
    # sau khi đã chờ hơn 3 phút — một câu không nói gì về nguyên nhân thật.
    # Nguyên nhân đã sửa ở chỗ gọi (thêm `encoding="utf-8"`), nhưng vẫn phải
    # phòng ở đây: luồng đọc còn có thể chết vì lý do khác.
    ra_chuan = proc.stdout or ""
    ra_loi = proc.stderr or ""
    if proc.returncode != 0:
        logger.warning(f"Worker OCR lỗi ({ra_loi.strip()[:300]}) — "
                       "thử in-process")
        return None
    if not ra_chuan.strip():
        logger.warning("Worker OCR không trả ra dòng nào (luồng đọc hỏng?) — "
                       "thử in-process")
        return None
    try:
        data = json.loads(ra_chuan.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"Worker OCR trả kết quả sai định dạng ({e})")
        return None
    if not data.get("ok"):
        logger.warning(f"Worker OCR báo lỗi: {data.get('error')}")
        return None
    if thong_ke is not None:
        thong_ke["anh_loi"] = int(data.get("anh_loi") or 0)
        # E6 — worker đo tách khởi động/quét (xem `text_regions_worker.py`).
        # Worker cũ chưa có hai khoá này thì bỏ trống, không đoán: một con số
        # bịa ở đây sẽ dẫn thẳng tới một quyết định thiết kế sai.
        for khoa in ("khoi_dong_s", "quet_s"):
            if data.get(khoa) is not None:
                thong_ke[khoa] = float(data[khoa])
    return data.get("boxes") or []


def _chay_co_the_huy(cmd: list[str], han_gio: float, cancel_event):
    """Chạy worker, cứ 0,2 giây ngó xem người dùng có bấm Dừng chưa.

    Trả về ``CompletedProcess`` khi xong, ``None`` khi bị huỷ; ném
    ``TimeoutExpired`` khi quá hạn — cùng hợp đồng với ``subprocess.run``.
    """
    import subprocess
    import time

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    het_han = time.monotonic() + han_gio
    while True:
        try:
            out, err = proc.communicate(timeout=0.2)
            return subprocess.CompletedProcess(cmd, proc.returncode, out, err)
        except subprocess.TimeoutExpired:
            pass
        if cancel_event.is_set():
            proc.kill()
            proc.communicate()
            return None
        if time.monotonic() > het_han:
            proc.kill()
            proc.communicate()
            raise subprocess.TimeoutExpired(cmd, han_gio)


def gan_khoang_thoi_gian(regions: list[dict], moc: list[float]) -> list[dict]:
    """Suy khoảng thời gian che cho từng vùng, từ các khung hình đã thấy nó.

    Vì sao (mini-spec C50): bộ lọc xuất video đã hỗ trợ ``t_start``/``t_end``
    từ lâu (``media/subtitle.py`` sinh ``enable='between(t,..)'``) nhưng lượt
    quét chưa bao giờ điền — nên MỌI vùng đều che suốt cả video. Với video
    dài, một dòng chữ chỉ hiện ở phút thứ 3 sẽ làm mờ luôn 40 phút còn lại.

    Vùng xuất hiện ở TẤT CẢ khung hình đã quét thì coi như chữ tĩnh (watermark,
    tên kênh) → che suốt, không gắn mốc: vừa đúng, vừa nhẹ cho ffmpeg.

    Vùng xuất hiện rời rạc thì mỗi chuỗi khung liền nhau thành một khoảng, nới
    ra nửa bước lấy mẫu mỗi phía — chữ có thể đã hiện trước và tắt sau cái
    khung ta chụp được.
    """
    if not moc or len(moc) < 2:
        return [dict(r) for r in regions]
    buoc = (max(moc) - min(moc)) / (len(moc) - 1)
    nua = buoc / 2
    ra = []
    for r in regions:
        anh = sorted(_tap_anh(r))
        if not anh or len(anh) >= len(moc):
            ra.append({k: v for k, v in r.items() if k != "_anh"})
            continue
        # Cắt thành các chuỗi khung liền nhau.
        chuoi, hien_tai = [], [anh[0]]
        for i in anh[1:]:
            if i == hien_tai[-1] + 1:
                hien_tai.append(i)
            else:
                chuoi.append(hien_tai)
                hien_tai = [i]
        chuoi.append(hien_tai)
        for c in chuoi:
            moi = {k: v for k, v in r.items() if k != "_anh"}
            moi["t_start"] = max(0.0, moc[c[0]] - nua)
            moi["t_end"] = moc[c[-1]] + nua
            ra.append(moi)
    return ra


def detect_text_regions(image_paths: list[str], settings=None,
                        cancel_event=None,
                        moc_thoi_gian: list[float] | None = None,
                        thong_ke: dict | None = None) -> list[dict]:
    """Quét nhiều frame đại diện, gộp kết quả, trả về rectangle sẵn dùng
    trực tiếp cho ``blur_regions`` (cùng format style_dialog.py đã dùng).

    Ưu tiên chạy trong ``.venv-ocr`` (cô lập, đúng convention dự án);
    ``settings=None`` hoặc chưa cài .venv-ocr thì rơi về in-process (cần
    rapidocr-onnxruntime có sẵn trong venv hiện tại — dev/test).

    Trả về rỗng nếu không phát hiện chữ nào — KHÔNG tự bật tính năng blur
    khi video sạch (guardrail 4, mini-spec V5).

    Ném :class:`ChuaCaiOcr` khi KHÔNG bộ quét nào chạy được (C56). Rỗng phải
    có nghĩa duy nhất là "đã quét, video sạch chữ" — trộn hai ca đó vào cùng
    một giá trị là cách chắc chắn để nói dối người dùng.
    """
    all_boxes = (_detect_via_subprocess(image_paths, settings, cancel_event)
                 if settings else None)
    if cancel_event is not None and cancel_event.is_set():
        return []
    if all_boxes is None:
        try:
            all_boxes = _detect_in_process(image_paths)
        except ChuaCaiOcr:
            # Có `.venv-ocr` mà vẫn rơi tới đây nghĩa là worker vừa hỏng, KHÔNG
            # phải chưa cài — bảo người dùng đi cài lại thứ họ đã cài là chỉ
            # sai đường.
            if settings is not None and settings.ocr_configured():
                raise ChuaCaiOcr(
                    "Bộ quét chữ đã cài nhưng lượt này không chạy được — xem "
                    "Nhật ký để biết lý do") from None
            raise
    if not all_boxes:
        return []
    merged = merge_regions(all_boxes)
    # C63 — bỏ chữ chỉ TRÔI QUA một khung (biển hiệu, chữ trên tường). Số bỏ
    # đi phải nói ra: lọc âm thầm thì lần sau vùng cần che biến mất mà không ai
    # hiểu vì sao.
    merged, da_bo = loc_theo_lap_lai(merged, len(image_paths))
    if thong_ke is not None:
        thong_ke["da_bo"] = da_bo
        thong_ke["so_khung"] = len(image_paths)
    if da_bo:
        logger.info("Bỏ %d vùng chỉ thấy ở một khung (chữ trôi qua, không "
                    "phải watermark/phụ đề cháy)", da_bo)
    if moc_thoi_gian:
        merged = gan_khoang_thoi_gian(merged, moc_thoi_gian)
    return [_pad(r) for r in merged]


# ======================================================================
# Lớp ĐỌC nội dung chữ — mini-spec H2a (08/09/2026, đóng gap audit H2)
# ======================================================================
#
# Đo thật trước khi chọn ngưỡng (không suy đoán): RapidOCR trên máy thử
# hiếm khi trả confidence thấp — kể cả chữ mờ/tương phản thấp vẫn ra
# ~0,96-0,99 (engine có xu hướng "đọc tự tin hoặc không phát hiện được
# vùng nào" hơn là đọc nửa vời). Ngưỡng dưới đây là khởi điểm hợp lý theo
# quy ước OCR phổ biến — CHƯA có đủ ca đọc-sai-mà-confidence-thấp để hiệu
# chỉnh chặt hơn, cần thêm dữ liệu thật từ các lượt H2a chạy sau.
#
# Giới hạn ĐÃ ĐO, KHÔNG do ngưỡng này bắt được: chữ tiếng Việt bị RapidOCR
# đọc MẤT DẤU THANH (model nhận dạng bundled sẵn — ch_PP-OCRv4 — không có
# tiếng Việt trong bộ ký tự) nhưng vẫn báo confidence CAO (đo thật: 0,90-
# 0,99 cho cả câu tiếng Việt đọc sai/mất dấu). Ngưỡng tin cậy KHÔNG phải
# tín hiệu cho lỗi này — xem docs/MINI-SPEC_H2a_OCR_Read_Layer_Gap.md.
NGUONG_TIN_CAY_DOC = 0.70

# --- Bộ đọc thay được (mini-spec H2b, 09/09/2026) ----------------------------
#
# Việc DÒ VÙNG chữ và việc ĐỌC NỘI DUNG chữ có nhu cầu khác hẳn nhau, nên tách
# thành hai thứ thay được độc lập. `detect_text_regions()` (làm mờ chữ) chỉ cần
# biết chữ NẰM ĐÂU — RapidOCR làm tốt, chạy offline, KHÔNG đổi gì ở đây.
#
# Chỉ đường ĐỌC mới cần đổi: RapidOCR không phát ra được dấu tiếng Việt (giới
# hạn từ điển của model, xem chú thích ở `NGUONG_TIN_CAY_DOC` và
# docs/MINI-SPEC_H2b_Doc_Chu_Co_Dau.md). Hằng số dưới đây để bên gọi chọn bộ
# đọc, thay vì ghim cứng một engine trong hàm.
BO_DOC_CUC_BO = "cuc_bo"
BO_DOC_MAY_CHU = "may_chu"
BO_DOC_HOP_LE = (BO_DOC_CUC_BO, BO_DOC_MAY_CHU)


class DocChuThatBai(RuntimeError):
    """OCR đã cài nhưng lượt ĐỌC CHỮ này gọi lỗi trên MỌI khung hình được
    đưa vào — khác hẳn :class:`ChuaCaiOcr` ("chưa cài gì cả") và khác
    trạng thái ``"no_text"`` ("đã chạy xong ít nhất 1 khung, không thấy
    chữ"). Guardrail 4 của H2a: bốn trạng thái không được trộn vào nhau.
    """


@dataclass
class QuanSatChu:
    """Một chữ đọc được, TẠI ĐÚNG một khung hình — KHÔNG gộp qua nhiều
    khung (Scope A của H2a: chưa đủ bằng chứng để bịa thuật toán gộp nội
    dung, khác `merge_regions()` vốn gộp theo VỊ TRÍ cho mục đích làm mờ,
    sai nếu dùng cho nội dung vì hai chữ khác nhau có thể cùng vị trí)."""

    text: str
    #: ``None`` khi bộ đọc không chấm điểm tin cậy (bộ đọc máy chủ, H2b) —
    #: KHÔNG điền 1.0 cho đủ chỗ: một điểm tin cậy bịa ra trông y hệt điểm
    #: đo thật, và mọi thứ đọc trường này sau đó đều tin nhầm.
    confidence: float | None
    x: float
    y: float
    w: float
    h: float
    frame_index: int
    timestamp_s: float | None
    source: str          # "subprocess" | "in_process" | "may_chu"
    status: str          # "ok" | "unconfirmed"


@dataclass
class KetQuaDocChu:
    """``trang_thai``: ``"co_chu"`` (thấy ít nhất 1 chữ) hoặc ``"no_text"``
    (chạy xong, không thấy gì). ``"unavailable"``/``"failed"`` KHÔNG phải
    giá trị của trường này — hai ca đó ném ngoại lệ (`ChuaCaiOcr`/
    `DocChuThatBai`), vì lúc đó không có "quan_sat" nào để đặt vào đây.
    """

    trang_thai: str
    quan_sat: list[QuanSatChu] = field(default_factory=list)
    #: Đo cho E6 — `{"khoi_dong_s": …, "moi_khung_s": …, "so_khung": …}`.
    #: Tách hai phần vì chúng phản ứng NGƯỢC nhau với việc giảm số khung:
    #: phần mỗi-khung co lại theo tỉ lệ, phần khởi động thì không nhúc nhích.
    #: Gộp làm một con số là không trả lời được câu "cắt khung có nhanh lên
    #: không" — mà đó là câu quyết định cả mini-spec E6.
    thoi_gian: dict = field(default_factory=dict)


def read_text_regions(
    image_paths: list[str], settings=None, cancel_event=None,
    moc_thoi_gian: list[float] | None = None,
    bo_doc: str = BO_DOC_CUC_BO, client=None, xin_phep=None,
) -> KetQuaDocChu:
    """Đọc NỘI DUNG chữ overlay tại từng khung hình — mini-spec H2a.

    Khác `detect_text_regions()` (hàm phía trên, dùng cho tính năng làm mờ/
    xoá chữ — KHÔNG đổi, vẫn vứt nội dung chữ như cũ): hàm này GIỮ LẠI chữ
    đã đọc được, để mini-spec H2 (Flow Blueprint, chưa build) có bằng chứng
    caption thật theo dòng thời gian.

    Trả về **quan sát THÔ, chưa gộp** — mỗi chữ đọc được ở một khung hình là
    MỘT mục riêng, gắn đúng ``frame_index``/``timestamp_s`` của khung đó.
    Không tự suy luận "chữ này là cùng một caption xuất hiện xuyên suốt
    K khung" — `merge_regions()` làm việc đó theo VỊ TRÍ, đúng cho mục đích
    làm mờ (không cần biết nội dung) nhưng SAI ở đây: hai caption khác nhau
    xuất hiện cùng một vùng màn hình (rất phổ biến — chữ luôn nằm đáy
    khung) sẽ bị gộp nhầm thành một nếu gộp theo vị trí.

    ``image_paths``/``moc_thoi_gian``: bên gọi tự quyết định mật độ lấy mẫu
    khung hình — KHÔNG dùng lại mật độ thưa của `detect_text_regions()`
    (5-24 khung rải đều CẢ VIDEO, dựng cho watermark/phụ đề cháy nằm yên
    nhiều giây). Đo thật 08/09: caption dài 0,5 giây bị bộ lấy mẫu thưa đó
    bỏ lọt HOÀN TOÀN (0/5 khung trúng); lấy mẫu mỗi 0,2-0,4 giây bắt được.
    Với ~1,2 giây/khung trên CPU (đo thật, ảnh 640×360), lấy mẫu dày cho cả
    một video dài là chi phí thật — bên gọi (mini-spec H2 sau này) tự cân
    đối theo độ dài video cần phân tích, hàm này không tự áp đặt.

    ``bo_doc`` (mini-spec H2b): chọn bộ ĐỌC nội dung. ``BO_DOC_CUC_BO`` (mặc
    định) giữ nguyên hành vi cũ — RapidOCR tại máy, miễn phí, offline, nhưng
    **không phát ra được dấu tiếng Việt** (giới hạn từ điển của model, xem
    chú thích ở `NGUONG_TIN_CAY_DOC`). ``BO_DOC_MAY_CHU`` đọc bằng mô hình
    nhìn ảnh trên máy chủ: ra dấu đúng, nhưng cần mạng + tốn Vox, nên bên gọi
    phải tự quyết định chứ hàm này không tự ý đổi. Bước DÒ VÙNG vẫn do
    RapidOCR chạy tại máy trong cả hai ca — máy chủ chỉ đọc lại nội dung của
    những khung THẬT SỰ đổi chữ (xem `autodub/media/doc_chu_may_chu.py`).

    Ném :class:`ChuaCaiOcr` khi chưa cài bộ OCR nào (unavailable — cùng
    điều kiện với `detect_text_regions()`); ném :class:`DocChuThatBai` khi
    cả hai đường subprocess lẫn in-process đều gọi lỗi trên MỌI khung hình
    (failed — khác "chạy xong, không thấy chữ").
    """
    if bo_doc not in BO_DOC_HOP_LE:
        raise ValueError(
            f"Bộ đọc không hợp lệ: {bo_doc!r} (chỉ nhận {BO_DOC_HOP_LE})")
    if not image_paths:
        return KetQuaDocChu(trang_thai="no_text", quan_sat=[])

    thong_ke: dict = {}
    nguon = "subprocess"
    _bat_dau_tong = time.monotonic()
    all_boxes = (_detect_via_subprocess(image_paths, settings, cancel_event,
                                        doc_chu=True, thong_ke=thong_ke)
                if settings else None)
    if cancel_event is not None and cancel_event.is_set():
        return KetQuaDocChu(trang_thai="no_text", quan_sat=[])
    if all_boxes is None:
        nguon = "in_process"
        thong_ke = {}
        try:
            all_boxes = _detect_in_process(image_paths, doc_chu=True,
                                           thong_ke=thong_ke)
        except ChuaCaiOcr:
            if settings is not None and settings.ocr_configured():
                raise ChuaCaiOcr(
                    "Bộ đọc chữ đã cài nhưng lượt này không chạy được — xem "
                    "Nhật ký để biết lý do") from None
            raise

    if thong_ke.get("anh_loi", 0) >= len(image_paths):
        raise DocChuThatBai(
            f"Đọc chữ lỗi trên toàn bộ {len(image_paths)} khung hình đưa "
            "vào — xem Nhật ký để biết lý do từng khung.")

    quan_sat = [
        QuanSatChu(
            text=box["text"], confidence=box["confidence"],
            x=box["x"], y=box["y"], w=box["w"], h=box["h"],
            frame_index=box["anh"],
            timestamp_s=(moc_thoi_gian[box["anh"]]
                        if moc_thoi_gian and box["anh"] < len(moc_thoi_gian)
                        else None),
            source=nguon,
            status=("ok" if box["confidence"] >= NGUONG_TIN_CAY_DOC
                   else "unconfirmed"),
        )
        for box in all_boxes
    ]

    if bo_doc == BO_DOC_MAY_CHU and quan_sat:
        # Nhập lười: `doc_chu_may_chu` kéo theo `saas_client`, mà module này
        # còn được dùng ở đường làm mờ chữ vốn chạy hoàn toàn offline.
        from autodub.media.doc_chu_may_chu import doc_lai_bang_may_chu
        quan_sat = doc_lai_bang_may_chu(
            quan_sat, image_paths, client=client, cancel_event=cancel_event,
            xin_phep=xin_phep)

    # Lượt chạy thật 12/09 (v3.17.14) trả về tệp chẩn đoán KHÔNG có
    # `khoi_dong_s`/`quet_s` dù mã đã có trong bản đó — chưa rõ vì sao. Ghi
    # thêm tổng đo ở TIẾN TRÌNH CHA làm mức chặn trên, và nói thẳng là chưa
    # tách được, để lượt sau còn lần ra. Tuyệt đối không suy ra hai phần từ
    # con số gộp này — một con số bịa ở đây dẫn thẳng tới quyết định sai.
    thoi_gian = {
        "duong": nguon,
        "so_khung": len(image_paths),
        **{k: thong_ke[k] for k in ("khoi_dong_s", "quet_s") if k in thong_ke},
    }
    thoi_gian["tong_o_tien_trinh_cha_s"] = round(
        time.monotonic() - _bat_dau_tong, 3)
    if "khoi_dong_s" not in thong_ke:
        thoi_gian["thieu_tach_khoi_dong"] = (
            "worker không báo `khoi_dong_s`/`quet_s` — chỉ có tổng, KHÔNG "
            "suy ra được cắt khung có rút ngắn thời gian không")
        logger.warning(
            "Worker OCR (%s) không báo thời gian khởi động/quét — E6 câu C.4 "
            "không trả lời được từ lượt này", nguon)
    return KetQuaDocChu(
        trang_thai=("co_chu" if quan_sat else "no_text"),
        quan_sat=quan_sat, thoi_gian=thoi_gian)
