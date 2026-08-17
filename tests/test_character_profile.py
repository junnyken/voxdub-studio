"""Mini-spec V57 — hồ sơ nhân vật dùng lại qua nhiều tập.

Nguyên tắc chi phối mọi test ở đây: **khớp sai tệ hơn không khớp**. Gán nhầm
giọng của nhân vật khác vào một người lạ làm hỏng cả tập theo cách người dùng
chỉ phát hiện sau khi đã nghe lại — nên nhóm test "KHÔNG được khớp" quan
trọng ngang nhóm "phải khớp".

Chạy:  pytest tests/test_character_profile.py
"""
from __future__ import annotations

import json

import pytest

import pathlib

from autodub.character_profile import (
    MATCH_TOLERANCE_HZ,
    Character,
    CharacterProfile,
)


def _profile(**kw) -> CharacterProfile:
    return CharacterProfile(
        name="Phim A",
        characters=[
            Character(name="Nam chính", voice="Bùi Thiện", median_f0=115.0,
                      gender="male", episodes=3),
            Character(name="Nữ chính", voice="Bùi Trang", median_f0=205.0,
                      gender="female", episodes=3),
        ],
        **kw,
    )


# --- Khớp ĐÚNG -----------------------------------------------------------

def test_same_person_next_episode_gets_the_same_voice():
    """Đây là lý do V57 tồn tại: tập 2 phải nhận lại đúng giọng tập 1.

    Nhãn diarization đổi (`SPEAKER_00` → `SPEAKER_01`) là chuyện bình thường
    giữa 2 file — khớp phải dựa vào giọng, không dựa vào nhãn.
    """
    profile = _profile()

    matched = profile.match_speakers({"SPEAKER_01": 117.0, "SPEAKER_00": 203.0})

    assert matched == {"SPEAKER_01": "Nam chính", "SPEAKER_00": "Nữ chính"}
    assert profile.voice_for("Nam chính") == "Bùi Thiện"


def test_small_recording_differences_still_match():
    profile = _profile()
    inside = 115.0 + MATCH_TOLERANCE_HZ - 1

    assert profile.match_speakers({"S0": inside}) == {"S0": "Nam chính"}


# --- KHÔNG được khớp ------------------------------------------------------

def test_a_stranger_is_not_forced_onto_an_existing_character():
    profile = _profile()
    outside = 115.0 + MATCH_TOLERANCE_HZ + 5

    assert profile.match_speakers({"S0": outside}) == {}, (
        "ngoài ngưỡng thì phải coi là người mới, không gán bừa giọng cũ"
    )


def test_speaker_without_usable_audio_is_skipped():
    """F0 = 0 nghĩa là không đủ dữ liệu voiced — không đoán (đúng nếp V36)."""
    profile = _profile()

    assert profile.match_speakers({"S0": 0.0}) == {}


def test_two_speakers_near_one_character_only_one_matches():
    """Một-đối-một: nếu không, 2 người nói sẽ cùng nhận một giọng — đúng cái
    lỗi mà tính năng này sinh ra để tránh."""
    profile = _profile()

    matched = profile.match_speakers({"S0": 114.0, "S1": 116.0})

    assert len(matched) == 1
    assert list(matched.values()) == ["Nam chính"]
    assert matched.get("S0") == "Nam chính", "người gần nhất phải thắng"


def test_empty_profile_matches_nothing():
    assert CharacterProfile(name="Mới").match_speakers({"S0": 120.0}) == {}


# --- Ghi nhớ sau mỗi tập --------------------------------------------------

def test_pitch_is_smoothed_not_overwritten():
    """Một tập thu âm tệ không được kéo lệch hồ sơ đã đúng qua nhiều tập."""
    profile = _profile()

    profile.remember({"S0": "Nam chính"}, {"S0": 135.0}, {"S0": "Bùi Thiện"})

    nam = next(c for c in profile.characters if c.name == "Nam chính")
    assert 115.0 < nam.median_f0 < 125.0, (
        f"F0 phải nhích nhẹ chứ không nhảy hẳn sang 135 (đang {nam.median_f0})"
    )
    assert nam.episodes == 4


