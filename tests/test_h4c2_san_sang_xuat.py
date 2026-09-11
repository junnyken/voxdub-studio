"""Chặn xuất video CÂM — mini-spec H4c-2.

Lỗi thật: dự án do `du_an_tu_kich_ban.dung_du_an()` dựng ra có transcript và
video nền nhưng **không có tệp giọng nào** (`data/segments/` rỗng). Bấm «Xuất
video» ngay lúc đó — đúng luồng mà chính docstring của H4c quảng cáo — thì:

  * `_export` chỉ hỏi lại khi có câu vừa sửa hoặc giọng chưa áp dụng, mà dự
    án mới dựng thì cả hai đều rỗng ⇒ đi thẳng;
  * `build_merged_audio` ghi ``Segment file not found ... skipping`` cho TỪNG
    câu rồi dựng một nền im lặng;
  * `merge_video` vẫn mux ra tệp bình thường.

Kết quả: `dubbed_video.mp4` có hình, có phụ đề, **không có tiếng**, không một
lỗi hay cảnh báo nào.

Máy BIẾT thiếu giọng từ trước khi chạy. Đây là đúng lớp lỗi đã phải sửa ở
trang Hồ sơ Brand: nói ra điều người dùng làm được, đừng tạo một kết quả vô
dụng rồi để họ tự suy đoán.
"""
from __future__ import annotations

import json
import os

import pytest

from autodub.editor import SanSangXuat, kiem_san_sang_xuat
from autodub.languages import TARGETS


def _du_an(tmp_path, so_cau: int, co_giong: list[int] | None = None) -> str:
    """Dựng khung thư mục dự án tối thiểu mà `_load_segments` đọc được."""
    from autodub.utils import seg_wav_path

    work = tmp_path / "duan"
    (work / "data" / "segments").mkdir(parents=True)
    segs = [{"id": i + 1, "start": i * 2.0, "end": i * 2.0 + 2.0,
             "text": f"Câu {i + 1}", "text_vi": f"Câu {i + 1}"}
            for i in range(so_cau)]
    with open(work / "data" / "transcript_vi.json", "w", encoding="utf-8") as f:
        json.dump(segs, f, ensure_ascii=False)
    for i in (co_giong or []):
        p = seg_wav_path(str(work / "data" / "segments"), i)
        with open(p, "wb") as f:
            f.write(b"RIFF....WAVEfmt ")
    return str(work)


VI = TARGETS["vi"]


# ------------------------------------------------------ đếm cho đúng ------

def test_du_an_vua_dung_tu_kich_ban_la_CAM_HOAN_TOAN(tmp_path):
    ra = kiem_san_sang_xuat(_du_an(tmp_path, 4), VI)
    assert ra.tong_cau == 4
    assert ra.thieu_giong == [1, 2, 3, 4]
    assert ra.cam_hoan_toan is True
    assert ra.xuat_duoc is False


def test_du_giong_thi_xuat_duoc(tmp_path):
    ra = kiem_san_sang_xuat(_du_an(tmp_path, 3, co_giong=[1, 2, 3]), VI)
    assert ra.thieu_giong == []
    assert ra.xuat_duoc is True
    assert ra.cam_hoan_toan is False


def test_thieu_MOT_cau_van_KHONG_xuat_duoc(tmp_path):
    ra = kiem_san_sang_xuat(_du_an(tmp_path, 3, co_giong=[1, 3]), VI)
    assert ra.thieu_giong == [2], "phải chỉ đúng câu nào thiếu"
    assert ra.xuat_duoc is False
    # Thiếu một câu thì KHÁC câm hoàn toàn — hai câu nói khác nhau.
    assert ra.cam_hoan_toan is False


def test_tep_giong_RONG_cung_la_thieu(tmp_path):
    """ffmpeg ghi hụt vẫn để lại tệp 0 byte, mà 0 byte thì bước trộn cũng bỏ
    qua y hệt như không có tệp. Đếm nó là "có" thì cổng này vô dụng."""
    from autodub.utils import seg_wav_path

    work = _du_an(tmp_path, 2, co_giong=[1, 2])
    rong = seg_wav_path(os.path.join(work, "data", "segments"), 2)
    open(rong, "wb").close()
    assert os.path.getsize(rong) == 0

    ra = kiem_san_sang_xuat(work, VI)
    assert ra.thieu_giong == [2]


def test_du_an_KHONG_co_cau_nao_thi_bao_loi_khac_han(tmp_path):
    """0 câu là dự án hỏng theo kiểu KHÁC — `_load_segments` đã chặn sẵn với
    câu nói đúng chuyện. Đừng để nó rơi vào nhánh "thiếu giọng đọc", vì bảo
    người dùng đi đọc lại một dự án không có câu nào là chỉ sai đường.
    """
    from autodub.editor import EditorError

    with pytest.raises(EditorError, match="trống hoặc sai định dạng"):
        kiem_san_sang_xuat(_du_an(tmp_path, 0), VI)


# ------------------------------------------- nối với H4c, đường đi thật ---

