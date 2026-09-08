"""Nối "Nhập phụ đề" với "Dịch phụ đề" thành một luồng (08/09/2026) — yêu
cầu người dùng thật: *"định hướng nó luồng tự động nối luôn Nhập phụ đề với
Dịch phụ đề thành một luồng — phụ đề nước ngoài + video → tự dịch → dự án
lồng tiếng luôn"*.

Trước đây `nhap_phu_de.py` chỉ nhận phụ đề ĐÃ tiếng Việt (`nhap_du_an`); tệp
này khoá hành vi của `nhap_du_an_dich` — bản nhận phụ đề NGÔN NGỮ NƯỚC NGOÀI,
tự dịch (local NLLB hoặc SaaS) trước khi dựng dự án, và khoá cửa vào GUI mới
(hộp thoại `NhapPhuDeDichDialog`) nối vào nút thứ hai trên trang launcher.
"""
from __future__ import annotations

import json
import os
from unittest.mock import MagicMock

import pytest

from autodub import nhap_phu_de as npd

SRT_EN = """1
00:00:01,000 --> 00:00:03,000
Hello everyone,

2
00:00:03,000 --> 00:00:05,000
welcome to the show.

3
00:00:06,500 --> 00:00:09,000
Thanks for watching.
"""


@pytest.fixture()
def video_gia(tmp_path):
    p = tmp_path / "video.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return str(p)


@pytest.fixture()
def srt_en(tmp_path):
    p = tmp_path / "phu_de_en.srt"
    p.write_text(SRT_EN, encoding="utf-8")
    return str(p)


# -- Dịch local (NLLB offline) ------------------------------------------

def test_dich_local_dung_field_dich_giu_field_goc(srt_en, video_gia, tmp_path,
                                                   monkeypatch):
    import autodub.text.translate_local as translate_local

    ghi_nhan = {}

    def gia_lap(items, src, tgt, settings, reporter=None, progress_step="translate",
               cancel_event=None):
        ghi_nhan["items"] = items
        ghi_nhan["src"] = src
        ghi_nhan["tgt"] = tgt
        return {i: f"Da dich: {t}" for i, t in items}

    monkeypatch.setattr(translate_local, "run_local_worker", gia_lap)

    ket = npd.nhap_du_an_dich(
        video_gia, srt_en, str(tmp_path / "out"),
        source_flores="eng_Latn", target_key="vi", dich_mode="local",
        settings=MagicMock())

    assert ghi_nhan["src"] == "eng_Latn"
    assert ghi_nhan["tgt"] == "vie_Latn"   # target_key="vi" -> flores qua bảng có sẵn

    cau = json.load(open(os.path.join(ket.thu_muc, "data", "transcript_vi.json"),
                         encoding="utf-8"))
    for c in cau:
        assert c["text_vi"].startswith("Da dich: ")
        assert c["text"] != c["text_vi"], "phải giữ được cả bản gốc lẫn bản dịch"
    assert ket.credit_charged == 0


def test_dich_local_dung_dung_transcript_field_cho_dich_khac_vi(
        srt_en, video_gia, tmp_path, monkeypatch):
    """target_key="en" (dịch tiếng Anh -> tiếng Nhật chẳng hạn) phải ghi
    ra text_field ĐÚNG của target đó, không hardcode text_vi."""
    import autodub.text.translate_local as translate_local

    monkeypatch.setattr(translate_local, "run_local_worker",
                        lambda items, *a, **k: {i: f"JP:{t}" for i, t in items})

    ket = npd.nhap_du_an_dich(
        video_gia, srt_en, str(tmp_path / "out"),
        source_flores="eng_Latn", target_key="ja", dich_mode="local",
        settings=MagicMock())

    duong = os.path.join(ket.thu_muc, "data", "transcript_ja.json")
    assert os.path.isfile(duong), "phải ghi ra transcript_ja.json, không phải _vi"
    cau = json.load(open(duong, encoding="utf-8"))
    for c in cau:
        assert "text_ja" in c
        assert c["text_ja"].startswith("JP:")


def test_thieu_settings_thi_bao_ro(srt_en, video_gia, tmp_path):
    with pytest.raises(npd.LoiNhap, match="cấu hình"):
        npd.nhap_du_an_dich(
            video_gia, srt_en, str(tmp_path / "out"),
            source_flores="eng_Latn", target_key="vi", dich_mode="local",
            settings=None)


# -- Dịch SaaS ------------------------------------------------------------

def test_dich_saas_tru_vox_va_ghi_dung_field(srt_en, video_gia, tmp_path,
                                             monkeypatch):
    fake_client = MagicMock()
    fake_client.translate_subtitle.return_value = {
        "segments": [{"id": 1, "text": "Xin chao moi nguoi,"},
                    {"id": 2, "text": "chao mung den voi show."},
                    {"id": 3, "text": "Cam on da xem."}],
        "creditCharged": 6, "balanceAfter": 994,
    }
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    ket = npd.nhap_du_an_dich(
        video_gia, srt_en, str(tmp_path / "out"),
        source_flores="eng_Latn", target_key="vi", dich_mode="saas",
        job_id="test-job")

    assert fake_client.translate_subtitle.called
    _, kwargs = fake_client.translate_subtitle.call_args
    assert kwargs["source_flores"] == "eng_Latn"
    assert kwargs["target_flores"] == "vie_Latn"
    assert kwargs["job_id"] == "test-job"

    assert ket.credit_charged == 6
    cau = json.load(open(os.path.join(ket.thu_muc, "data", "transcript_vi.json"),
                         encoding="utf-8"))
    assert cau[0]["text_vi"] == "Xin chao moi nguoi,"