def test_new_speaker_becomes_a_new_character():
    profile = _profile()

    profile.remember({}, {"SPEAKER_09": 160.0}, {"SPEAKER_09": "Bùi Vân"})

    names = [c.name for c in profile.characters]
    assert "SPEAKER_09" in names, "người lạ phải được thêm làm nhân vật mới"
    new = next(c for c in profile.characters if c.name == "SPEAKER_09")
    assert new.voice == "Bùi Vân"
    assert new.median_f0 == 160.0
    assert new.episodes == 1


def test_voice_change_is_remembered_for_next_episode():
    """Người dùng đổi giọng cho nhân vật ở tập này → tập sau dùng giọng mới."""
    profile = _profile()

    profile.remember({"S0": "Nam chính"}, {"S0": 115.0}, {"S0": "Phạm Tuyên"})

    assert profile.voice_for("Nam chính") == "Phạm Tuyên"


# --- Lưu trữ ---------------------------------------------------------------

def test_round_trip_keeps_everything(tmp_path):
    profile = _profile(pronouns="tôi – anh", glossary="显卡 = card đồ họa",
                       context="phim cổ trang")
    profile.save(str(tmp_path))

    loaded = CharacterProfile.load(str(tmp_path), "Phim A")

    assert loaded.pronouns == "tôi – anh"
    assert loaded.glossary == "显卡 = card đồ họa"
    assert loaded.context == "phim cổ trang"
    assert [c.name for c in loaded.characters] == ["Nam chính", "Nữ chính"]
    assert loaded.voice_for("Nữ chính") == "Bùi Trang"


def test_missing_profile_loads_empty_instead_of_failing(tmp_path):
    loaded = CharacterProfile.load(str(tmp_path), "Chưa từng có")

    assert loaded.characters == []
    assert loaded.name == "Chưa từng có"


def test_corrupt_profile_degrades_and_is_never_overwritten(tmp_path):
    """Hồ sơ hỏng không được làm sập lượt dub, và cũng không được đè lên.

    File của người dùng có thể chỉ lỗi cú pháp nhỏ mà họ tự sửa được — ghi đè
    là xoá mất công sức của họ.
    """
    path = CharacterProfile.path_for(str(tmp_path), "Phim A")
    path_obj = pathlib.Path(path)
    path_obj.write_text("{ hỏng cú pháp", encoding="utf-8")

    loaded = CharacterProfile.load(str(tmp_path), "Phim A")
    assert loaded.characters == [], "phải chạy tiếp như chưa có hồ sơ"

    loaded.remember({}, {"S0": 120.0}, {"S0": "X"})
    assert loaded.save(str(tmp_path)) == "", "không được ghi đè hồ sơ hỏng"
    assert path_obj.read_text(encoding="utf-8") == "{ hỏng cú pháp"
    assert path == str(path_obj)


def test_profile_file_is_human_editable_json(tmp_path):
    """Người dùng phải đổi được tên nhân vật bằng tay — đó là lý do dùng JSON
    dễ đọc chứ không phải định dạng nhị phân."""
    profile = _profile()
    profile.save(str(tmp_path))

    profile_path = pathlib.Path(CharacterProfile.path_for(str(tmp_path), "Phim A"))
    raw = json.loads(profile_path.read_text(encoding="utf-8"))
    assert raw["characters"][0]["name"] == "Nam chính"
    raw["characters"][0]["name"] = "Lý Tứ"
    profile_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    reloaded = CharacterProfile.load(str(tmp_path), "Phim A")
    assert [c.name for c in reloaded.characters] == ["Lý Tứ", "Nữ chính"]


# --- V59: khớp bằng speaker embedding ------------------------------------

def _vec(*values) -> list[float]:
    """Vector ngắn cho dễ đọc — cosine không quan tâm số chiều."""
    return list(values)


def _profile_with_embeddings() -> CharacterProfile:
    return CharacterProfile(
        name="Phim C",
        characters=[
            Character(name="Nam chính", voice="Bùi Thiện", median_f0=120.0,
                      embedding=_vec(1.0, 0.0, 0.0), episodes=2),
            Character(name="Nam phụ", voice="Bùi Thành", median_f0=124.0,
                      embedding=_vec(0.0, 1.0, 0.0), episodes=2),
        ],
    )