def test_du_an_H4c_THAT_vua_dung_xong_thi_bi_chan(tmp_path):
    """Không dựng khung thư mục bằng tay: gọi thẳng `dung_du_an` như người
    dùng, rồi hỏi cổng xuất.

    Đây là chỗ lỗi đã trốn — mọi test H4c trước đây chỉ chứng minh dự án MỞ
    được, chưa ai hỏi nó có xuất ra tiếng không.
    """
    from autodub import du_an_tu_kich_ban as da

    anh = []
    for i in range(3):
        p = tmp_path / f"a{i}.png"
        p.write_bytes(b"x")
        anh.append(str(p))

    kb = {"id": "s1", "status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": f"Câu số {i} đủ dài để đo.",
         "captionSuggestionVi": f"Chữ {i}", "visualBriefVi": "Cận cảnh"}
        for i in range(3)]}

    goi = {}

    def _ghep(duong_anh, duong_ra, *, giay_moi_anh, **kw):
        goi["giay"] = list(giay_moi_anh)
        open(duong_ra, "wb").write(b"video gia")

    ket = da.dung_du_an(kb, anh, str(tmp_path / "duan"), ghep_video=_ghep,
                        do_thoi_luong=lambda _p: sum(goi["giay"]))

    ra = kiem_san_sang_xuat(ket.work_dir, VI)
    assert ra.tong_cau == 3
    assert ra.cam_hoan_toan is True, (
        "dự án dựng từ kịch bản mà cổng xuất tưởng là có tiếng — video xuất "
        "ra sẽ câm mà không cảnh báo gì")


# --------------------------------------------------- giao diện chặn thật -

