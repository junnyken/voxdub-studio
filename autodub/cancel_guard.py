"""Cho nút Dừng cắt ngang được các bước chạy bằng tiến trình con.

Vì sao cần (mini-spec V79): `ProgressReporter.check_cancelled()` chỉ được gọi
GIỮA hai bước, nên bấm Dừng lúc đang tách nhạc nền (Demucs, 10+ phút) hay
đang xuất video (ffmpeg) thì **không có tác dụng gì** cho tới khi bước đó tự
xong. Người dùng thấy nút bấm rồi mà máy vẫn cày — y hệt ca canh chữ karaoke
đã sửa ở V76.

Hai bài học được đóng gói sẵn ở đây, để lần sau nối thêm bước mới không phải
học lại:

- **V72**: kiểm cờ rồi đi chờ chỉ đúng khi cái chờ NGẮN. Với `communicate()`
  hay `readline()` hàng chục phút thì phải GIẾT tiến trình con — giết xong
  ống dữ liệu đóng, lời gọi đang chờ trả về ngay.
- **V74/V76**: giết tiến trình làm bước đó "hỏng" theo đủ kiểu (mã thoát khác
  0, JSON rỗng, timeout). Nếu để nguyên, tầng trên hiểu là LỖI rồi chạy
  đường dự phòng — Demucs sẽ "tách hỏng" và video ra thiếu nhạc nền, dù người
  dùng chỉ bấm Dừng. Nên ở đây mọi lỗi phát sinh SAU khi cờ bật đều được đổi
  thành :class:`PipelineCancelled`.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from autodub.progress import PipelineCancelled

_LOI_DUNG = "Đã dừng theo yêu cầu."


def _canh_mot_tien_trinh(proc, cancel_event, xong) -> None:
    """Canh cờ Dừng, giết ``proc`` khi cờ bật.

    Tự kết thúc khi tiến trình con đã thoát — nhờ vậy nơi gọi không bắt buộc
    phải nhớ tắt luồng canh (thân hàm dài, nhiều đường `return`/`raise` thì
    kiểu gì cũng có đường quên).
    """
    while not xong.is_set() and proc.poll() is None:
        if cancel_event.wait(0.3):
            try:
                proc.kill()
            except Exception:
                pass
            return


def kiem_dung(cancel_event) -> None:
    """Ném :class:`PipelineCancelled` nếu người dùng đã bấm Dừng."""
    if cancel_event is not None and cancel_event.is_set():
        raise PipelineCancelled(_LOI_DUNG)


@contextmanager
def giet_khi_dung(proc, cancel_event):
    """Giết ``proc`` ngay khi cờ Dừng bật, và báo đúng lý do ra ngoài.

    Dùng bọc quanh đoạn CHỜ tiến trình con (``communicate``/vòng đọc). Không
    có ``cancel_event`` thì hoàn toàn trong suốt — mọi lời gọi cũ giữ nguyên
    hành vi.
    """
    if cancel_event is None:
        yield
        return

    xong = threading.Event()

    threading.Thread(target=_canh_mot_tien_trinh, args=(proc, cancel_event, xong),
                     daemon=True).start()
    try:
        yield
    except PipelineCancelled:
        raise
    except BaseException:
        # Lỗi này gần như chắc chắn LÀ hậu quả của cú giết ở trên.
        if cancel_event.is_set():
            raise PipelineCancelled(_LOI_DUNG) from None
        raise
    else:
        # Chạy xong sạch sẽ nhưng cờ đã bật giữa chừng: kết quả có thể dở
        # dang (tiến trình bị giết đúng lúc gần xong) — vẫn tính là đã dừng.
        if cancel_event.is_set():
            raise PipelineCancelled(_LOI_DUNG)
    finally:
        xong.set()


def bat_dau_canh(proc, cancel_event):
    """Bản không-``with`` của :func:`giet_khi_dung`, trả hàm dừng canh.

    Dùng cho thân hàm dài đã có sẵn `try/finally` riêng, bọc thêm một tầng
    `with` chỉ để thụt lề lại cả trăm dòng là đổi nhiều mà chẳng rõ hơn.
    Nơi gọi tự chịu trách nhiệm đổi lỗi thành :class:`PipelineCancelled`
    (thường bằng :func:`kiem_dung` ở tầng trên).
    """
    if cancel_event is None:
        return lambda: None

    xong = threading.Event()
    threading.Thread(target=_canh_mot_tien_trinh, args=(proc, cancel_event, xong),
                     daemon=True).start()
    return xong.set
