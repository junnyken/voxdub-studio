"""Danh mục giọng CapCut — đọc ``Voice.json`` trong gói, KHÔNG gọi mạng.

Tách khỏi :mod:`autodub.speech.tts.voices` để module danh mục chung không
phải biết chi tiết định dạng của CapCut, và để giao diện tra cứu tên giọng
mà không kéo theo client HTTP.

Tên hiển thị trong ``Voice.json`` có dạng «Thanh Lan - Nữ ngọt ngào»: phần
trước dấu gạch là TÊN giọng (định danh trong app, phải là duy nhất), phần
sau chỉ để mô tả.
"""
from __future__ import annotations

import hashlib
import json
import os
import uuid

from autodub.speech.tts.capcut_api.config import DEFAULT_DEVICE, catalog_file
from autodub.utils import save_json_atomic

#: Ngôn ngữ duy nhất app dùng — Voice.json còn nhiều giọng ngoại ngữ khác.
LANG = "vi-VN"

#: Giọng mặc định khi catalog offline rỗng (máy chưa cài VieNeu).
DEFAULT_CAPCUT_VOICE = "Minh Trang"


#: mini-spec V20 (docs/PLAN.md, Phase E) — bug thật tìm ra khi audit: heuristic
#: cũ CHỈ nhận diện giọng nữ tiếng Việt (khớp voice_type theo 3 mã BV cụ thể
#: hoặc chuỗi "female" LITERAL trong voice_type). Với catalog tiếng Anh (V8/
#: V11), nhiều giọng ghi rõ giới tính ngay trong TÊN hiển thị nhưng KHÔNG có
#: "female" trong voice_type — bị mặc định gắn nhầm thành "male": xác nhận
#: thật qua Voice.json — "Energetic Famale" (voice_type=BV503_streaming),
#: "American Female" (BV029_streaming) đều bị gắn "male" trước khi sửa. Hậu
#: quả THẬT (không chỉ hiển thị sai): bộ lọc giới tính trong Thư viện giọng
#: đọc (autodub_gui/pages/voice_library.py) ẨN MẤT các giọng nữ này khỏi kết
#: quả lọc "Nữ" — người dùng không tìm thấy giọng dù nó tồn tại.
#:
#: Vài giọng ("Jenny" — voice_type "en-US-JennyMultilingualNeural") không có
#: TÍN HIỆU CHỮ nào ở cả voice_type lẫn tên hiển thị (không suy được từ text)
#: — đây là giọng "Jenny" nổi tiếng của Microsoft Azure Neural TTS, giới
#: tính nữ là thông tin công khai đã biết (voice gallery chính thức của
#: Microsoft), không phải suy đoán — liệt kê tường minh, không lẫn vào
#: heuristic chung để không code cứng thêm ngoại lệ không kiểm chứng được.
_KNOWN_VOICE_TYPE_GENDER = {
    "en-us-jennymultilingualneural": "female",
}


def _gender_of(voice_type: str, display_name: str = "") -> str:
    """Suy giới tính từ ``voice_type`` VÀ tên hiển thị đầy đủ.

    Giọng hiệu ứng/không rõ tín hiệu chữ nào mặc định dựng trên nền nam
    (giữ đúng quy ước cũ, xem V8) — chỉ mở rộng nguồn tín hiệu để bắt đúng
    các giọng ghi rõ giới tính trong TÊN thay vì chỉ trong voice_type.
    """
    vt = voice_type.lower()
    if vt in _KNOWN_VOICE_TYPE_GENDER:
        return _KNOWN_VOICE_TYPE_GENDER[vt]
    text = f"{voice_type} {display_name}".lower()
    # "famale"/"famle" là lỗi chính tả THẬT tìm thấy trong chính Voice.json
    # ("Energetic Famale", "Dolly famle") — không phải suy đoán, đọc trực
    # tiếp từ dữ liệu catalog.
    if ("female" in text or "famale" in text or "famle" in text or "nữ" in text
            or vt.startswith("bv421") or vt.startswith("bv074")
            or vt.startswith("bv562")):
        return "female"
    return "male"


def _split_name(display_name: str) -> tuple[str, str]:
    """«Thanh Lan - Nữ ngọt ngào» → («Thanh Lan», «Nữ ngọt ngào»)."""
    name, _, description = display_name.partition(" - ")
    return name.strip(), description.strip()


#: Cache theo ngôn ngữ — mini-spec V8 (docs/PLAN.md) generalize entries()
#: nhận tham số ``lang`` thay vì hardcode LANG, để dành cho ngôn ngữ đích
#: khác tiếng Việt. Mặc định vẫn là LANG (vi-VN) — mọi lời gọi cũ không
#: truyền tham số tiếp tục chạy ĐÚNG Y HỆT trước đây (0 regression).
_entries_by_lang: dict[str, list[dict]] = {}


