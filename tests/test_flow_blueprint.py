"""Trích bằng chứng (ASR+OCR) cho Flow Blueprint — mini-spec H2 (docs/
PLAN.md, Phase H mới).

Test mật độ lấy mẫu thuần (không cần video thật) + gộp quan sát liên tiếp,
và MỘT lượt tích hợp thật (ffmpeg thật dựng video có phụ đề, OCR in-process
thật — `.venv-test` có rapidocr) với ASR giả lập (Whisper thật để dành cho
live verification cuối, không lặp lại ở mọi test đơn vị).
"""
from __future__ import annotations

import os
import shutil

import pytest

from autodub import flow_blueprint as fb
from autodub.config import Settings

_HAS_FFMPEG = shutil.which("ffmpeg") is not None
_BARLOW_FONT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts", "BarlowCondensed-Regular.ttf")


# ------------------------------------------------------- mật độ lấy mẫu ---

def test_video_rong_khong_co_moc_nao():
    assert fb.moc_lay_mau_thich_ung(0) == []
    assert fb.moc_lay_mau_thich_ung(-5) == []


def test_video_ngan_hon_10s_lay_mau_day_ca_video():
    """Hai đầu (0-5s, 5s cuối) chồng nhau ở video < 10s — lấy mẫu dày cho
    TOÀN BỘ thay vì để một khoảng giữa vô nghĩa."""
    moc = fb.moc_lay_mau_thich_ung(3.0)
    assert moc[0] == 0.0
    assert moc[-1] == 3.0
    # Toàn bộ video 3s dùng bước 0.2s -> khoảng 16 mốc, KHÔNG rơi về bước 0.5s.
    buoc = [round(moc[i + 1] - moc[i], 2) for i in range(len(moc) - 1)]
    assert all(b <= fb.GIAY_MOI_KHUNG_DAU_CUOI + 0.01 for b in buoc)


def test_video_90s_dung_ca_ba_doan():
    moc = fb.moc_lay_mau_thich_ung(90.0)
    assert moc[0] == 0.0
    assert moc[-1] == 90.0
    # Đoạn đầu (0-5s) phải dày hơn hẳn đoạn giữa (quanh 45s).
    dau = [m for m in moc if m <= 5.0]
    giua = [m for m in moc if 40.0 <= m <= 50.0]
    buoc_dau = (dau[-1] - dau[0]) / (len(dau) - 1)
    buoc_giua = (giua[-1] - giua[0]) / (len(giua) - 1)
    assert buoc_dau < buoc_giua


def test_khong_bo_lot_caption_ngan_da_do_that_o_H2a():
    """Cùng kịch bản đã đo thật ở H2a: caption 0,5 giây tại [0.15s,0.65s] bị
    bộ lấy mẫu THƯA (làm mờ chữ) bỏ lọt hoàn toàn. Mốc thích ứng của H2 phải
    bắt được."""
    moc = fb.moc_lay_mau_thich_ung(3.0)
    assert any(0.15 <= m <= 0.65 for m in moc), (
        "mốc thích ứng của H2 phải dày hơn bộ lấy mẫu cũ, không được bỏ lọt "
        "đúng ca đã biết là lỗi")


def test_chinh_sach_noi_ro_video_dai_hon_muc_cam_ket():
    ngan = fb.ta_chinh_sach_lay_mau(60.0)
    dai = fb.ta_chinh_sach_lay_mau(150.0)
    assert "90s" not in ngan or "dài hơn" not in ngan
    assert "dài hơn mức H2-MVP cam kết" in dai
    assert "150" in dai


# --------------------------------------------------- gộp quan sát OCR -----

def test_gop_quan_sat_giong_het_lien_tiep():
    tho = [
        {"text": "FLASH SALE", "status": "ok", "timestamp_s": 0.2},
        {"text": "FLASH SALE", "status": "ok", "timestamp_s": 0.4},
        {"text": "FLASH SALE", "status": "ok", "timestamp_s": 0.6},
    ]
    gop = fb.gop_quan_sat_lien_tiep(tho)
    assert gop == [{"text": "FLASH SALE", "status": "ok", "start_s": 0.2, "end_s": 0.6}]


def test_gop_khong_gop_hai_caption_khac_nhau():
    tho = [
        {"text": "FLASH SALE", "status": "ok", "timestamp_s": 0.2},
        {"text": "BUY NOW", "status": "ok", "timestamp_s": 0.4},
    ]
    assert len(fb.gop_quan_sat_lien_tiep(tho)) == 2


