"""Mini-spec V42 (docs/PLAN.md, Phase G) — audit kiến trúc batch song song
tìm ra bug thật (không phải gap chính của mini-spec, phát sinh lúc audit):
tên thư mục 1 lượt chạy MỚI chỉ phân giải tới GIÂY
(``datetime.now().strftime("%Y%m%d%H%M%S")``) — 2 lượt chạy MỚI khởi động
cùng 1 giây (2 tiến trình CLI độc lập, hoặc concurrency trong tương lai) sẽ
trùng tên, ``ensure_dir(exist_ok=True)`` lặng lẽ tái dùng thư mục cũ như thể
đang resume, khiến 2 video khác nhau đè file lên nhau.
"""
from __future__ import annotations

import os

from autodub.pipeline import DubPipeline


def test_no_collision_returns_base_name_unchanged(tmp_path):
    """0 regression: thư mục chưa tồn tại -> tên y hệt trước (không thêm hậu tố)."""
    name = DubPipeline._unique_new_folder_name(str(tmp_path), "20260816120000_vi")
    assert name == "20260816120000_vi"


def test_collision_appends_disambiguating_suffix(tmp_path):
    """Bug thật V42: 2 lượt chạy MỚI cùng giây -> KHÔNG được trả cùng 1 tên."""
    os.makedirs(tmp_path / "20260816120000_vi")

    name = DubPipeline._unique_new_folder_name(str(tmp_path), "20260816120000_vi")

    assert name != "20260816120000_vi"
    assert name.startswith("20260816120000_vi-")


def test_multiple_collisions_each_get_distinct_names(tmp_path):
    os.makedirs(tmp_path / "20260816120000_vi")
    os.makedirs(tmp_path / "20260816120000_vi-2")

    name = DubPipeline._unique_new_folder_name(str(tmp_path), "20260816120000_vi")

    assert name == "20260816120000_vi-3"
    assert not os.path.exists(tmp_path / name)
