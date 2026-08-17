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

#: Ngưỡng cosine coi là CÙNG một người, khi có embedding thật (mini-spec
#: V59). Embedding pyannote cho cùng người thường >0.8, người khác thường
#: <0.5 — 0.72 nằm giữa, nghiêng về phía thận trọng vì khớp sai tệ hơn không
#: khớp.
EMBEDDING_MATCH_THRESHOLD = 0.72

PROFILE_VERSION = 2


@dataclass
class Character:
    """Một nhân vật của series."""
    name: str
    voice: str = ""
    median_f0: float = 0.0
    gender: str = ""
    #: Vector đặc trưng giọng do pyannote tính (mini-spec V59). Rỗng với hồ
    #: sơ lập trước V59 hoặc khi pyannote bản cũ không trả embedding — lúc đó
    #: khớp rơi về F0 như V57.
    embedding: list[float] = field(default_factory=list)
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
                # Bỏ field lạ thay vì nổ: hồ sơ v1 (trước V59) thiếu
                # `embedding`, hồ sơ do bản mới hơn ghi có thể có field chưa
                # biết — cả hai đều phải nạp được.
                characters=[_character_from(c) for c in raw.get("characters", [])],
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

    def match_speakers(self, pitches: dict[str, float],
                       embeddings: dict[str, list[float]] | None = None,
                       ) -> dict[str, str]:
        """Khớp người nói của tập này với nhân vật đã biết.

        **V59**: có embedding cho CẢ hai phía thì khớp bằng cosine (chính xác
        hơn hẳn), thiếu một phía thì rơi về F0 như V57. Trộn hai thang đo
        trong cùng một lượt xếp hạng là sai — cosine 0.9 và lệch 3Hz không so
        sánh được với nhau — nên embedding được xét TRƯỚC và trọn vẹn, xong
        mới tới F0 cho những ai còn lại.

        Trả ``{speaker_label: character_name}`` — chỉ chứa những cặp khớp
        được. Người nói không khớp KHÔNG có mặt trong kết quả (caller tự xử
        như nhân vật mới).

        Ghép THAM LAM theo khoảng cách tăng dần và MỘT-ĐỐI-MỘT: cặp gần nhau
        nhất được chốt trước, nhân vật đã dùng thì không khớp cho người thứ
        hai (Constraint 3). Không có bước này thì 2 người nói có F0 gần nhau
        sẽ cùng nhận một giọng — đúng cái lỗi mà tính năng này sinh ra để
        tránh.
        """
        embeddings = embeddings or {}
        matched: dict[str, str] = {}
        used_characters: set[str] = set()

        # --- Vòng 1: embedding (chính xác hơn, ưu tiên tuyệt đối) ---------
        emb_pairs = []
        for speaker, vector in embeddings.items():
            if not vector:
                continue
            for character in self.characters:
                if not character.embedding:
                    continue
                score = _cosine(vector, character.embedding)
                if score >= EMBEDDING_MATCH_THRESHOLD:
                    # Xếp theo khoảng cách (1 - cosine) để dùng chung một
                    # chiều "càng nhỏ càng gần" với vòng F0 bên dưới.
                    emb_pairs.append((1.0 - score, speaker, character.name))

        # --- Vòng 2: F0 cho những ai vòng 1 không phủ (hồ sơ cũ, pyannote
        # cũ, hoặc người nói thiếu embedding) -----------------------------
        f0_pairs = []
        for speaker, f0 in pitches.items():
            if not f0 or f0 <= 0:
                continue          # không đủ dữ liệu voiced → không đoán
            for character in self.characters:
                if character.median_f0 <= 0:
                    continue
                distance = abs(f0 - character.median_f0)
                if distance <= MATCH_TOLERANCE_HZ:
                    f0_pairs.append((distance, speaker, character.name))

        for pairs in (sorted(emb_pairs, key=lambda p: p[0]),
                      sorted(f0_pairs, key=lambda p: p[0])):
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
                 genders: dict[str, str] | None = None,
                 embeddings: dict[str, list[float]] | None = None) -> None:
        """Cập nhật hồ sơ sau một tập: làm mượt F0, thêm nhân vật mới.

        F0 cập nhật bằng TRUNG BÌNH ĐỘNG chứ không đè giá trị mới — một tập
        thu âm tệ không được phép kéo lệch hồ sơ đã đúng qua nhiều tập.
        """
        genders = genders or {}
        embeddings = embeddings or {}
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
                new_vec = embeddings.get(speaker) or []
                if new_vec:
                    # Trung bình động rồi chuẩn hoá lại — cùng lý do làm mượt
                    # F0: một tập thu âm tệ không được kéo lệch hồ sơ đã đúng.
                    c.embedding = _blend(c.embedding, new_vec, PITCH_SMOOTHING)
                c.episodes += 1
                continue

            if not name:
                # Nhân vật mới: đặt tên tạm theo nhãn của tập này. Người dùng
                # đổi tên trong file JSON được — đó là lý do hồ sơ để dạng
                # text dễ đọc chứ không phải nhị phân.
                name = _unique_name(speaker, by_name)
            new = Character(name=name, voice=voice, median_f0=max(0.0, f0),
                            gender=genders.get(speaker, ""), episodes=1,
                            embedding=_normalise(embeddings.get(speaker) or []))
            self.characters.append(new)
            by_name[name] = new