def test_nut_xuat_BI_CHAN_va_chi_dung_viec_can_lam(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from autodub_gui.pages import editor_export as ee

    QApplication.instance() or QApplication([])
    thay = {}
    monkeypatch.setattr(ee.ConfirmDialog, "ask", staticmethod(
        lambda _p, tieu_de, loi, **kw: (
            thay.update(tieu_de=tieu_de, loi=loi, xac_nhan=kw.get("confirm_label", ""),
                        detail=kw.get("detail", "")),
            (True, True))[1]))

    trang = ee.VoiceAndExportMixin.__new__(ee.VoiceAndExportMixin)
    trang._work_dir = "/tmp/khong-quan-trong"
    trang._state = type("S", (), {"target": VI})()
    da_mo = []
    trang._show_tab = da_mo.append
    monkeypatch.setattr("autodub.editor.kiem_san_sang_xuat",
                        lambda *a, **k: SanSangXuat(tong_cau=5, thieu_giong=[1, 2, 3, 4, 5]))

    assert ee.VoiceAndExportMixin._chan_neu_thieu_giong(trang) is True, "phải CHẶN"
    assert "KHÔNG CÓ TIẾNG" in thay["loi"], "phải nói thẳng hậu quả"
    # Nêu đúng nút người dùng bấm được, không chỉ báo lỗi.
    assert "Lưu tất cả và đọc lại" in thay["loi"]
    assert "không tốn Vox" in thay["loi"], "phải nói rõ bước chữa là miễn phí"
    assert da_mo == ["voice"], "bấm đồng ý phải mở đúng thẻ Giọng đọc"


def test_du_giong_thi_KHONG_chan(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from autodub_gui.pages import editor_export as ee

    QApplication.instance() or QApplication([])
    monkeypatch.setattr(ee.ConfirmDialog, "ask", staticmethod(
        lambda *a, **k: pytest.fail("chặn nhầm một dự án đã đủ giọng")))
    trang = ee.VoiceAndExportMixin.__new__(ee.VoiceAndExportMixin)
    trang._work_dir = "/tmp/x"
    trang._state = type("S", (), {"target": VI})()
    monkeypatch.setattr("autodub.editor.kiem_san_sang_xuat",
                        lambda *a, **k: SanSangXuat(tong_cau=3, thieu_giong=[]))
    assert ee.VoiceAndExportMixin._chan_neu_thieu_giong(trang) is False


def test_dem_hong_thi_KHONG_chan_nham(monkeypatch):
    """Chặn nhầm còn tệ hơn: người dùng có video hợp lệ mà không xuất được."""
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from autodub_gui.pages import editor_export as ee

    QApplication.instance() or QApplication([])
    ghi = []

    def _no(*a, **k):
        raise RuntimeError("đĩa lỗi")

    trang = ee.VoiceAndExportMixin.__new__(ee.VoiceAndExportMixin)
    trang._work_dir = "/tmp/x"
    trang._state = type("S", (), {"target": VI})()
    trang.log = type("L", (), {"append_log": lambda _s, t, m=0: ghi.append(t)})()
    monkeypatch.setattr("autodub.editor.kiem_san_sang_xuat", _no)

    assert ee.VoiceAndExportMixin._chan_neu_thieu_giong(trang) is False
    assert ghi and "đĩa lỗi" in ghi[0], "hỏng phải LỘ RA ở Nhật ký, không nuốt"


def test_nut_XUAT_that_su_di_qua_cong_nay(monkeypatch):
    """Chốt chỗ GỌI, không chỉ chốt thân hàm.

    Phát hiện khi tự kiểm: gỡ dòng gọi `_chan_neu_thieu_giong()` khỏi
    `_export()` mà **không test nào đỏ** — tức cổng có thể tồn tại đầy đủ và
    vẫn bị đi vòng qua. Đúng lớp sai đã mắc ba lần trước đó.
    """
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from autodub_gui.pages import editor_export as ee

    QApplication.instance() or QApplication([])
    import autodub_gui.workers as w
    monkeypatch.setattr(w, "RebuildWorker", lambda *a, **k: pytest.fail(
        "đã bắt đầu xuất video dù cổng giọng đọc bảo dừng"))

    goi = []
    trang = ee.VoiceAndExportMixin.__new__(ee.VoiceAndExportMixin)
    trang._busy_warn = lambda: False
    trang._work_dir = "/tmp/x"
    trang._flush_edits = lambda: None
    trang.voice_panel = type("V", (), {"has_pending_voice_change": lambda _s: False})()
    trang._chan_neu_thieu_giong = lambda: goi.append(1) or True

    ee.VoiceAndExportMixin._export(trang)
    assert goi, "_export không hỏi cổng giọng đọc"


# ---------------------------------------------------------------------------
# Lỗi tìm ra bằng PILOT H4 CỤC BỘ (11/09/2026), không phải bằng test.
#
# `editor._check_render_mode()` chặn xuất khi `data/segments/` có tệp .wav mà
# không có dấu `.render_mode` khớp `DubPipeline.RENDER_MODE` — nó canh những
# dự án đời cũ đọc theo cơ chế gộp câu. Dấu đó do `DubPipeline` ghi, mà dự án
# dựng từ kịch bản KHÔNG đi qua pipeline lần nào.
#
# Người dùng: dựng dự án → đọc bằng VieNeu → bấm Xuất → nhận "Thư mục này
# chứa giọng đọc tạo theo cơ chế gộp câu đời cũ. Hãy chạy tiếp dự án một
# lần…" — một việc KHÔNG TỒN TẠI cho loại dự án này. Câu báo lỗi đúng với ca
# nó canh, nhưng chỉ sai đường hoàn toàn ở đây.
#
# Không test nào bắt được vì chưa lượt nào đi tới bước xuất.

def test_du_an_H4c_khai_dung_co_che_doc_theo_tung_cau(tmp_path):
    from autodub import du_an_tu_kich_ban as da
    from autodub.pipeline import DubPipeline

    anh = []
    for i in range(2):
        p = tmp_path / f"a{i}.png"
        p.write_bytes(b"x")
        anh.append(str(p))
    kb = {"id": "s1", "status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": f"Câu {i} đủ dài để đo.",
         "captionSuggestionVi": "c", "visualBriefVi": "v"} for i in range(2)]}

    goi = {}
    ket = da.dung_du_an(
        kb, anh, str(tmp_path / "duan"),
        ghep_video=lambda p, r, *, giay_moi_anh, **k: (
            goi.update(giay=list(giay_moi_anh)), open(r, "wb").write(b"v"))[0],
        do_thoi_luong=lambda _p: sum(goi["giay"]))

    dau = os.path.join(ket.work_dir, "data", "segments", ".render_mode")
    assert os.path.isfile(dau), (
        "thiếu dấu cơ chế đọc — người dùng sẽ bị chặn ở bước Xuất với lời "
        "khuyên 'chạy tiếp dự án một lần', việc không tồn tại cho dự án này")
    with open(dau, encoding="utf-8") as f:
        assert f.read().strip().splitlines()[0] == DubPipeline.RENDER_MODE


def test_cong_render_mode_cho_du_an_H4c_di_qua(tmp_path):
    """Kiểm HÀNH VI của chính cổng đã chặn, không chỉ kiểm có tệp."""
    from autodub import du_an_tu_kich_ban as da
    from autodub.editor import _check_render_mode
    from autodub.utils import seg_wav_path

    anh = [str(tmp_path / "a.png")]
    (tmp_path / "a.png").write_bytes(b"x")
    kb = {"id": "s1", "status": "ready", "beats": [
        {"beatType": "hook", "voiceoverTextVi": "Một câu đủ dài để đo thử.",
         "captionSuggestionVi": "c", "visualBriefVi": "v"}]}
    goi = {}
    ket = da.dung_du_an(
        kb, anh, str(tmp_path / "duan"),
        ghep_video=lambda p, r, *, giay_moi_anh, **k: (
            goi.update(giay=list(giay_moi_anh)), open(r, "wb").write(b"v"))[0],
        do_thoi_luong=lambda _p: sum(goi["giay"]))

    # Sau khi đọc xong, thư mục có .wav — đúng ca mà cổng kia canh.
    seg_dir = os.path.join(ket.work_dir, "data", "segments")
    with open(seg_wav_path(seg_dir, 1), "wb") as f:
        f.write(b"RIFF....WAVEfmt ")

    _check_render_mode(ket.work_dir)   # không được ném