def test_embedding_separates_two_men_with_almost_identical_pitch():
    """Đây là LÝ DO V59 tồn tại — chỗ mà F0 chắc chắn lẫn.

    Hai người cùng giới, F0 chênh 4Hz (trong ngưỡng ±18Hz của V57) nên khớp
    bằng F0 rất dễ đảo người. Embedding thì tách bạch hoàn toàn.
    """
    profile = _profile_with_embeddings()

    matched = profile.match_speakers(
        pitches={"S0": 123.0, "S1": 121.0},
        embeddings={"S0": _vec(0.0, 0.99, 0.01),      # rõ ràng là Nam phụ
                    "S1": _vec(0.98, 0.02, 0.0)},     # rõ ràng là Nam chính
    )

    assert matched == {"S0": "Nam phụ", "S1": "Nam chính"}


def test_embedding_below_threshold_is_not_forced():
    profile = _profile_with_embeddings()

    matched = profile.match_speakers(
        pitches={},                                   # không có F0 để rơi về
        embeddings={"S0": _vec(0.5, 0.5, 0.7071)},    # cosine ~0.5 với cả hai
    )

    assert matched == {}, "dưới ngưỡng thì là người mới, không gán bừa"


def test_falls_back_to_pitch_when_profile_has_no_embeddings():
    """Hồ sơ lập trước V59 vẫn phải dùng được — không bắt làm lại từ đầu."""
    old_profile = CharacterProfile(
        name="Hồ sơ cũ",
        characters=[Character(name="Nam chính", voice="Bùi Thiện",
                              median_f0=115.0, episodes=5)],
    )

    matched = old_profile.match_speakers(
        pitches={"S0": 116.0}, embeddings={"S0": _vec(1.0, 0.0, 0.0)})

    assert matched == {"S0": "Nam chính"}


def test_embedding_wins_over_pitch_when_they_disagree():
    """Trộn 2 thang đo là sai — embedding phải được xét trọn vẹn TRƯỚC."""
    profile = _profile_with_embeddings()

    # F0 nói S0 giống "Nam chính" (120 vs 120), embedding nói là "Nam phụ".
    matched = profile.match_speakers(
        pitches={"S0": 120.0},
        embeddings={"S0": _vec(0.02, 0.99, 0.0)},
    )

    assert matched == {"S0": "Nam phụ"}, "embedding chính xác hơn, phải thắng"


def test_embedding_is_remembered_and_smoothed():
    profile = _profile_with_embeddings()

    profile.remember({"S0": "Nam chính"}, {"S0": 120.0}, {"S0": "Bùi Thiện"},
                     embeddings={"S0": _vec(0.0, 1.0, 0.0)})

    nam = next(c for c in profile.characters if c.name == "Nam chính")
    # Trộn 75% vector cũ (1,0,0) + 25% vector mới (0,1,0) → vẫn nghiêng hẳn
    # về chiều cũ, không nhảy hẳn sang vector của một tập.
    assert nam.embedding[0] > nam.embedding[1], (
        f"phải làm mượt chứ không đè: {nam.embedding}"
    )


def test_new_character_stores_a_normalised_embedding():
    profile = CharacterProfile(name="Mới")

    profile.remember({}, {"S0": 130.0}, {"S0": "Giọng X"},
                     embeddings={"S0": _vec(3.0, 4.0, 0.0)})   # norm = 5

    new = profile.characters[0]
    assert abs(sum(x * x for x in new.embedding) - 1.0) < 1e-6, (
        "lưu dạng đã chuẩn hoá để so cosine không phụ thuộc độ dài vector"
    )


def test_old_profile_file_without_embedding_field_still_loads(tmp_path):
    """Hồ sơ v1 (trước V59) phải nạp được, không nổ vì thiếu field."""
    import json as _json
    path = pathlib.Path(CharacterProfile.path_for(str(tmp_path), "Cũ"))
    path.write_text(_json.dumps({
        "version": 1, "name": "Cũ",
        "characters": [{"name": "A", "voice": "V", "median_f0": 110.0,
                        "gender": "male", "episodes": 3}],
    }), encoding="utf-8")

    loaded = CharacterProfile.load(str(tmp_path), "Cũ")

    assert loaded.characters[0].name == "A"
    assert loaded.characters[0].embedding == []


