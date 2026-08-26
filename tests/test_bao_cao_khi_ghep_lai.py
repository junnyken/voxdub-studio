"""Ghép lại từ Trình chỉnh sửa phải để lại báo cáo chất lượng.

Tìm ra 26/8/2026 khi rà bản đề bài E1 ("đặt trần ép tốc độ đọc"). Hoá ra trần
**đã có sẵn** (`timing_max_atempo`, mặc định 1.1) và engine **đã đo** từng câu:
nén bao nhiêu, dời bao nhiêu, còn chồng tiếng bao nhiêu.

Thứ hỏng là một dòng:

    merge_dir, _timing = apply_soft_timing(...)

Đo xong rồi **vứt đi**. Đường lồng tiếng chính ghi kết quả ra
`quality_report.json` và trang Báo cáo chất lượng hiện đủ từng câu kèm chữ;
ai đi đường Trình chỉnh sửa thì không thấy gì.

Đúng chỗ này quan trọng với đường mới "Mở video + phụ đề tiếng Việt" (C37):
toàn bộ luồng đó nằm trong Trình chỉnh sửa.
"""
from __future__ import annotations

import json
import os

from autodub.editor import ghi_bao_cao_chat_luong
from autodub.languages import get_target
from autodub.media.timing import TimingReport

CAU = [
    {"id": 1, "start": 0.0, "end": 2.0, "duration": 2.0, "text_vi": "câu một"},
    {"id": 2, "start": 2.0, "end": 4.0, "duration": 2.0, "text_vi": "câu hai"},
]


def _bao_cao_co_van_de() -> TimingReport:
    rep = TimingReport(segments_total=2, segments_compressed=1,
                       segments_overlapped=1, total_overlap_s=0.42,
                       max_shift_s=0.3, segments_shifted=1)
    rep.details = [{"id": 2, "atempo": 1.08, "overlap_prev_s": 0.42,
                    "shift_s": 0.3}]
    return rep


def test_ghep_lai_de_lai_bao_cao(tmp_path):
    duong = ghi_bao_cao_chat_luong(str(tmp_path), get_target("vi"), CAU,
                                   _bao_cao_co_van_de())
    assert duong and os.path.isfile(duong)

    bc = json.load(open(duong, encoding="utf-8"))
    assert bc["summary"]["segments_compressed"] == 1
    assert bc["summary"]["segments_overlapped"] == 1


def test_bao_cao_chi_ro_TUNG_CAU_kem_chu(tmp_path):
    """Cảnh báo chung "có câu bị đọc nhanh" thì người dùng không sửa được gì."""
    duong = ghi_bao_cao_chat_luong(str(tmp_path), get_target("vi"), CAU,
                                   _bao_cao_co_van_de())
    bc = json.load(open(duong, encoding="utf-8"))

    assert bc["per_segment"], "không chỉ ra câu nào"
    cau = bc["per_segment"][0]
    assert cau["id"] == 2
    assert cau.get("atempo") == 1.08, "không nói mức đọc nhanh bao nhiêu"
    assert "text" in cau, "không kèm chữ thì không tìm ra câu đó trong editor"


def test_video_sach_thi_danh_sach_rong(tmp_path):
    duong = ghi_bao_cao_chat_luong(str(tmp_path), get_target("vi"), CAU,
                                   TimingReport(segments_total=2))
    bc = json.load(open(duong, encoding="utf-8"))

    assert bc["per_segment"] == []
    assert bc["summary"]["segments_ok"] == 2


def test_GIU_phan_cua_luot_chay_goc(tmp_path):
    """Ghi đè cả tệp là xoá mất trace rà soát bản dịch của lượt chạy trước."""
    from autodub.workdir import data_path

    duong = data_path(str(tmp_path), "quality_report.json", create_dir=True)
    with open(duong, "w", encoding="utf-8") as f:
        json.dump({"translate_review": [{"id": 9, "note": "đã sửa"}],
                   "summary": {"segments_total": 99}}, f)

    ghi_bao_cao_chat_luong(str(tmp_path), get_target("vi"), CAU,
                           _bao_cao_co_van_de())
    bc = json.load(open(duong, encoding="utf-8"))

    assert bc["translate_review"] == [{"id": 9, "note": "đã sửa"}], (
        "đã xoá mất dữ liệu của lượt chạy gốc")
    assert bc["summary"]["segments_total"] == 2, "số liệu mới phải đè số cũ"


def test_bao_cao_hong_thi_KHONG_giet_luot_ghep(tmp_path, monkeypatch, caplog):
    """Video vẫn phải ghép xong; thiếu báo cáo là mất tiện nghi, không mất việc."""
    from autodub import editor

    class _Hong:
        @staticmethod
        def _build_quality_report(*a, **k):
            raise RuntimeError("giả vờ hỏng")

    monkeypatch.setattr("autodub.pipeline.DubPipeline", _Hong)
    with caplog.at_level("WARNING"):
        ra = editor.ghi_bao_cao_chat_luong(str(tmp_path), get_target("vi"),
                                           CAU, _bao_cao_co_van_de())

    assert ra == ""
    assert any("báo cáo chất lượng" in r.message for r in caplog.records), (
        "nuốt lỗi không dấu vết thì lần sau không ai biết vì sao mất báo cáo")


def test_duong_ghep_KHONG_con_vut_ket_qua_do(  ):
    """Chốt gốc: `apply_soft_timing` trả báo cáo, không được gán vào `_`."""
    import inspect

    from autodub import editor

    nguon = inspect.getsource(editor)
    assert "_timing = apply_soft_timing" not in nguon, (
        "lại vứt kết quả đo đi — người dùng mất bảng câu bị đọc nhanh")
    assert "ghi_bao_cao_chat_luong(work_dir" in nguon, (
        "đo rồi mà không ghi ra thì cũng như không đo")
