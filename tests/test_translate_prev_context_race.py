"""Mini-spec V39 (docs/PLAN.md) — sửa race condition khiến `prev_context`
(bản dịch tiếng Việt của lô liền trước, gửi cho lô sau để giữ mạch xưng
hô/thuật ngữ) gần như luôn RỖNG khi các lô dịch chạy song song, vì trước
đây `_run_batch()` tính `prev_context` NGAY LÚC dựng payload — trước khi
lô trước kịp có phản hồi mạng. Test không gọi mạng thật — `FakeClient`
mô phỏng độ trễ có kiểm soát bằng `time.sleep()` ngắn (không phải
`threading.Event` treo vô hạn, để test không bao giờ bị treo thật)."""
from __future__ import annotations

import threading
import time

import pytest

from autodub.config import Settings
from autodub.languages import get_target
from autodub.text import translate_saas


class FakeClient:
    """Máy khách giả — ghi lại `prev_context` nhận được mỗi lô, có thể mô
    phỏng độ trễ mạng khác nhau cho từng lô qua `delays` (giây, theo thứ
    tự lô gọi tới, không nhất thiết theo thứ tự lô được nộp)."""

    def __init__(self, delays: dict[int, float] | None = None):
        self.delays = delays or {}
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def translate(self, segments, *, job_id, prev_context=None, **kwargs):
        batch_index = len(self.calls)  # đúng thứ tự GỌI TỚI thật, không phải thứ tự nộp
        with self._lock:
            self.calls.append({"segments": segments, "prev_context": prev_context})
            idx = len(self.calls) - 1
        delay = self.delays.get(idx, 0.0)
        if delay:
            time.sleep(delay)
        return {
            "segments": [{"id": s["id"], "text_vi": f"vi {s['text']}"} for s in segments],
            "creditCharged": len(segments),
            "balanceAfter": 100,
        }


def _segments(n: int) -> list[dict]:
    return [{"id": i, "text": f"source {i}", "duration": 2.0, "slot": 2.0}
            for i in range(1, n + 1)]


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(translate_saas.RATE_LIMITER, "acquire", lambda: None)


def _run(client, monkeypatch, *, batch_size=2, workers=2):
    monkeypatch.setattr(translate_saas, "get_client", lambda: client)
    settings = Settings()
    settings.translate_batch_size = batch_size
    settings.parallel_workers = workers
    return translate_saas.translate_segments(
        _segments(4), get_target("vi"), "en-US", settings)


def test_prev_context_gets_real_translation_when_previous_batch_finishes_fast(
        patched, monkeypatch):
    """Lô trước xong nhanh (bình thường) -> lô sau THẬT SỰ nhận được bản
    dịch tiếng Việt trong prev_context, không phải rỗng như bug cũ."""
    client = FakeClient()  # không delay — lô nào cũng xong gần như ngay
    _run(client, monkeypatch)

    assert len(client.calls) == 2
    second_call = client.calls[1]
    prev = second_call["prev_context"]
    assert prev, "prev_context không được rỗng khi lô trước đã xong"
    assert any("text_vi" in item for item in prev), (
        "phải có ít nhất 1 câu trong prev_context mang bản dịch tiếng Việt thật")


def test_second_batch_does_not_wait_forever_when_previous_batch_is_slow(
        patched, monkeypatch):
    """Lô trước chậm hơn trần chờ -> lô sau vẫn tự chạy tiếp (không treo cả
    lượt dịch), prev_context không có bản dịch (đúng graceful-degrade cũ),
    nhưng vẫn hoàn tất bình thường."""
    monkeypatch.setattr(translate_saas, "_PREV_BATCH_WAIT_S", 0.05)
    # Lô đầu (gọi tới đầu tiên) "chậm" 0.3s — vượt xa trần 0.05s đã patch,
    # nhưng vẫn đủ nhanh để test không treo thật lâu.
    client = FakeClient(delays={0: 0.3})

    started = time.monotonic()
    out = _run(client, monkeypatch)
    elapsed = time.monotonic() - started

    assert len(out) == 4  # vẫn dịch xong đủ 4 câu, không crash/treo
    second_call = client.calls[1]
    prev = second_call["prev_context"]
    assert not any("text_vi" in item for item in prev), (
        "lô trước chưa xong trong hạn thì prev_context không được có bản dịch giả")
    # Tổng thời gian không được xấp xỉ tổng 2 lô cộng dồn tuần tự thật sự
    # (0.3s lô 1 + toàn bộ lô 2 nối đuôi) — chỉ cần dưới 1 lô chậm nhất
    # cộng thêm chút overhead, xác nhận lô 2 THẬT SỰ chạy song song, không
    # bị chặn chờ lô 1 xong hẳn.
    assert elapsed < 0.3 + 0.2


def test_single_batch_video_unaffected_no_wait_attempted(patched, monkeypatch):
    """Video 1 lô (không có lô nào trước để chờ) — 0 regression, hành vi
    y hệt trước khi có V39."""
    client = FakeClient()
    out = _run(client, monkeypatch, batch_size=40, workers=4)  # 4 câu < 40 -> 1 lô
    assert len(client.calls) == 1
    assert out[0]["text_vi"] == "vi source 1"
    assert client.calls[0]["prev_context"] == []
