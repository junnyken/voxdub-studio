"""Mini-spec V5 (docs/PLAN.md) — phát hiện tự động vùng chữ overlay (OCR)
để đề xuất blur_regions, thay vì bắt người dùng tự vẽ tay từ đầu.

Test merge_regions() thuần (không cần OCR thật) + test integration thật
qua RapidOCR trên ảnh tổng hợp (PIL vẽ chữ Trung bằng font CJK hệ thống)
+ video NÉN THẬT (ffmpeg libx264, không phải PNG tĩnh — Re-audit
2026-08-17, đóng tiếp gap "chưa video thật" đã ghi ở docs/TEST_LOG.md mục
V5: thêm chữ tiếng Việt có dấu, watermark có hiệu ứng mờ dần, phụ đề cứng
kiểu burn-in — 3 case CHƯA từng test trước đó). ffmpeg đã có sẵn trong CI
từ V38 (xem .github/workflows/test.yml) nên test video nén này chạy được
trong CI, không chỉ sandbox có cài thêm.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

from autodub.config import Settings
from autodub.media.text_regions import merge_regions, _iou

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from autodub.media.text_regions import detect_text_regions  # noqa: E402

# C56 — TRƯỚC ĐÂY tệp này mở đầu bằng `importorskip("rapidocr_onnxruntime")`,
# tức đòi OCR nằm trong VENV CHÍNH. Nhưng đường chính của sản phẩm là
# `.venv-ocr` (subprocess), và KHÔNG bộ cài nào đặt rapidocr vào venv chính —
# `scripts/setup_ocr.py` cố ý cài vào venv riêng. Hệ quả: cả tệp này **chưa bao
# giờ chạy**, kể cả sau khi cài đúng cách, kể cả trên CI. Tính năng quét chữ
# (V5, C48–C51) coi như không có test, mà nhìn bảng kết quả thì chỉ thấy màu
# xám "skipped" — một sắc thái của màu xanh.
#
# Nay: chạy được đường nào thì kiểm đường đó, ưu tiên đường THẬT.
_CO_OCR_VENV_CHINH = importlib.util.find_spec("rapidocr_onnxruntime") is not None
try:
    _CAI_DAT = Settings.load()
    _CO_VENV_OCR = bool(_CAI_DAT.ocr_configured())
except Exception:  # noqa: BLE001 — không đọc được cấu hình thì coi như chưa cài
    _CAI_DAT, _CO_VENV_OCR = None, False

can_ocr = pytest.mark.skipif(
    not (_CO_OCR_VENV_CHINH or _CO_VENV_OCR),
    reason="chưa cài OCR: chạy scripts/setup_ocr.py (.venv-ocr) hoặc "
           "pip install rapidocr-onnxruntime vào venv hiện tại")


def quet(paths: list[str]) -> list[dict]:
    """Quét bằng đường THẬT nếu có `.venv-ocr`, không thì in-process.

    Bọc lại thay vì gọi thẳng `detect_text_regions` để mọi test dưới đây tự
    động chạy trên đường mà bản `.exe` dùng, chứ không chỉ đường dev.
    """
    if _CO_VENV_OCR:
        return detect_text_regions(paths, settings=_CAI_DAT)
    return detect_text_regions(paths)

_CJK_FONT = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
_HAS_CJK_FONT = os.path.isfile(_CJK_FONT)
_HAS_FFMPEG = shutil.which("ffmpeg") is not None
_BARLOW_FONT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts", "BarlowCondensed-Regular.ttf")


# ------------------------------------------------------------- merge thuần --

def test_iou_no_overlap_is_zero():
    a = {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1}
    b = {"x": 0.5, "y": 0.5, "w": 0.1, "h": 0.1}
    assert _iou(a, b) == 0.0


def test_iou_identical_boxes_is_one():
    a = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    assert _iou(a, dict(a)) == pytest.approx(1.0)


def test_merge_regions_combines_overlapping_boxes():
    boxes = [
        {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.1, "confidence": 0.9},
        {"x": 0.12, "y": 0.11, "w": 0.2, "h": 0.1, "confidence": 0.95},
    ]
    merged = merge_regions(boxes)
    assert len(merged) == 1, "2 box chồng lấn nhiều phải gộp thành 1"


def test_merge_regions_keeps_separate_far_apart_boxes():
    boxes = [
        {"x": 0.0, "y": 0.0, "w": 0.1, "h": 0.1, "confidence": 0.9},
        {"x": 0.8, "y": 0.8, "w": 0.1, "h": 0.1, "confidence": 0.9},
    ]
    merged = merge_regions(boxes)
    assert len(merged) == 2, "2 box xa nhau không được gộp nhầm"


def test_merge_regions_empty_input():
    assert merge_regions([]) == []


# ------------------------------------------------- integration thật (RapidOCR) --

@can_ocr
def test_clean_image_detects_nothing(tmp_path):
    """Guardrail 4 (mini-spec V5): video sạch không được tự bật tính năng blur."""
    img = Image.new("RGB", (640, 360), (20, 20, 20))
    path = str(tmp_path / "clean.png")
    img.save(path)
    assert quet([path]) == []


@pytest.mark.skipif(not _HAS_CJK_FONT, reason="cần font CJK hệ thống để vẽ chữ Trung thử")
@can_ocr
def test_detects_overlay_text_on_synthetic_frame(tmp_path):
    img = Image.new("RGB", (1280, 720), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_CJK_FONT, 42)
    draw.text((950, 30), "频道水印", font=font, fill=(255, 255, 0))
    draw.text((80, 640), "今天分享一个超简单的家常菜做法", font=font, fill=(255, 255, 255))
    path = str(tmp_path / "frame.png")
    img.save(path)

    regions = quet([path])
    assert len(regions) == 2, f"phải phát hiện đúng 2 vùng chữ, ra {regions}"
    # Watermark góc trên-phải: x lớn, y nhỏ.
    top_right = max(regions, key=lambda r: r["x"])
    assert top_right["x"] > 0.6 and top_right["y"] < 0.2
    # Câu tiêu đề dưới: x nhỏ, y lớn.
    bottom_left = min(regions, key=lambda r: r["x"])
    assert bottom_left["x"] < 0.2 and bottom_left["y"] > 0.7


@pytest.mark.skipif(not _HAS_CJK_FONT, reason="cần font CJK hệ thống để vẽ chữ Trung thử")
@can_ocr
def test_same_watermark_across_frames_merges_into_one_region(tmp_path):
    """Chữ overlay tĩnh (watermark) xuất hiện gần nguyên vị trí qua nhiều
    frame — phải gộp thành 1 rectangle, không phải N rectangle trùng lặp."""
    font = ImageFont.truetype(_CJK_FONT, 42)
    paths = []
    for i, (bg, text2) in enumerate([
        ((30, 30, 30), "今天分享一个超简单的家常菜做法"),
        ((40, 40, 60), "记得点赞关注哦"),
        ((25, 35, 45), "喜欢的话别忘了订阅"),
    ]):
        img = Image.new("RGB", (1280, 720), bg)
        draw = ImageDraw.Draw(img)
        draw.text((950, 30 + i), "频道水印", font=font, fill=(255, 255, 0))
        draw.text((80, 640), text2, font=font, fill=(255, 255, 255))
        path = str(tmp_path / f"frame{i}.png")
        img.save(path)
        paths.append(path)

    regions = quet(paths)
    # Watermark gộp thành 1 (dù xuất hiện 3 lần) + vùng caption (nội dung đổi
    # theo từng frame nhưng vị trí gần giống nhau nên cũng gộp/gần gộp được).
    watermark_like = [r for r in regions if r["x"] > 0.6]
    assert len(watermark_like) == 1, (
        f"watermark lặp lại 3 frame phải gộp thành 1 vùng, ra {len(watermark_like)}: {regions}")


@pytest.mark.skipif(not _HAS_CJK_FONT, reason="cần font CJK hệ thống để vẽ chữ Trung thử")
@pytest.mark.skipif(
    not (_CO_OCR_VENV_CHINH and _CO_VENV_OCR),
    reason="cần CẢ hai đường mới so được: .venv-ocr (setup_ocr.py) và "
           "rapidocr-onnxruntime trong venv hiện tại")
def test_subprocess_path_matches_in_process_path(tmp_path):
    """Đường `.venv-ocr` (đường CHÍNH, bản .exe dùng) phải cho kết quả GIỐNG
    HỆT đường in-process.

    C56: bản trước giả lập venv bằng chính `sys.executable`, tức so đường
    in-process với... đường in-process chạy qua subprocess. Nay dùng
    `.venv-ocr` THẬT — mới là thứ đang so."""
    from autodub.media.text_regions import detect_text_regions

    img = Image.new("RGB", (1280, 720), (30, 30, 30))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(_CJK_FONT, 42)
    draw.text((950, 30), "频道水印", font=font, fill=(255, 255, 0))
    path = str(tmp_path / "frame.png")
    img.save(path)

    via_subprocess = detect_text_regions([path], settings=_CAI_DAT)
    via_in_process = detect_text_regions([path])
    assert len(via_subprocess) == 1
    assert via_subprocess == via_in_process


# --------------------------------------- video nén thật (Re-audio 2026-08-17) --

@pytest.mark.skipif(not _HAS_FFMPEG, reason="cần ffmpeg để dựng video nén thật")
@pytest.mark.skipif(not _HAS_CJK_FONT, reason="cần font CJK hệ thống")
@pytest.mark.skipif(not os.path.isfile(_BARLOW_FONT), reason="thiếu font dự án")
@can_ocr
def test_real_encoded_video_detects_vietnamese_and_faded_watermark(tmp_path):
    """Video NÉN THẬT (libx264, không phải PNG tĩnh) với 3 case CHƯA từng
    test trước Re-audit này: (1) tiêu đề tiếng Việt CÓ DẤU, (2) watermark
    Trung CÓ HIỆU ỨNG MỜ DẦN (alpha thay đổi theo thời gian, không phải
    trong suốt cố định), (3) phụ đề cứng kiểu burn-in (hộp nền mờ, giữa
    khung hình dưới) — đóng đúng 3 gap ghi trong docs/TEST_LOG.md mục V5
    "vẫn còn thiếu... chưa có phụ đề cứng/tiêu đề kênh"."""
    video_path = str(tmp_path / "real_test.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=3",
        "-vf",
        "noise=alls=15:allf=t+u,"
        f"drawtext=fontfile={_CJK_FONT}:text='频道水印 CHANNEL':"
        "fontcolor=white:fontsize=32:x=w-tw-20:y=30:"
        "alpha='0.4+0.4*sin(2*PI*t/3)',"
        f"drawtext=fontfile={_BARLOW_FONT}:text='Kênh Ẩm Thực Việt':"
        "fontcolor=yellow:fontsize=36:x=20:y=20:box=1:boxcolor=black@0.35:"
        "boxborderw=6,"
        f"drawtext=fontfile={_BARLOW_FONT}:"
        "text='Hôm nay mình hướng dẫn làm món ăn':fontcolor=white:"
        "fontsize=30:x=(w-text_w)/2:y=h-70:box=1:boxcolor=black@0.5:"
        "boxborderw=8",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", video_path,
    ], check=True, capture_output=True)

    frame_path = str(tmp_path / "frame.png")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", video_path,
        "-vf", "select=eq(n\\,45)", "-vsync", "0", "-frames:v", "1", frame_path,
    ], check=True, capture_output=True)

    regions = quet([frame_path])
    assert regions, "phải phát hiện được ít nhất 1 vùng chữ trên video nén thật"

    # Xác nhận bằng crop trực quan thay vì chỉ tin số lượng box (đúng
    # phương pháp Re-audit 08-11 đã dùng) — mọi vùng CÓ DIỆN TÍCH ĐỦ LỚN
    # (loại nhiễu/artefact nhỏ như timecode góc của testsrc2) phải nằm
    # trọn trong khung hình và không rỗng.
    img = Image.open(frame_path)
    w, h = img.size
    significant = [r for r in regions if r["w"] * r["h"] > 0.01]
    assert significant, f"không có vùng nào đủ lớn để là chữ thật: {regions}"
    for r in significant:
        assert 0.0 <= r["x"] <= 1.0 and 0.0 <= r["y"] <= 1.0
        assert r["x"] + r["w"] <= 1.05 and r["y"] + r["h"] <= 1.05

    # Vùng watermark (góc phải-trên, x lớn/y nhỏ) phải nằm trong số phát
    # hiện được dù đang ở giữa chu kỳ mờ dần (frame 45/90 = giữa video).
    watermark_like = [r for r in significant if r["x"] > 0.5 and r["y"] < 0.3]
    assert watermark_like, (
        f"không phát hiện được watermark đang mờ dần: {regions}")


@pytest.mark.skipif(not _HAS_FFMPEG, reason="cần ffmpeg để dựng video nén thật")
@can_ocr
def test_real_encoded_noisy_video_without_text_detects_nothing(tmp_path):
    """Guardrail 4 (mini-spec V5) trên nền THẬT phức tạp (nhiễu thời gian
    qua ffmpeg, không phải màu phẳng PIL) — video sạch không có chữ vẫn
    không được tự bật blur, kể cả khi nền không đơn sắc."""
    video_path = str(tmp_path / "clean_noisy.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=2",
        "-vf", "noise=alls=15:allf=t+u",
        "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", video_path,
    ], check=True, capture_output=True)

    frame_path = str(tmp_path / "frame.png")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", video_path,
        "-vf", "select=eq(n\\,20)", "-vsync", "0", "-frames:v", "1", frame_path,
    ], check=True, capture_output=True)

    assert quet([frame_path]) == []


# ------------------------------------------------ C56: rỗng ≠ chưa cài ---

def test_chua_cai_ocr_thi_NEM_LOI_chu_khong_bao_video_sach_chu(tmp_path, monkeypatch):
    """Bug thật C56, ảnh hưởng MỌI người dùng chưa chạy bộ cài.

    Chưa cài OCR thì `detect_text_regions` trả `[]`, và giao diện báo nguyên
    văn *"Không phát hiện chữ overlay nào trong video này."* — người dùng kết
    luận video mình sạch chữ rồi đi tiếp. Bản `.exe` không bundle rapidocr nên
    đây là đường mặc định, không phải ca hiếm.

    `[]` chỉ được phép có MỘT nghĩa: đã quét, không thấy gì.
    """
    from autodub.media import text_regions as tr

    def khong_co_engine():
        raise ImportError("No module named 'rapidocr_onnxruntime'")

    monkeypatch.setattr(tr, "_get_engine", khong_co_engine)
    img = Image.new("RGB", (320, 240), (10, 10, 10))
    path = str(tmp_path / "frame.png")
    img.save(path)

    with pytest.raises(tr.ChuaCaiOcr) as e:
        tr.detect_text_regions([path])
    assert "cài" in str(e.value).lower(), "lời báo phải nói việc cần làm"


def test_da_cai_ma_worker_hong_thi_KHONG_bao_la_chua_cai(tmp_path, monkeypatch):
    """Bảo người dùng đi cài lại thứ họ đã cài là chỉ sai đường."""
    from autodub.media import text_regions as tr

    monkeypatch.setattr(tr, "_detect_via_subprocess", lambda *a, **k: None)
    monkeypatch.setattr(tr, "_get_engine",
                        lambda: (_ for _ in ()).throw(ImportError("x")))

    class _CoVenvOcr:
        def ocr_configured(self):
            return True
        def __getattr__(self, ten):
            return lambda *a, **k: ""

    img = Image.new("RGB", (320, 240), (10, 10, 10))
    path = str(tmp_path / "frame.png")
    img.save(path)

    with pytest.raises(tr.ChuaCaiOcr) as e:
        tr.detect_text_regions([path], settings=_CoVenvOcr())
    assert "đã cài" in str(e.value), f"lời báo sai nguyên nhân: {e.value}"


@can_ocr
def test_quet_that_ma_khong_co_chu_van_tra_rong(tmp_path):
    """Nửa còn lại của hợp đồng: có engine + ảnh sạch = `[]`, không ném lỗi."""
    img = Image.new("RGB", (640, 360), (20, 60, 20))
    path = str(tmp_path / "sach.png")
    img.save(path)
    assert quet([path]) == []
