"""Mini-spec C44 (docs/PLAN.md) — chất lượng HIỂU NGUỒN.

Ba lỗ hổng thật đo được trước C44, tất cả cùng một gốc: "ngôn ngữ gốc" là thứ
người dùng KHAI, không phải thứ máy NGHE THẤY.

1. Bật "Để ứng dụng tự nhận ra ngôn ngữ" → `source_lang` rỗng đi suốt pipeline:
   lời nhắc dịch ghi "translate an ASR transcript from  to Vietnamese", dịch
   ngoại tuyến báo "không hỗ trợ ngôn ngữ nguồn ''", phép so nguồn-trùng-đích
   luôn trả False (Việt→Việt vẫn bị tính tiền dịch).
2. Đường ASR in-process truyền `language=""` xuống faster-whisper, trong khi
   `Tokenizer.__init__` chỉ nhận `None` để tự nhận dạng ("'' is not a valid
   language code") — chạy từ mã nguồn hoặc mẻ ≥2 video là chết ngay ở bước nghe.
3. Không có một luật nào trong prompt nói về NGÔN NGỮ NGUỒN — mọi luật chất
   lượng đều gắn với ngôn ngữ đích.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from autodub.languages import from_asr_code, ten_ngon_ngu_nguon
from autodub.pipeline import DubPipeline
from autodub.text import translate_hint

REPO = Path(__file__).resolve().parents[1]


# ------------------------------------------------- mã ASR → nguồn của app --

@pytest.mark.parametrize("asr_code,expected", [
    ("en", "en-US"), ("zh", "zh-CN"), ("ja", "ja-JP"), ("KO", "ko-KR"),
])
def test_ma_whisper_ve_dung_ma_nguon_cua_app(asr_code, expected):
    assert from_asr_code(asr_code) == expected


def test_ma_ngoai_danh_sach_giu_nguyen_khong_doan_bua():
    # Whisper nhận ~100 ngôn ngữ, app chỉ cho chọn 9 — mã lạ phải đi tiếp
    # nguyên vẹn để máy chủ còn gọi tên được, KHÔNG được rơi về zh-CN.
    assert from_asr_code("de") == "de"
    assert from_asr_code("") == ""


def test_ten_hien_cho_nguoi_dung_khong_bao_gio_rong():
    assert ten_ngon_ngu_nguon("en-US") == "tiếng Anh"
    assert ten_ngon_ngu_nguon("") == "tự nhận dạng"
    assert ten_ngon_ngu_nguon("de") == "de"


# ----------------------------------------- ASR trả lại ngôn ngữ nghe được --

class _FakeInfo:
    language = "en"
    language_probability = 0.98


class _FakeModel:
    """Ghi lại đúng tham số `language` mà faster-whisper nhận được."""

    def __init__(self):
        self.language_seen = "chưa gọi"

    def transcribe(self, _audio, **kwargs):
        self.language_seen = kwargs.get("language", "không truyền")
        return iter(()), _FakeInfo()


class _FakeSettings:
    whisper_model = "small"
    whisper_beam_size = 5


def test_in_process_khong_con_truyen_chuoi_rong_xuong_whisper(monkeypatch):
    """faster-whisper CHỈ tự nhận dạng khi `language is None`; chuỗi rỗng làm
    `Tokenizer` ném ValueError. Đây là ca "tự nhận ngôn ngữ" chạy từ mã nguồn."""
    from autodub.speech import transcriber

    model = _FakeModel()
    monkeypatch.setattr(transcriber, "_load_whisper_model",
                        lambda *_a, **_k: (model, "cpu"))
    nhan_dang: dict = {}
    transcriber._transcribe_whisper("a.wav", "", _FakeSettings(),
                                    detected_out=nhan_dang)
    assert model.language_seen is None, "phải là None, không phải chuỗi rỗng"
    assert nhan_dang == {"language": "en", "prob": 0.98}


def test_in_process_van_ton_trong_ngon_ngu_nguoi_dung_chon(monkeypatch):
    from autodub.speech import transcriber

    model = _FakeModel()
    monkeypatch.setattr(transcriber, "_load_whisper_model",
                        lambda *_a, **_k: (model, "cpu"))
    transcriber._transcribe_whisper("a.wav", "zh-CN", _FakeSettings())
    assert model.language_seen == "zh"


def test_transcribe_chuyen_tiep_detected_out_qua_duong_subprocess(monkeypatch):
    """`transcribe()` là cửa duy nhất pipeline dùng — dict phải đi xuyên qua."""
    from autodub.speech import transcriber

    def _fake_sub(_audio, _lang, _settings, cancel_event=None, on_segment=None,
                  detected_out=None):
        if detected_out is not None:
            detected_out["language"] = "zh"
            detected_out["prob"] = 0.87
        return [{"id": 1, "text": "x", "start": 0.0, "end": 1.0, "duration": 1.0}]

    class _S:
        asr_engine = "whisper"

        @staticmethod
        def whisper_venv_configured():
            return True

    monkeypatch.setattr(transcriber, "_transcribe_whisper_subprocess", _fake_sub)
    nhan_dang: dict = {}
    transcriber.transcribe("a.wav", "", _S(), detected_out=nhan_dang)
    assert nhan_dang["language"] == "zh"


# --------------------------------------- chạy tiếp dự án đã nghe bằng auto --

def _viet_transcript(tmp_path):
    t = tmp_path / "transcript_original.json"
    t.write_text(json.dumps([{"start": 0, "end": 1, "text": "x"}]), encoding="utf-8")
    return t


def test_de_may_tu_nhan_thi_khong_bat_nghe_lai_ca_video(tmp_path):
    """Lượt trước nghe ra tiếng Anh; lượt này người dùng vẫn để máy tự nhận.
    Ép nghe lại một video vài giờ vì chuyện đó là phạt oan."""
    transcript = _viet_transcript(tmp_path)
    marker = tmp_path / ".asr_lang"
    marker.write_text("en-US", encoding="utf-8")
    assert DubPipeline._load_cached_transcript(str(transcript), str(marker), "") is not None


def test_doi_ngon_ngu_that_thi_van_phai_nghe_lai(tmp_path):
    """Guardrail V40 giữ nguyên — chỉ ca "để máy tự nhận" mới được bỏ qua."""
    transcript = _viet_transcript(tmp_path)
    marker = tmp_path / ".asr_lang"
    marker.write_text("en-US", encoding="utf-8")
    assert DubPipeline._load_cached_transcript(str(transcript), str(marker), "zh-CN") is None


def test_lay_lai_duoc_ngon_ngu_da_nghe_lan_truoc(tmp_path):
    marker = tmp_path / ".asr_lang"
    marker.write_text(" en-US \n", encoding="utf-8")
    assert DubPipeline._doc_moc_ngon_ngu(str(marker)) == "en-US"
    assert DubPipeline._doc_moc_ngon_ngu(str(tmp_path / "khong-co")) == ""


# ------------------------------------- luật đọc hiểu nguồn (đường dịch tay) --

def test_prompt_dich_tay_goi_ten_ngon_ngu_nguon():
    from autodub.languages import get_target

    p = translate_hint.build_translation_prompt(get_target("vi"), "zh-CN")
    assert "from Chinese (Mandarin) to Vietnamese" in p
    assert "from zh-CN to" not in p


def test_prompt_dich_tay_khong_de_lai_khoang_trang_khi_chua_biet_nguon():
    from autodub.languages import get_target

    p = translate_hint.build_translation_prompt(get_target("vi"), "")
    assert "transcript from  to" not in p
    assert "an unidentified language" in p


@pytest.mark.parametrize("source_lang,phai_co,khong_duoc_co", [
    ("zh-CN", "Dropped subjects", "Phrasal verbs"),
    ("en-US", "Phrasal verbs", "Dropped subjects"),
])
def test_moi_nguon_chi_nhan_luat_cua_chinh_no(source_lang, phai_co, khong_duoc_co):
    from autodub.languages import get_target

    p = translate_hint.build_translation_prompt(get_target("vi"), source_lang)
    assert phai_co in p
    assert khong_duoc_co not in p


def test_moi_nguon_deu_duoc_nhac_ban_chep_loi_la_cua_may():
    from autodub.languages import get_target

    for src in ("zh-CN", "en-US", "de", ""):
        p = translate_hint.build_translation_prompt(get_target("vi"), src)
        assert "machine transcript, not written text" in p, src


# ------------------------- canh hai đường dịch không lệch danh sách ngôn ngữ --

def test_duong_may_chu_va_duong_dich_tay_phu_cung_mot_danh_sach_nguon():
    """Lớp lỗi #5 của dự án (câu chữ hai nơi đi lệch nhau): thêm ngôn ngữ nguồn
    ở máy chủ mà quên đường dịch tay thì người chọn dịch ngoại tuyến (D1) lãnh
    bản dịch kém hơn, không ai báo. Test này canh DANH SÁCH, không canh câu chữ
    — hai bên cố ý viết dài ngắn khác nhau."""
    js = (REPO / "control_server/src/prompts/translate.js").read_text(encoding="utf-8")
    khoi = js.split("const SOURCE_RULES = {", 1)[1].split("\n}", 1)[0]
    khoa_js = set(re.findall(r"^  ([a-z]{2}):", khoi, re.M))
    assert khoa_js, "không đọc được SOURCE_RULES phía máy chủ"
    assert khoa_js == set(translate_hint.SOURCE_RULES), (
        f"máy chủ có luật nguồn cho {sorted(khoa_js)}, đường dịch tay có "
        f"{sorted(translate_hint.SOURCE_RULES)}")


def test_hai_duong_goi_ten_ngon_ngu_giong_nhau():
    js = (REPO / "control_server/src/prompts/translate.js").read_text(encoding="utf-8")
    khoi = js.split("const SOURCE_NAMES = {", 1)[1].split("}", 1)[0]
    ten_js = dict(re.findall(r"(\w+): '([^']+)'", khoi))
    assert ten_js == translate_hint.SOURCE_NAMES


# ------------- bỏ hẳn khâu dịch: chỉ khi CHẮC video đúng ngôn ngữ đích --

def test_moc_giu_ca_do_tin_cay_va_chi_so_phan_ma(tmp_path):
    """Chạy tiếp phải quyết y hệt lượt đầu — nên marker giữ cả con số. Nhưng
    phép so "đổi ngôn ngữ" (V40) chỉ được nhìn phần mã, nếu không mọi lượt
    chạy tiếp đều bị bắt nghe lại cả video."""
    marker = tmp_path / ".asr_lang"
    marker.write_text("en-US 0.982", encoding="utf-8")
    assert DubPipeline._doc_moc_ngon_ngu(str(marker)) == "en-US"
    assert DubPipeline._doc_moc_tin_cay(str(marker)) == pytest.approx(0.982)

    transcript = _viet_transcript(tmp_path)
    assert DubPipeline._load_cached_transcript(
        str(transcript), str(marker), "en-US") is not None, (
        "marker kiểu mới bị coi là 'đã đổi ngôn ngữ' → nghe lại oan cả video")


def test_moc_doi_cu_doc_ra_khong_biet_chu_khong_phai_chac_chan(tmp_path):
    """Marker từ trước C44 chỉ có mã. Đọc ra 0 = "không biết" — lượt chạy tiếp
    KHÔNG được dựa vào đó để bỏ hẳn khâu dịch."""
    marker = tmp_path / ".asr_lang"
    marker.write_text("vi-VN", encoding="utf-8")
    assert DubPipeline._doc_moc_ngon_ngu(str(marker)) == "vi-VN"
    assert DubPipeline._doc_moc_tin_cay(str(marker)) == 0.0


def test_moc_hong_khong_lam_do_lat_chay(tmp_path):
    marker = tmp_path / ".asr_lang"
    marker.write_text("en-US khong-phai-so", encoding="utf-8")
    assert DubPipeline._doc_moc_tin_cay(str(marker)) == 0.0
    assert DubPipeline._doc_moc_ngon_ngu(str(tmp_path / "trong.txt")) == ""


def test_nguong_tin_cay_nam_trong_ma_va_du_cao():
    """Rào chắn này quyết định có BỎ HẲN khâu dịch hay không — đoán sai là
    giao ra video chưa dịch mà không ai báo. Test canh chính con số đó."""
    src = (REPO / "autodub/pipeline.py").read_text(encoding="utf-8")
    m = re.search(r"if khong_can_dich and nguon_do_tin_cay < ([\d.]+):", src)
    assert m, "rào chắn độ tin cậy đã bị gỡ khỏi pipeline"
    assert float(m.group(1)) >= 0.8
