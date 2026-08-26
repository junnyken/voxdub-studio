"""Giá mỗi câu thoại — MỘT chỗ tính, mọi câu chữ đều hỏi ở đây.

Vì sao cần tệp này (mini-spec D1e): giá từng bị gõ thẳng vào ba câu chữ khác
nhau trong giao diện — bảng tóm tắt bước 5, gợi ý ô "Dịch tự động", và dòng
giải thích ở bước Chạy dịch. Cả ba đều ghi "12 Vox/câu" cho lượt dịch tự
động, đúng khi máy chủ là đường duy nhất, SAI kể từ khi người dùng chọn được
dịch ngoại tuyến (lúc đó không có phần cộng thêm, còn 10).

Đây là lớp lỗi #5 của dự án (FEATURES.md §6): câu chữ nói về tiền đi lệch
khỏi mã. Chữa bằng cách bỏ hẳn con số khỏi câu chữ, không phải sửa ba chuỗi
rồi hy vọng lần sau ai đó nhớ sửa cả ba.

Giá LẤY TỪ MÁY CHỦ khi có (`app_config()["pricing"]`) — đổi giá bên máy chủ
là app hiện đúng ngay, không cần phát hành lại. Chỉ đọc bản đã nhớ đệm, cố ý
KHÔNG gọi mạng: hàm này chạy trong lúc dựng nhãn trên luồng giao diện, một
lượt gọi mạng ở đó là một lần app đứng hình.
"""
from __future__ import annotations

from autodub.utils import setup_logging

logger = setup_logging("autodub_gui.gia")

#: Dùng khi chưa hỏi được máy chủ. Khớp mặc định trong
#: control_server/src/services/config.service.js.
GIA_MAC_DINH = (10, 2, 20)


def bang_gia() -> tuple[int, int, int]:
    """``(nền mỗi câu, cộng thêm khi dịch tự động, gói tiêu đề + mô tả)``."""
    try:
        from autodub.saas_client import get_client, is_configured

        if not is_configured():
            return GIA_MAC_DINH
        client = get_client()
        # Chỉ lấy bản đã nhớ đệm — `_config` được nạp lúc khởi động.
        cau_hinh = getattr(client, "_config", None) or {}
        gia = cau_hinh.get("pricing") or {}
        if not gia:
            return GIA_MAC_DINH
        return (int(gia.get("segmentBase", GIA_MAC_DINH[0])),
                int(gia.get("segmentAutoTranslate", GIA_MAC_DINH[1])),
                int(gia.get("metadata", GIA_MAC_DINH[2])))
    except Exception as e:  # noqa: BLE001 — nhãn hiển thị không được làm sập app
        logger.warning(f"Chưa lấy được bảng giá từ máy chủ ({e}) — hiện giá "
                       "mặc định. Số thật vẫn do máy chủ chốt lúc giữ chỗ.")
        return GIA_MAC_DINH


def moi_cau(settings, auto_translate: bool) -> int:
    """Giá một câu thoại theo đúng lựa chọn hiện tại của người dùng.

    Dịch ngoại tuyến KHÔNG có phần cộng thêm: bản dịch do máy người dùng làm,
    máy chủ không chạy gì cả (xem `pipeline._run_impl`, cờ `dich_ngoai_tuyen`
    đi thẳng vào `create_hold(auto_translate=False)`).
    """
    nen, them, _meta = bang_gia()
    if not auto_translate:
        return nen
    if getattr(settings, "translate_mode", "server") == "offline":
        return nen
    return nen + them


def gia_goi_dang_bai() -> int:
    return bang_gia()[2]
