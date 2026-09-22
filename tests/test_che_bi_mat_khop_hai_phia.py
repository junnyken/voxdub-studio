"""Hai bản che bí mật (Python và Node) phải che GIỐNG HỆT nhau.

`autodub/bang_chung.py::che_bi_mat` dùng cho bằng chứng phía máy người dùng;
`control_server/src/utils/che-bi-mat.js` dùng cho bộ thu bằng chứng cổng trợ
lý (`control_server/scripts/thu-bang-chung-assist.js`) chạy trong tiến trình
Node. Hai bản, một nhiệm vụ — tức là một khoản NỢ đúng kiểu đã ba lần làm
dự án này trôi lệch âm thầm: danh sách ngôn ngữ (V49), hằng số tốc độ đọc
(H6), mã thành công 201 của Phase H.

Tệp này trả lãi khoản nợ đó: đẩy CÙNG một bộ mẫu qua cả hai bản rồi so từng
ký tự. Sửa một bên mà quên bên kia là đỏ ngay tại đây, không phải đỏ ở một
tệp bằng chứng đã tải lên đâu đó với khoá API nằm giữa.

Bộ mẫu cố ý gồm cả những dạng đã gặp thật: `.env` đọc lên thành chuỗi, tham
số dòng lệnh tách đôi, tiêu đề `Authorization`, và chuỗi vô hại (không được
che nhầm thành rỗng).
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess

import pytest

from autodub.bang_chung import che_bi_mat

GOC = pathlib.Path(__file__).resolve().parent.parent
JS = GOC / "control_server" / "src" / "utils" / "che-bi-mat.js"

MAU = [
    {"api_key": "sk-live-0123456789abcdef", "an_toan": "xin chào"},
    {"Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.abc"},
    {"long": {"device_token": "tok_abcdef123456", "so": 12, "co": True}},
    "VOXDUB_API_TOKEN=abc123xyz",
    "chạy xong rồi, api-key: 'sk-zzz' và còn nữa",
    ["--hf-token", "hf_abcdef", "--giu"],
    {"ghi_chu": "không có gì bí mật ở đây", "rong": "", "khong": None},
    {"secret": ""},
    {"ds": ["password=abc", {"apikey": "k1"}, 7]},
    "Không có dấu bằng nào nên không che gì cả",
]


@pytest.fixture(scope="module")
def che_ben_node():
    if shutil.which("node") is None:
        pytest.skip("không có node trên máy này")
    if not JS.is_file():
        pytest.skip("không có control_server/ (nhánh deploy chỉ chứa autodub)")

    lai = GOC / "control_server" / "src" / "utils" / "che-bi-mat.js"
    ma = (
        "const {cheBiMat} = require(process.argv[1]);"
        "let vao='';process.stdin.on('data',c=>vao+=c).on('end',()=>{"
        "process.stdout.write(JSON.stringify(JSON.parse(vao).map(x=>cheBiMat(x))))});"
    )

    def chay(mau: list):
        ra = subprocess.run(
            ["node", "-e", ma, str(lai)],
            input=json.dumps(mau), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=60)
        assert ra.returncode == 0, f"bản Node chạy hỏng: {ra.stderr[:400]}"
        return json.loads(ra.stdout)

    return chay


def test_hai_ban_che_giong_het_nhau(che_ben_node):
    ben_node = che_ben_node(MAU)
    ben_python = [json.loads(json.dumps(che_bi_mat(m))) for m in MAU]
    for mau, py, js in zip(MAU, ben_python, ben_node):
        assert py == js, (
            "Hai bản che khác nhau cho mẫu:\n"
            f"  vào   : {json.dumps(mau, ensure_ascii=False)}\n"
            f"  python: {json.dumps(py, ensure_ascii=False)}\n"
            f"  node  : {json.dumps(js, ensure_ascii=False)}")


def test_ca_hai_ban_deu_THAT_SU_che(che_ben_node):
    """Phép canh ngược: hai bản giống nhau nhưng cùng KHÔNG che thì vô dụng."""
    ben_node = json.dumps(che_ben_node(MAU), ensure_ascii=False)
    ben_python = json.dumps([che_bi_mat(m) for m in MAU], ensure_ascii=False)
    for lo in ("sk-live-0123456789abcdef", "tok_abcdef123456", "abc123xyz",
               "hf_abcdef", "sk-zzz"):
        assert lo not in ben_node, f"bản Node để lọt «{lo}»"
        assert lo not in ben_python, f"bản Python để lọt «{lo}»"
    for giu in ("xin chào", "không có gì bí mật ở đây"):
        assert giu in ben_node and giu in ben_python, (
            f"«{giu}» bị che nhầm — che quá tay thì bằng chứng thành vô nghĩa")
