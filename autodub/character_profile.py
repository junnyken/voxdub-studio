"""Hồ sơ nhân vật dùng lại qua nhiều tập của một series (mini-spec V57).

Vấn đề: dub cả một series thì hiện tập nào giọng nấy — nhân vật A ở tập 1 là
giọng nam trầm, sang tập 2 thành giọng khác, xem 5 tập là thấy loạn. Xưng hô
và thuật ngữ riêng của series cũng phải nhập lại từ đầu mỗi tập.

Điểm chốt kỹ thuật: nhãn diarization (``SPEAKER_00``…) **không ổn định giữa
các file** — cùng một người ở tập sau rất có thể mang nhãn khác. Nên không
khớp theo nhãn được, phải khớp theo ĐẶC TRƯNG GIỌNG.

Đặc trưng dùng ở đây là **F0 trung vị** (`diarization_voice_match.
estimate_speaker_pitch`) — thô, nhưng là thứ dự án ĐÃ tính sẵn cho mỗi lượt
dub từ V36, so sánh được giữa các file, và không kéo thêm một model nhận dạng
người nói nào vào bộ cài (Constraint 1). Đúng tinh thần "tín hiệu số học đơn
giản, đủ dùng" đã áp dụng cho V35/V36.

Nguyên tắc quan trọng nhất: **khớp sai tệ hơn không khớp**. Gán nhầm giọng
của nhân vật khác vào một người lạ làm hỏng cả tập theo cách người dùng chỉ
phát hiện khi đã nghe lại — nên ngoài ngưỡng tin cậy thì coi là nhân vật mới,
không đoán bừa.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field

from autodub.utils import save_json_atomic, setup_logging

logger = setup_logging("autodub.character_profile")

#: Lệch F0 tối đa (Hz) còn coi là cùng một người. ~18Hz đủ rộng để chịu khác
#: biệt do micro/nén audio giữa các tập, nhưng vẫn hẹp hơn khoảng cách điển
#: hình giữa giọng nam (~110Hz) và giọng nữ (~200Hz) — hai người khác giới
#: không thể khớp nhầm nhau.
MATCH_TOLERANCE_HZ = 18.0

#: Trọng số bản ghi mới khi cập nhật F0 (trung bình động). Cố ý NHỎ: một tập
#: thu âm tệ không được kéo lệch hồ sơ đã đúng qua nhiều tập.
PITCH_SMOOTHING = 0.25

PROFILE_VERSION = 1


@dataclass
class Character:
    """Một nhân vật của series."""
    name: str
    voice: str = ""
    median_f0: float = 0.0
    gender: str = ""
    #: Số tập đã gặp — dùng để người dùng biết nhân vật nào là chính.
    episodes: int = 0


@dataclass
class CharacterProfile:
    """Hồ sơ một series: nhân vật + quy ước dịch dùng chung."""
    name: str
    characters: list[Character] = field(default_factory=list)
    #: Quy ước dịch của riêng series này — áp lại mỗi tập, khỏi nhập lại.
    pronouns: str = ""
    glossary: str = ""
    context: str = ""
    version: int = PROFILE_VERSION

    # ------------------------------------------------------------ lưu trữ --

    @staticmethod
    def path_for(profiles_dir: str, name: str) -> str:
        return os.path.join(profiles_dir, f"{_slug(name)}.json")

    @classmethod
    def load(cls, profiles_dir: str, name: str) -> "CharacterProfile":
        """Nạp hồ sơ, hoặc trả hồ sơ RỖNG nếu chưa có/hỏng.

        Hồ sơ hỏng KHÔNG được làm sập lượt dub (Constraint 4): mất phần ghi
        nhớ thì lượt này rơi về hành vi V36 bình thường, còn hơn là không dub
        được gì.
        """
        path = cls.path_for(profiles_dir, name)
        if not os.path.isfile(path):
            return cls(name=name)
        try:
            with open(path, encoding="utf-8") as fh:
                raw = json.load(fh)
            return cls(
                name=raw.get("name") or name,
                characters=[Character(**c) for c in raw.get("characters", [])],
                pronouns=raw.get("pronouns", ""),
                glossary=raw.get("glossary", ""),
                context=raw.get("context", ""),
                version=int(raw.get("version") or PROFILE_VERSION),
            )
        except (OSError, ValueError, TypeError) as err:
            logger.warning(
                "Hồ sơ nhân vật «%s» đọc không được (%s) — lượt này chạy như "
                "chưa có hồ sơ, KHÔNG ghi đè file cũ.", name, err)
            profile = cls(name=name)
            profile._broken = True        # noqa: SLF001 — cờ nội bộ, xem save()
            return profile

    def save(self, profiles_dir: str) -> str:
        """Ghi hồ sơ xuống đĩa (nguyên tử).

        Hồ sơ đọc hỏng thì KHÔNG ghi đè: file của người dùng có thể chỉ lỗi cú
        pháp nhỏ và họ tự sửa được — đè lên là xoá mất công sức của họ.
        """
        if getattr(self, "_broken", False):
            logger.warning("Bỏ qua ghi đè hồ sơ hỏng «%s»", self.name)
            return ""
        os.makedirs(profiles_dir, exist_ok=True)
        path = self.path_for(profiles_dir, self.name)
        save_json_atomic(
            {
                "version": self.version,
                "name": self.name,
                "characters": [asdict(c) for c in self.characters],
                "pronouns": self.pronouns,
                "glossary": self.glossary,
                "context": self.context,
            },
            path,
        )
        return path

    # ----------------------------------------------------------- nghiệp vụ --

    def match_speakers(self, pitches: dict[str, float]) -> dict[str, str]:
        """Khớp người nói của tập này với nhân vật đã biết.

        Trả ``{speaker_label: character_name}`` — chỉ chứa những cặp khớp
        được. Người nói không khớp KHÔNG có mặt trong kết quả (caller tự xử
        như nhân vật mới).

        Ghép THAM LAM theo khoảng cách tăng dần và MỘT-ĐỐI-MỘT: cặp gần nhau
        nhất được chốt trước, nhân vật đã dùng thì không khớp cho người thứ
        hai (Constraint 3). Không có bước này thì 2 người nói có F0 gần nhau
        sẽ cùng nhận một giọng — đúng cái lỗi mà tính năng này sinh ra để
        tránh.
        """
        known = [c for c in self.characters if c.median_f0 > 0]
        if not known:
            return {}

        pairs = []
        for speaker, f0 in pitches.items():
            if not f0 or f0 <= 0:
                continue          # không đủ dữ liệu voiced → không đoán
            for character in known:
                distance = abs(f0 - character.median_f0)
                if distance <= MATCH_TOLERANCE_HZ:
                    pairs.append((distance, speaker, character.name))

        pairs.sort(key=lambda p: p[0])
        matched: dict[str, str] = {}
        used_characters: set[str] = set()
        for _distance, speaker, character_name in pairs:
            if speaker in matched or character_name in used_characters:
                continue
            matched[speaker] = character_name
            used_characters.add(character_name)
        return matched

    def voice_for(self, character_name: str) -> str:
        for c in self.characters:
            if c.name == character_name:
                return c.voice
        return ""

    def remember(self, speaker_to_character: dict[str, str],
                 pitches: dict[str, float], voices: dict[str, str],
                 genders: dict[str, str] | None = None) -> None:
        """Cập nhật hồ sơ sau một tập: làm mượt F0, thêm nhân vật mới.

        F0 cập nhật bằng TRUNG BÌNH ĐỘNG chứ không đè giá trị mới — một tập
        thu âm tệ không được phép kéo lệch hồ sơ đã đúng qua nhiều tập.
        """
        genders = genders or {}
        by_name = {c.name: c for c in self.characters}

        for speaker, f0 in pitches.items():
            name = speaker_to_character.get(speaker)
            voice = voices.get(speaker, "")
            if name and name in by_name:
                c = by_name[name]
                if f0 > 0:
                    c.median_f0 = round(
                        (1 - PITCH_SMOOTHING) * c.median_f0 + PITCH_SMOOTHING * f0, 2)
                if voice:
                    c.voice = voice
                c.episodes += 1
                continue

            if not name:
                # Nhân vật mới: đặt tên tạm theo nhãn của tập này. Người dùng
                # đổi tên trong file JSON được — đó là lý do hồ sơ để dạng
                # text dễ đọc chứ không phải nhị phân.
                name = _unique_name(speaker, by_name)
            new = Character(name=name, voice=voice, median_f0=max(0.0, f0),
                            gender=genders.get(speaker, ""), episodes=1)
            self.characters.append(new)
            by_name[name] = new


def _slug(name: str) -> str:
    import re
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", name.strip()).strip("-").lower()
    return slug or "khong-ten"


def _unique_name(base: str, taken: dict) -> str:
    name = base
    i = 2
    while name in taken:
        name = f"{base}-{i}"
        i += 1
    return name
