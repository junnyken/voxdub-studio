"""Mini-spec V20 (docs/PLAN.md, Phase E) — bug thật: suy giới tính giọng
CapCut chỉ nhận diện đúng giọng nữ tiếng Việt (voice_type khớp 3 mã BV cụ
thể hoặc chứa "female" LITERAL) — với catalog tiếng Anh, nhiều giọng ghi rõ
giới tính ngay trong TÊN hiển thị nhưng không lộ qua voice_type, bị gắn
nhầm "male" mặc định. Hậu quả thật: bộ lọc giới tính trong Thư viện giọng
đọc (voice_library.py) ẩn mất các giọng nữ này khỏi kết quả lọc "Nữ".
"""
from __future__ import annotations

from autodub.speech.tts.capcut_catalog import _gender_of, entries


def test_gender_of_vietnamese_bv_prefix_still_correct_0_regression():
    assert _gender_of("BV421_vivn_streaming") == "female"
    assert _gender_of("BV074_streaming") == "female"
    assert _gender_of("BV562_streaming") == "female"


def test_gender_of_literal_female_in_voice_type_still_correct_0_regression():
    assert _gender_of("en_female_janeamber_mars_bigtts") == "female"


def test_gender_of_bug_reproduced_without_display_name():
    """Tái tạo đúng bug cũ: không có display_name để tham khảo, voice_type
    không có tín hiệu chữ nào -> rơi về mặc định "male" (hành vi CŨ giữ
    nguyên khi thiếu display_name, không phải hồi quy)."""
    assert _gender_of("BV503_streaming") == "male"
    assert _gender_of("BV029_streaming") == "male"


def test_gender_of_fixed_with_display_name_female_in_title():
    """Bug thật đã sửa: tên hiển thị ghi rõ "Female"/"Famale" (lỗi chính tả
    thật trong chính Voice.json) nhưng voice_type không có tín hiệu — giờ
    phải nhận đúng "female", không còn mặc định sai thành "male"."""
    assert _gender_of("BV503_streaming", "Energetic Famale") == "female"
    assert _gender_of("BV029_streaming", "American Female") == "female"
    assert _gender_of("en_us_002_dsp", "Dolly famle") == "female"
    assert _gender_of("ICL_en_female_ditie_dsp", "Creepy female") == "female"


def test_gender_of_known_branded_voice_jenny_is_female():
    """"Jenny" (Microsoft Azure Neural TTS, giới tính nữ là thông tin công
    khai) không có TÍN HIỆU CHỮ nào ở cả voice_type lẫn tên hiển thị — cần
    bảng tra riêng, không suy được từ text."""
    assert _gender_of("en-US-JennyMultilingualNeural", "Jenny") == "female"


def test_gender_of_defaults_male_when_truly_no_signal():
    """Giọng hiệu ứng/không rõ giới tính (không khớp mọi tín hiệu) vẫn mặc
    định "male" — giữ đúng quy ước cũ (V8), không đổi hành vi này."""
    assert _gender_of("en_male_deadpool", "Deadpool") == "male"
    assert _gender_of("ICL_en_male_oogie2", "Oogie") == "male"


def test_english_catalog_gender_distribution_real_data_no_longer_skewed():
    """Xác nhận thật trên chính Voice.json (không mock) — trước khi sửa:
    17 giọng nữ tiếng Anh, 3 trong số đó (Jenny/Energetic Famale/American
    Female) bị đếm nhầm thành nam. Sau khi sửa, cả 3 phải nằm đúng trong
    nhóm nữ."""
    en = entries("en-US")
    by_name = {e["name"]: e for e in en}
    for name in ("Jenny", "Energetic Famale", "American Female", "Dolly famle"):
        assert name in by_name, f"{name} phải còn trong catalog"
        assert by_name[name]["gender"] == "female", (
            f"{name} phải được nhận đúng là giọng nữ")