def test_gop_khong_gop_khac_status_du_cung_text():
    """Một chữ đọc CHẮC ở khung này và KHÔNG CHẮC ở khung sau là hai tín
    hiệu khác nhau — gộp mất thông tin đó là sai."""
    tho = [
        {"text": "giam gia", "status": "ok", "timestamp_s": 1.0},
        {"text": "giam gia", "status": "unconfirmed", "timestamp_s": 1.2},
    ]
    assert len(fb.gop_quan_sat_lien_tiep(tho)) == 2


def test_gop_giu_moc_dau_cuoi_khong_mat_timestamp():
    tho = [{"text": "x", "status": "ok", "timestamp_s": t} for t in [1.0, 1.2, 1.4]]
    gop = fb.gop_quan_sat_lien_tiep(tho)
    assert gop == [{"text": "x", "status": "ok", "start_s": 1.0, "end_s": 1.4}]


def test_gop_khong_gop_qua_khoang_cach_xa_du_cung_chu():
    """Chữ 'x' hiện ở 1,0-1,4s rồi TẮT, xuất hiện lại ở 9,0s — đây là HAI lần
    xuất hiện, không phải một khoảng liên tục 1,0-9,0s. Gộp nhầm sẽ nói dối
    là chữ hiện SUỐT 8 giây trong khi thực ra biến mất giữa chừng."""
    tho = ([{"text": "x", "status": "ok", "timestamp_s": t} for t in [1.0, 1.2, 1.4]]
          + [{"text": "x", "status": "ok", "timestamp_s": 9.0}])
    gop = fb.gop_quan_sat_lien_tiep(tho)
    assert gop == [
        {"text": "x", "status": "ok", "start_s": 1.0, "end_s": 1.4},
        {"text": "x", "status": "ok", "start_s": 9.0, "end_s": 9.0},
    ]


def test_gop_danh_sach_rong():
    assert fb.gop_quan_sat_lien_tiep([]) == []


# --------------------------------------------------- tích hợp thật --------

@pytest.fixture()
def video_co_phu_de(tmp_path):
    """Video 3 giây thật (ffmpeg), có tiếng (câm) + chữ 'FLASH SALE' hiện từ
    0,2s đến 1,0s — đủ để OCR in-process thật đọc được."""
    if not _HAS_FFMPEG:
        pytest.skip("cần ffmpeg")
    import subprocess

    out = str(tmp_path / "video.mp4")
    vf = (f"drawtext=text='FLASH SALE':fontfile={_BARLOW_FONT}:fontsize=40:"
         "fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,0.2,1.0)'")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=480x270:d=3:r=15",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-shortest",
        "-vf", vf, "-c:v", "libx264", "-pix_fmt", "yuv420p", out,
    ], capture_output=True, timeout=30, check=True)
    return out


def _gia_lap_asr(audio_path, language, settings, cancel_event=None, on_segment=None,
                 detected_out=None):
    if detected_out is not None:
        detected_out["language"] = "en"
        detected_out["prob"] = 0.95
    return [{"start": 0.0, "end": 2.5, "text": "Stop wasting money on this."}]


def test_trich_bang_chung_that_tra_du_asr_va_ocr(tmp_path, video_co_phu_de, monkeypatch):
    import autodub.speech.transcriber as transcriber_mod

    monkeypatch.setattr(transcriber_mod, "transcribe", _gia_lap_asr)

    ket = fb.trich_bang_chung(video_co_phu_de, str(tmp_path / "work"), Settings())

    assert ket.source_type == "file"
    assert ket.language_source_detected == "en"
    assert len(ket.transcript) == 1
    assert ket.transcript[0]["text"] == "Stop wasting money on this."
    # H2 Guardrail: PHẢI dùng read_text_regions() (giữ "text"), KHÔNG dùng
    # detect_text_regions() (không có "text") — nếu ai lỡ đổi lại hàm cũ,
    # ocr_evidence sẽ KHÔNG có khoá "text" và assert dưới đây đỏ.
    assert ket.ocr_evidence, "phải đọc được caption 'FLASH SALE' trong video thật"
    # Đo thật (09-09): RapidOCR đọc dòng "FLASH SALE" vẽ bằng ffmpeg drawtext
    # thành "FLASHSALE" (mất khoảng trắng, confidence vẫn 0,997) — cùng kiểu
    # lệch đã ghi nhận ở H2a (mất dấu thanh tiếng Việt): engine tự tin đọc
    # SAI hình thức chứ không phải không đọc được. So sánh bỏ khoảng trắng để
    # test phản ánh đúng hành vi đo được, không đòi hỏi độ chính xác OCR
    # không có thật.
    assert any("FLASHSALE" in o["text"].replace(" ", "") for o in ket.ocr_evidence)
    assert all("text" in o for o in ket.ocr_evidence)
    assert "ASR: 1 câu" in ket.evidence_summary
    assert "OCR:" in ket.evidence_summary