def entries(lang: str = LANG) -> list[dict]:
    """Các mục cùng ngôn ngữ trong Voice.json, đã tách tên và suy giới tính.

    Mỗi mục: ``{"name", "description", "gender", "voice_type",
    "resource_id"}``. Trả về danh sách rỗng nếu thiếu file (bản đóng gói
    hỏng) — app vẫn chạy được bằng giọng offline.
    """
    if lang in _entries_by_lang:
        return _entries_by_lang[lang]
    path = catalog_file()
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        _entries_by_lang[lang] = []
        return _entries_by_lang[lang]
    result: list[dict] = []
    seen: dict[str, int] = {}
    for item in raw:
        if not isinstance(item, dict) or item.get("lang") != lang:
            continue
        display_name = str(item.get("display_name", ""))
        name, description = _split_name(display_name)
        voice_type = str(item.get("voice_type", ""))
        if not name or not voice_type:
            continue
        # mini-spec V21 (docs/PLAN.md, Phase E) — bug thật tìm ra ở V20:
        # 2 mục trùng TÊN hiển thị (vd "Trickster" — 2 voice_type khác
        # nhau) trước đây bị ``continue`` (bỏ hẳn mục thứ 2, không ai chọn
        # được nó dù tồn tại thật trong Voice.json). Giờ đánh số phân biệt
        # thay vì bỏ — "Trickster" và "Trickster (2)" đều chọn được.
        if name in seen:
            seen[name] += 1
            name = f"{name} ({seen[name]})"
        else:
            seen[name] = 1
        result.append({
            "name": name,
            "description": description,
            "gender": _gender_of(voice_type, display_name),
            "voice_type": voice_type,
            "resource_id": str(item.get("resource_id", "")),
        })
    _entries_by_lang[lang] = result
    return result


def names(lang: str = LANG) -> set[str]:
    """Tên mọi giọng CapCut của 1 ngôn ngữ — dùng để định tuyến engine."""
    return {e["name"] for e in entries(lang)}


def lookup(name: str, lang: str = LANG) -> dict | None:
    """Mục catalog của một tên giọng, hoặc None nếu không phải giọng CapCut."""
    for entry in entries(lang):
        if entry["name"] == name:
            return entry
    return None


def device_file() -> str:
    """Nơi cất hồ sơ thiết bị CapCut (ghi được cả khi chạy từ bản đóng gói)."""
    return os.path.join(os.path.expanduser("~"), ".voxdub_cache",
                        "capcut_device.json")


def _fresh_ids(seed: str | None = None) -> dict:
    """Bộ ba định danh 19 chữ số. ``seed`` cố định → luôn ra cùng bộ.

    Lần đầu ta gieo bằng vân tay máy để một máy có định danh ổn định; khi bị
    máy chủ chặn thì gieo ngẫu nhiên để lấy định danh khác hẳn.
    """
    if seed is None:
        seed = uuid.uuid4().hex + uuid.uuid4().hex
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()

    def _id(chunk: str) -> str:
        # Cùng dạng ID thật của CapCut: 19 chữ số, mở đầu bằng 7.
        return "7" + str(int(chunk, 16) % 10 ** 18).zfill(18)

    return {"device_id": _id(digest[:16]),
            "iid": _id(digest[16:32]),
            "tdid": _id(digest[32:48])}


def device_profile() -> dict:
    """Hồ sơ thiết bị CapCut, đọc từ đĩa; lần đầu thì tạo và ghi lại.

    Trước đây hồ sơ được suy thẳng từ vân tay máy, không lưu gì cả. Cách đó
    hỏng theo kiểu không cứu được: máy chủ CapCut chặn một device_id (trả
    ``ret: -6, shark block only``) thì máy đó vĩnh viễn không đọc được nữa vì
    mỗi lần chạy lại suy ra đúng ID đã bị chặn. Nay hồ sơ nằm trong tệp để
    :func:`rotate_device` thay được bằng ID mới khi bị chặn.
    """
    from autodub.device_id import get_fingerprint

    path = device_file()
    try:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        if all(saved.get(k) for k in ("device_id", "iid", "tdid")):
            return {**DEFAULT_DEVICE, **saved}
    except (OSError, ValueError):
        pass
    try:
        seed = get_fingerprint()
    except Exception:  # noqa: BLE001 — không đọc được vân tay thì lấy ngẫu nhiên
        seed = None
    return _write_profile(_fresh_ids(seed))


def rotate_device() -> dict:
    """Cấp hồ sơ thiết bị mới và ghi đè lên tệp — dùng khi bị máy chủ chặn."""
    return _write_profile(_fresh_ids())


def _write_profile(ids: dict) -> dict:
    profile = {**DEFAULT_DEVICE, **ids,
               "region": "VN", "loc": "VN", "lan": "vi-VN"}
    try:
        save_json_atomic(profile, device_file())
    except OSError:
        pass  # không ghi được thì vẫn chạy, chỉ là lần sau lại đổi ID
    return profile