def apply_translation_context(profile: "CharacterProfile", settings) -> list[str]:
    """Áp xưng hô/thuật ngữ/ngữ cảnh của series LÊN cấu hình của lượt chạy.

    Chủ dự án chốt (2026-08-18): **hồ sơ series ĐÈ cài đặt chung**. Lý do:
    người dùng chọn hồ sơ "Phim A" là đang nói "lần này tôi làm phim A", nên
    quy ước của phim A phải thắng cấu hình mặc định của toàn app.

    Nhưng chỉ đè bằng những trường hồ sơ CÓ điền. Trường trống KHÔNG được xoá
    cài đặt chung — chọn một hồ sơ mới lập (chưa điền gì) mà bị mất sạch xưng
    hô đã cấu hình là kiểu mất mát âm thầm tệ nhất.

    Sửa TẠI CHỖ trên đối tượng settings của lượt chạy (không ghi xuống file
    `.env`): hồ sơ chỉ có hiệu lực cho lượt này, không lặng lẽ đổi cấu hình
    mặc định của người dùng.

    Trả về danh sách tên trường đã đè, để ghi log cho người dùng thấy.
    """
    applied: list[str] = []
    for field_name, attr in (("pronouns", "translate_pronouns"),
                             ("glossary", "translate_glossary"),
                             ("context", "translate_context")):
        value = str(getattr(profile, field_name, "") or "").strip()
        if not value:
            continue
        if str(getattr(settings, attr, "") or "").strip() == value:
            continue          # đã trùng, không tính là đè
        setattr(settings, attr, value)
        applied.append(field_name)
    return applied


def _character_from(raw: dict) -> Character:
    known = {f for f in Character.__dataclass_fields__}
    return Character(**{k: v for k, v in raw.items() if k in known})


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity. Vector lệch chiều → 0.0 (không khớp), không nổ."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _normalise(vector: list[float]) -> list[float]:
    norm = sum(x * x for x in vector) ** 0.5
    return [round(x / norm, 6) for x in vector] if norm > 0 else []


def _blend(old: list[float], new: list[float], weight: float) -> list[float]:
    """Trung bình động 2 vector rồi chuẩn hoá lại."""
    new_n = _normalise(new)
    if not old or len(old) != len(new_n):
        return new_n
    return _normalise([(1 - weight) * o + weight * n for o, n in zip(old, new_n)])


def _slug(name: str) -> str:
    """Tên file cho một hồ sơ — vừa đọc được, vừa KHÔNG đụng nhau.

    Bug thật, test bắt được lúc làm V59: bản đầu chỉ vứt mọi ký tự ngoài
    ASCII, nên «Phim Cổ Trang» và «Phim Có Trang» cùng ra `phim-c-trang` —
    hai series khác nhau ghi đè hồ sơ của nhau, trộn lẫn nhân vật. Với tên
    tiếng Việt thì đây là chuyện thường ngày, không phải ca hiếm.

    Sửa hai tầng: bỏ dấu ĐÚNG cách (Cổ → Co) cho tên đọc được, rồi gắn thêm
    6 ký tự băm của tên GỐC để hai tên khác nhau không bao giờ chung file.
    """
    import hashlib
    import re
    import unicodedata

    stripped = "".join(
        ch for ch in unicodedata.normalize("NFD", name.strip())
        if unicodedata.category(ch) != "Mn"
    ).replace("đ", "d").replace("Đ", "D")
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", stripped).strip("-").lower()
    digest = hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:6]
    return f"{slug or 'ho-so'}-{digest}"


def _unique_name(base: str, taken: dict) -> str:
    name = base
    i = 2
    while name in taken:
        name = f"{base}-{i}"
        i += 1
    return name