def test_asr_loi_khong_chan_ca_luot_van_co_ocr(tmp_path, video_co_phu_de, monkeypatch):
    import autodub.speech.transcriber as transcriber_mod
    from autodub.transcribe_tool import TranscribeError

    def loi(*a, **k):
        raise TranscribeError("giả lập ASR hỏng")

    monkeypatch.setattr(transcriber_mod, "transcribe", loi)

    ket = fb.trich_bang_chung(video_co_phu_de, str(tmp_path / "work"), Settings())
    assert ket.transcript == []
    assert ket.ocr_evidence, "OCR vẫn phải chạy dù ASR hỏng"
    assert "Không chép lời được" in ket.evidence_summary


def test_ocr_chua_cai_khong_chan_ca_luot_van_co_asr(tmp_path, video_co_phu_de, monkeypatch):
    import autodub.media.text_regions as tr_mod
    import autodub.speech.transcriber as transcriber_mod

    monkeypatch.setattr(transcriber_mod, "transcribe", _gia_lap_asr)
    # Sandbox này CÓ .venv-ocr cấu hình thật (đo thật 09-09) — nếu chỉ giả
    # ImportError cho `_get_engine` (đường in-process), `read_text_regions()`
    # vẫn ưu tiên chạy đường subprocess thật trước và đọc được chữ thật,
    # không mô phỏng đúng ca "chưa cài OCR". Phải chặn CẢ HAI đường: ép
    # subprocess trả None (giống "không dùng được") rồi mới giả ImportError
    # ở đường in-process dự phòng.
    monkeypatch.setattr(tr_mod, "_detect_via_subprocess", lambda *a, **k: None)
    monkeypatch.setattr(tr_mod, "_get_engine",
                        lambda: (_ for _ in ()).throw(ImportError("no rapidocr")))

    ket = fb.trich_bang_chung(video_co_phu_de, str(tmp_path / "work"), Settings())
    assert len(ket.transcript) == 1
    assert ket.ocr_evidence == []
    assert "Chưa cài bộ đọc chữ overlay" in ket.evidence_summary


def test_khong_co_gi_ca_thi_bao_loi_ro(tmp_path, monkeypatch):
    """ASR trống VÀ OCR trống (video câm, sạch chữ) -> không đủ bằng chứng,
    phải NÓI RÕ, không âm thầm trả bằng chứng rỗng."""
    if not _HAS_FFMPEG:
        pytest.skip("cần ffmpeg")
    import subprocess

    from autodub.transcribe_tool import TranscribeError

    out = str(tmp_path / "sach.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=320x180:d=1:r=5",
        "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", out,
    ], capture_output=True, timeout=30, check=True)

    import autodub.speech.transcriber as transcriber_mod

    def rong(*a, **k):
        return []

    monkeypatch.setattr(transcriber_mod, "transcribe", rong)

    with pytest.raises(TranscribeError, match="không đủ bằng chứng"):
        fb.trich_bang_chung(out, str(tmp_path / "work"), Settings())


def test_video_khong_doc_duoc_thoi_luong_van_tra_ve_duoc(monkeypatch, tmp_path):
    """Không đọc được thời lượng -> không lấy mẫu khung nào -> phần tóm tắt
    vẫn phải dựng được.

    Lỗi thật của bản dựng đầu: ba biến của nhánh OCR (`anh_paths`,
    `moc_lay_duoc`, `chon_bo_doc`) nằm TRONG `if moc:`, nên ca này ném
    NameError — đúng vào lúc mọi thứ đã trục trặc sẵn, tức lúc tệ nhất.
    """
    import autodub.flow_blueprint as fb

    media = tmp_path / "v.mp4"
    media.write_bytes(b"khong phai video that")

    import autodub.speech.transcriber as transcriber_mod
    import autodub.transcribe_tool as tt_mod
    import autodub.media.video as video_mod

    monkeypatch.setattr(
        tt_mod, "prepare_audio",
        lambda source, out_dir, settings=None: (str(media), "Tên", str(media)))
    monkeypatch.setattr(transcriber_mod, "transcribe", _gia_lap_asr)
    # probe hỏng -> 0 giây -> không có mốc lấy mẫu nào
    monkeypatch.setattr(video_mod, "probe_duration_s", lambda p: None)

    bc = fb.trich_bang_chung("nguon", str(tmp_path), Settings())

    assert bc.ocr_evidence == []
    assert "0 khung lấy mẫu" in bc.evidence_summary
    # Không có khung nào thì KHÔNG khoe tên bộ đọc — nói có bộ đọc chạy trong
    # khi nó chưa hề chạy là báo cáo sai.
    assert "Bộ đọc" not in bc.evidence_summary
