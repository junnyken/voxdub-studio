"""Bộ thu bằng chứng phải gửi ĐÚNG hình dạng dữ liệu mà máy khách gửi thật.

`control_server/scripts/thu-bang-chung-assist.js` gọi thẳng `POST /v1/ai/assist`
chứ không đi qua giao diện desktop — đó là đánh đổi đã nói rõ trong chính tệp
đó. Nhưng đánh đổi ấy chỉ chấp nhận được nếu **hình dạng `input` giống hệt**
thứ máy khách gửi. Nếu bộ thu tự bịa tên trường, bằng chứng thu về nói về một
cửa không tồn tại, và không ai nhận ra cho tới khi người dùng thật bấm nút.

Đây đúng lớp lỗi của `test_ma_thanh_cong_khop_may_chu.py` (máy chủ trả 201,
máy khách chỉ nhận 200 — hai bên đều xanh, đường nối thì chết): test này đọc
CẢ HAI phía và so tên trường.

Bốn cửa thật:
    explain_error   autodub_gui/workers.py
    character_name  autodub_gui/pages/editor_page.py
    tighten_line    autodub_gui/pages/editor_page.py
    scene_script    autodub/product_video.py
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

GOC = pathlib.Path(__file__).resolve().parent.parent
BO_THU = GOC / "control_server" / "scripts" / "thu-bang-chung-assist.js"

#: tác vụ → tệp chứa lời gọi thật ở máy khách
NOI_GOI = {
    "explain_error": "autodub_gui/workers.py",
    "character_name": "autodub_gui/pages/editor_page.py",
    "tighten_line": "autodub_gui/pages/editor_page.py",
    "scene_script": "autodub/product_video.py",
}


def _khoi_dict_sau(ma: str, vi_tri: int) -> str:
    """Trả về đoạn `{...}` đầu tiên kể từ ``vi_tri``, khớp ngoặc lồng nhau."""
    dau = ma.index("{", vi_tri)
    sau = 0
    for i in range(dau, len(ma)):
        if ma[i] == "{":
            sau += 1
        elif ma[i] == "}":
            sau -= 1
            if sau == 0:
                return ma[dau:i + 1]
    raise AssertionError("không tìm được ngoặc đóng")


def _khoa_may_khach(tac_vu: str) -> set[str]:
    duong = GOC / NOI_GOI[tac_vu]
    ma = duong.read_text(encoding="utf-8")
    moc = f'"{tac_vu}"'
    assert moc in ma, f"không thấy lời gọi {tac_vu} trong {duong}"
    khoi = _khoi_dict_sau(ma, ma.index(moc) + len(moc))
    # Tên trường trong dict Python của lời gọi: `"ten": ...`
    return set(__import__("re").findall(r'"(\w+)"\s*:', khoi))


@pytest.fixture(scope="module")
def mau_bo_thu() -> dict:
    if shutil.which("node") is None:
        pytest.skip("không có node trên máy này")
    if not BO_THU.is_file():
        pytest.skip("không có control_server/ (nhánh deploy chỉ chứa autodub)")
    ra = subprocess.run(
        ["node", "-e",
         "const {MAU}=require(process.argv[1]);process.stdout.write(JSON.stringify(MAU))",
         str(BO_THU)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60)
    assert ra.returncode == 0, f"đọc mẫu của bộ thu hỏng: {ra.stderr[:400]}"
    return json.loads(ra.stdout)


@pytest.mark.parametrize("tac_vu", sorted(NOI_GOI))
def test_ten_truong_khop_may_khach(mau_bo_thu, tac_vu):
    cua_may_khach = _khoa_may_khach(tac_vu)
    for i, mau in enumerate(mau_bo_thu[tac_vu]):
        assert set(mau) == cua_may_khach, (
            f"{tac_vu} mẫu #{i}: bộ thu gửi {sorted(mau)} còn máy khách gửi "
            f"{sorted(cua_may_khach)} ({NOI_GOI[tac_vu]}). Bằng chứng thu về "
            "sẽ nói về một cửa không tồn tại.")


def test_moi_tac_vu_co_it_nhat_hai_mau(mau_bo_thu):
    for tac_vu in NOI_GOI:
        assert len(mau_bo_thu[tac_vu]) >= 2, (
            f"{tac_vu} chỉ có {len(mau_bo_thu[tac_vu])} mẫu — ma trận §B2 đòi "
            "ít nhất hai lượt mỗi tác vụ")


def test_moi_mau_la_MOT_noi_dung_rieng(mau_bo_thu):
    """Trùng nội dung là rơi vào nhớ đệm — lượt đó không chạm tới mô hình.

    Đã suýt làm hỏng chính bộ thu: ca "thiếu nhà cung cấp" dùng lại câu của
    lượt trước thì máy chủ trả kết quả CŨ kèm HTTP 200, và phép kiểm 503 xanh
    giả theo chiều ngược lại.
    """
    for tac_vu, ds in mau_bo_thu.items():
        bam = [json.dumps(m, sort_keys=True, ensure_ascii=False) for m in ds]
        assert len(set(bam)) == len(bam), f"{tac_vu} có hai mẫu trùng nội dung"
