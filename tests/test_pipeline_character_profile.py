"""Mini-spec V57 — đường ráp hồ sơ nhân vật vào pipeline.

Test ở tầng `_apply_character_profile` chứ không chạy cả pipeline: chạy dub
thật chỉ để kiểm một bản đồ giọng là quá đắt, mà đây đúng là chỗ quyết định
nhân vật có giữ được giọng hay không.

Ba điều phải đúng:
* nhân vật cũ ghi đè được gán tự động của V36 (nếu không thì tính năng vô nghĩa),
* người lạ giữ nguyên giọng V36 vừa gán và được ghi vào hồ sơ cho tập sau,
* hồ sơ hỏng KHÔNG được làm hỏng lượt dub.
"""
from __future__ import annotations

import pytest

from autodub.character_profile import Character, CharacterProfile
from autodub.pipeline import DubPipeline


class _Settings:
    def __init__(self, out):
        self.output_dir = str(out)


@pytest.fixture()
def pipeline():
    return DubPipeline.__new__(DubPipeline)      # không cần __init__ nặng


def _seed_profile(tmp_path, name="Phim A"):
    profile = CharacterProfile(
        name=name,
        characters=[Character(name="Nam chính", voice="Bùi Thiện",
                              median_f0=115.0, gender="male", episodes=2)],
    )
    profile.save(str(tmp_path / "character_profiles"))
    return profile


def test_known_character_overrides_the_automatic_assignment(pipeline, tmp_path):
    """Chính là lý do V57 tồn tại: tập sau phải giữ đúng giọng tập trước."""
    _seed_profile(tmp_path)
    settings = _Settings(tmp_path)

    # V36 vừa gán nhầm một giọng khác cho người nói này.
    voice_map = pipeline._apply_character_profile(
        "Phim A", settings,
        pitches={"SPEAKER_02": 116.0},
        genders={"SPEAKER_02": "male"},
        voice_map={"SPEAKER_02": "Giọng ngẫu nhiên"},
    )

    assert voice_map["SPEAKER_02"] == "Bùi Thiện"


def test_stranger_keeps_the_v36_voice_and_is_remembered(pipeline, tmp_path):
    _seed_profile(tmp_path)
    settings = _Settings(tmp_path)

    voice_map = pipeline._apply_character_profile(
        "Phim A", settings,
        pitches={"SPEAKER_07": 240.0},          # xa nhân vật đã biết
        genders={"SPEAKER_07": "female"},
        voice_map={"SPEAKER_07": "Bùi Trang"},
    )

    assert voice_map["SPEAKER_07"] == "Bùi Trang", "người lạ giữ giọng V36 gán"

    saved = CharacterProfile.load(str(tmp_path / "character_profiles"), "Phim A")
    names = [c.name for c in saved.characters]
    assert "SPEAKER_07" in names, "người lạ phải được ghi lại cho tập sau"
    assert saved.voice_for("SPEAKER_07") == "Bùi Trang"


def test_second_episode_reuses_what_the_first_one_learned(pipeline, tmp_path):
    """Mô phỏng 2 tập liên tiếp — không seed sẵn, để hồ sơ tự hình thành."""
    settings = _Settings(tmp_path)

    # Tập 1: chưa có hồ sơ, V36 gán giọng, hồ sơ ghi lại.
    pipeline._apply_character_profile(
        "Series B", settings,
        pitches={"SPEAKER_00": 120.0},
        genders={"SPEAKER_00": "male"},
        voice_map={"SPEAKER_00": "Phạm Tuyên"},
    )

    # Tập 2: cùng người, nhãn khác, V36 gán giọng khác.
    voice_map = pipeline._apply_character_profile(
        "Series B", settings,
        pitches={"SPEAKER_03": 121.5},
        genders={"SPEAKER_03": "male"},
        voice_map={"SPEAKER_03": "Một giọng khác hẳn"},
    )

    assert voice_map["SPEAKER_03"] == "Phạm Tuyên", (
        "cùng một người ở tập 2 phải nhận lại giọng tập 1, dù nhãn đã đổi"
    )


def test_a_broken_profile_never_breaks_the_run(pipeline, tmp_path):
    profiles = tmp_path / "character_profiles"
    profiles.mkdir()
    (profiles / "phim-a.json").write_text("{ hỏng", encoding="utf-8")
    settings = _Settings(tmp_path)

    voice_map = pipeline._apply_character_profile(
        "Phim A", settings,
        pitches={"S0": 115.0}, genders={"S0": "male"},
        voice_map={"S0": "Bùi Thiện"},
    )

    assert voice_map == {"S0": "Bùi Thiện"}, "lượt dub phải chạy tiếp bình thường"


def test_profiles_live_next_to_the_output_folder(pipeline, tmp_path):
    """Người dùng phải tìm thấy hồ sơ để sửa tay — không giấu ở chỗ lạ."""
    settings = _Settings(tmp_path)

    path = DubPipeline._profiles_dir(settings)

    assert path.endswith("character_profiles")
    assert str(tmp_path) in path