def test_unknown_future_fields_are_ignored_not_fatal(tmp_path):
    import json as _json
    path = pathlib.Path(CharacterProfile.path_for(str(tmp_path), "Mới"))
    path.write_text(_json.dumps({
        "version": 99, "name": "Mới",
        "characters": [{"name": "A", "voice": "V", "truong_la": 123}],
    }), encoding="utf-8")

    loaded = CharacterProfile.load(str(tmp_path), "Mới")
    assert loaded.characters[0].name == "A"


def test_vietnamese_names_do_not_collide(tmp_path):
    """Bug thật tìm được khi làm V59.

    Bản đầu vứt mọi ký tự ngoài ASCII nên «Phim Cổ Trang» và «Phim Có Trang»
    cùng ra một tên file — hai series ghi đè hồ sơ của nhau, trộn lẫn nhân
    vật. Với tên tiếng Việt thì đây là chuyện thường ngày.
    """
    a = CharacterProfile.path_for(str(tmp_path), "Phim Cổ Trang")
    b = CharacterProfile.path_for(str(tmp_path), "Phim Có Trang")

    assert a != b, "hai tên khác nhau KHÔNG được dùng chung một file hồ sơ"
    assert "co-trang" in a, f"tên file vẫn phải đọc được: {a}"


def test_same_name_always_maps_to_the_same_file(tmp_path):
    """Ổn định giữa các lần chạy — nếu không thì tập 2 không tìm thấy hồ sơ."""
    first = CharacterProfile.path_for(str(tmp_path), "Phim Cổ Trang")
    second = CharacterProfile.path_for(str(tmp_path), "Phim Cổ Trang")

    assert first == second


# --- V61: ngưỡng chỉnh được + biên an toàn + ghi điểm để hiệu chỉnh -------

def test_ambiguous_match_is_refused_even_above_threshold(monkeypatch):
    """Hai nhân vật đều na ná thì KHÔNG chọn bừa.

    Đoán bừa giữa hai người giống nhau là kiểu sai tệ nhất: nhân vật A nói
    bằng giọng nhân vật B suốt cả tập.
    """
    import autodub.character_profile as cp

    profile = CharacterProfile(
        name="Song sinh",
        characters=[
            Character(name="Anh", voice="V1", embedding=_vec(1.0, 0.0, 0.0)),
            Character(name="Em", voice="V2", embedding=_vec(0.999, 0.045, 0.0)),
        ],
    )

    matched = profile.match_speakers(
        pitches={}, embeddings={"S0": _vec(1.0, 0.02, 0.0)})

    assert matched == {}, "chênh lệch quá nhỏ giữa 2 ứng viên → coi là người mới"


def test_scores_are_reported_for_threshold_tuning():
    """Không có số liệu thì mọi ngưỡng đều là phỏng đoán."""
    profile = _profile_with_embeddings()

    profile.match_speakers(pitches={}, embeddings={"S0": _vec(0.0, 1.0, 0.0)})
    lines = profile.explain_matches()

    assert len(lines) == 1
    assert "S0" in lines[0] and "Nam phụ" in lines[0]
    assert "khớp" in lines[0]


def test_threshold_is_configurable_by_env(monkeypatch, tmp_path):
    """Chỉnh được bằng biến môi trường — hiệu chỉnh không cần sửa code."""
    import importlib

    monkeypatch.setenv("VOXDUB_EMBEDDING_THRESHOLD", "0.99")
    import autodub.character_profile as cp
    reloaded = importlib.reload(cp)
    try:
        profile = reloaded.CharacterProfile(
            name="X",
            characters=[reloaded.Character(name="A", voice="V",
                                           embedding=[1.0, 0.0, 0.0])],
        )
        # cosine ~0.98 — qua mặc định 0.72 nhưng KHÔNG qua ngưỡng 0.99 vừa đặt.
        matched = profile.match_speakers(
            pitches={}, embeddings={"S0": [0.98, 0.2, 0.0]})
        assert matched == {}
    finally:
        monkeypatch.delenv("VOXDUB_EMBEDDING_THRESHOLD", raising=False)
        importlib.reload(reloaded)
