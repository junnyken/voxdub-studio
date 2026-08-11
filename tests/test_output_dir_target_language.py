"""Mini-spec V11 (docs/PLAN.md) — bug thật tìm ra trong lúc live-verify:
``DubPipeline.default_output_dir(target)`` bỏ qua tham số ``target``, luôn
trả về thư mục "VN" bất kể ngôn ngữ đích — video lồng tiếng Anh (target=en)
bị đặt lẫn trong ``output/VN/..._en`` thay vì một thư mục riêng cho tiếng
Anh. Không crash, chỉ sai tổ chức thư mục — phát hiện qua IDE diagnostic
"unused parameter" khi rà lại code xung quanh, không phải đoán.
"""
from __future__ import annotations

from autodub.config import Settings
from autodub.languages import get_target
from autodub.pipeline import DubPipeline


def test_vietnamese_target_output_dir_unchanged():
    """target=vi (0 regression) — y hệt trước V11: <output_dir>/VN."""
    settings = Settings(output_dir="/tmp/x-out")
    pipeline = DubPipeline(settings)
    assert pipeline.default_output_dir(get_target("vi")) == "/tmp/x-out/VN"


def test_vietnamese_target_respects_custom_override():
    settings = Settings(output_dir="/tmp/x-out",
                        vietnamese_output_dir="/custom/vi")
    pipeline = DubPipeline(settings)
    assert pipeline.default_output_dir(get_target("vi")) == "/custom/vi"


def test_english_target_gets_its_own_folder_not_vn():
    settings = Settings(output_dir="/tmp/x-out")
    pipeline = DubPipeline(settings)
    out = pipeline.default_output_dir(get_target("en"))
    assert out == "/tmp/x-out/EN"
    assert "VN" not in out


def test_english_target_ignores_vietnamese_specific_override():
    """VIETNAMESE_OUTPUT_DIR di dời output TIẾNG VIỆT, không phải mọi
    ngôn ngữ — target=en không được đi theo override đó."""
    settings = Settings(output_dir="/tmp/x-out",
                        vietnamese_output_dir="/custom/vi")
    pipeline = DubPipeline(settings)
    assert pipeline.default_output_dir(get_target("en")) == "/tmp/x-out/EN"