def test_thieu_cau_tra_ve_thi_giu_ban_goc_va_noi_ro(srt_en, video_gia, tmp_path,
                                                     monkeypatch):
    """Máy dịch bỏ sót 1 id — giữ nguyên câu gốc thay vì để trống, và PHẢI
    nói ra (đúng lớp lỗi #6, FEATURES.md §6: rỗng chỉ được có một nghĩa)."""
    fake_client = MagicMock()
    fake_client.translate_subtitle.return_value = {
        "segments": [{"id": 1, "text": "Xin chao."}],   # thiếu id 2, 3
        "creditCharged": 2, "balanceAfter": 998,
    }
    import autodub.saas_client as saas_client
    monkeypatch.setattr(saas_client, "get_client", lambda: fake_client)

    ket = npd.nhap_du_an_dich(
        video_gia, srt_en, str(tmp_path / "out"),
        source_flores="eng_Latn", target_key="vi", dich_mode="saas",
        gop=False)   # tắt gộp câu để giữ đúng 3 dòng như tệp .srt gốc

    cau = json.load(open(os.path.join(ket.thu_muc, "data", "transcript_vi.json"),
                         encoding="utf-8"))
    assert len(cau) == 3
    con_lai = [c for c in cau if c["id"] != 1]
    assert con_lai, "câu 2/3 phải còn tồn tại (rơi về bản gốc), không bị xoá"
    for c in con_lai:
        assert c["text_vi"] == c["text"]
    assert any("2" in c and "không trả về" in c for c in ket.canh_bao)


# -- Chốt đầu vào -----------------------------------------------------------

def test_nguon_va_dich_giong_nhau_thi_bao_ro(srt_en, video_gia, tmp_path):
    with pytest.raises(npd.LoiNhap, match="giống nhau"):
        npd.nhap_du_an_dich(
            video_gia, srt_en, str(tmp_path / "out"),
            source_flores="vie_Latn", target_key="vi", dich_mode="local",
            settings=MagicMock())


def test_ma_flores_nguon_sai_thi_bao_ro(srt_en, video_gia, tmp_path):
    with pytest.raises(npd.LoiNhap, match="không hợp lệ"):
        npd.nhap_du_an_dich(
            video_gia, srt_en, str(tmp_path / "out"),
            source_flores="not_a_real_code", target_key="vi", dich_mode="local",
            settings=MagicMock())


def test_dich_mode_sai_thi_bao_ro(srt_en, video_gia, tmp_path):
    with pytest.raises(npd.LoiNhap, match="Cách dịch"):
        npd.nhap_du_an_dich(
            video_gia, srt_en, str(tmp_path / "out"),
            source_flores="eng_Latn", target_key="vi", dich_mode="ca_hai",
            settings=MagicMock())


def test_thieu_video_van_bao_dung_nhu_duong_khong_dich(tmp_path, srt_en):
    with pytest.raises(npd.LoiNhap, match="video"):
        npd.nhap_du_an_dich(
            str(tmp_path / "khong-co.mp4"), srt_en, str(tmp_path),
            source_flores="eng_Latn", target_key="vi", dich_mode="local",
            settings=MagicMock())


# -- Trình chỉnh sửa mở được dự án vừa dịch ----------------------------------

def test_trinh_chinh_sua_MO_DUOC_du_an_vua_dich(srt_en, video_gia, tmp_path,
                                                monkeypatch):
    import autodub.text.translate_local as translate_local
    from autodub.editor import load_work_dir

    monkeypatch.setattr(translate_local, "run_local_worker",
                        lambda items, *a, **k: {i: f"vi:{t}" for i, t in items})

    ket = npd.nhap_du_an_dich(
        video_gia, srt_en, str(tmp_path / "out"),
        source_flores="eng_Latn", target_key="vi", dich_mode="local",
        settings=MagicMock())
    state = load_work_dir(ket.thu_muc)

    assert state.segments
    assert state.target.text_field == "text_vi"
    assert state.video_path == os.path.abspath(video_gia)


# -- Cửa vào GUI --------------------------------------------------------

def test_trang_launcher_co_nut_nhap_dich():
    import inspect

    pytest.importorskip("PySide6")
    from autodub_gui.pages import editor_launcher_page as elp

    nguon = inspect.getsource(elp.EditorLauncherPage)
    assert "nhập phụ đề nước ngoài" in nguon.lower() or "tự dịch" in nguon.lower()
    assert "NhapPhuDeDichDialog" in nguon
