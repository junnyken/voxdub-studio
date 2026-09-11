"""Mã HTTP thành công của máy khách phải khớp máy chủ.

Lỗi thật chủ dự án gặp ngày 10/09/2026, ngay lượt lưu hồ sơ brand ĐẦU TIÊN
của pilot: hộp thoại báo **"Lỗi máy chủ (HTTP 201)"**. `201 Created` là mã
THÀNH CÔNG, và là mã đúng chuẩn cho việc tạo mới — nhưng `_request()` chỉ
chấp nhận đúng `200`.

Ba cửa dùng `201`, và cả ba đều là Phase H: hồ sơ brand (H1), Flow Blueprint
(H2), BrandScript (H3). Nghĩa là lỗi này **chặn toàn bộ pilot**. Nặng nhất là
H2/H3: hai cửa đó đã **trừ Vox** rồi mới trả `201`, tức là trừ tiền xong báo
hỏng — và người dùng thấy lỗi sẽ bấm lại, mất tiền lần nữa.

**Vì sao không test nào bắt được**: test máy chủ kiểm `reply.code(201)`; test
máy khách (`test_saas_client_brand_profile.py`) giả lập nguyên hàm `_request`
và trả thẳng dict. Hai bên đều xanh, còn ĐƯỜNG NỐI giữa chúng thì chưa ai đi
qua. Tệp này đi vào đúng chỗ nối đó, và quét mã route để nó không hở lại.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

from autodub.saas_client import SaasClient, SaasError, _la_thanh_cong

GOC = pathlib.Path(__file__).resolve().parent.parent


class _TraLoiGia:
    def __init__(self, status_code, than=None, raw=None):
        self.status_code = status_code
        self._than = than
        self.content = raw if raw is not None else (
            json.dumps(than).encode() if than is not None else b"")
        self.headers = {}

    def json(self):
        if self._than is None:
            raise ValueError("không phải JSON")
        return self._than


class _PhienGia:
    def __init__(self, tra_loi):
        self.tra_loi = tra_loi
        self.da_goi = []

    def request(self, method, url, **kw):
        self.da_goi.append((method, url))
        return self.tra_loi

    def get(self, url, **kw):
        return self.request("GET", url, **kw)


def _client(tra_loi) -> SaasClient:
    c = SaasClient(base_url="http://test.local")
    c._http = lambda: _PhienGia(tra_loi)
    return c


# ----------------------------------------------------- luật 2xx -----------

@pytest.mark.parametrize("ma", [200, 201, 202, 203, 204, 299])
def test_moi_ma_2xx_deu_la_thanh_cong(ma):
    assert _la_thanh_cong(ma), f"{ma} là mã thành công mà bị coi là lỗi"


@pytest.mark.parametrize("ma", [199, 300, 301, 400, 401, 402, 404, 429, 500, 503])
def test_ngoai_2xx_khong_duoc_coi_la_thanh_cong(ma):
    assert not _la_thanh_cong(ma)


# --------------------------------------------- đi thẳng vào _request ------

def test_201_tra_ve_du_lieu_chu_KHONG_nem_loi():
    """Đúng lỗi đã xảy ra. Trước bản vá, dòng này ném SaasError("HTTP 201")."""
    c = _client(_TraLoiGia(201, {"id": "abc", "tenBrand": "Mắt Bão Invoice"}))
    ra = c._request("POST", "/v1/brand-profiles/", json_body={}, auth=False)
    assert ra["id"] == "abc"
    assert ra["tenBrand"] == "Mắt Bão Invoice"


def test_200_van_chay_nhu_cu():
    c = _client(_TraLoiGia(200, {"ok": True}))
    assert c._request("GET", "/v1/x", auth=False) == {"ok": True}


def test_204_than_rong_la_thanh_cong_khong_phai_du_lieu_hong():
    c = _client(_TraLoiGia(204, None, raw=b""))
    assert c._request("DELETE", "/v1/x", auth=False) == {}


def test_200_ma_than_khong_doc_duoc_thi_VAN_bao_loi():
    """Nới mã thành công không được nới luôn phần đọc dữ liệu."""
    c = _client(_TraLoiGia(200, None, raw=b"<html>khong phai json</html>"))
    with pytest.raises(SaasError, match="không đọc được"):
        c._request("GET", "/v1/x", auth=False)


def test_400_van_nem_loi_nhu_cu():
    c = _client(_TraLoiGia(400, {"code": "X", "message": "sai dữ liệu"}))
    with pytest.raises(SaasError, match="sai dữ liệu"):
        c._request("POST", "/v1/x", json_body={}, auth=False)


# ------------------------------------------------- chốt quét mã route -----

def _ma_thanh_cong_may_chu() -> dict[str, set[int]]:
    """Mọi `reply.code(2xx)` trong routes — máy chủ đang hứa những mã nào."""
    ra: dict[str, set[int]] = {}
    for tep in sorted((GOC / "control_server" / "src" / "routes").glob("*.js")):
        ma = tep.read_text(encoding="utf-8")
        so = {int(m) for m in re.findall(r"reply\s*\.\s*code\(\s*(\d{3})\s*\)", ma)
              if 200 <= int(m) < 300}
        if so:
            ra[tep.name] = so
    return ra


def test_may_chu_co_dung_ma_2xx_ngoai_200():
    """Chốt tiền đề của tệp này.

    Nếu một ngày mọi route đều về `200`, phép quét dưới thành vô nghĩa mà vẫn
    xanh — một test luôn đạt vì không kiểm gì cả còn tệ hơn không có test.
    """
    tat_ca = {m for so in _ma_thanh_cong_may_chu().values() for m in so}
    assert tat_ca - {200}, (
        "không route nào dùng mã 2xx ngoài 200 — kiểm lại phép quét, đừng để "
        "test này xanh suông")


def test_may_khach_chap_nhan_MOI_ma_thanh_cong_may_chu_tra_ve():
    lech = []
    for tep, so in _ma_thanh_cong_may_chu().items():
        for m in sorted(so):
            if not _la_thanh_cong(m):
                lech.append(f"{tep} trả {m} mà máy khách coi là lỗi")
    assert not lech, lech


class _TraLoiTai(_TraLoiGia):
    """Response tải tệp: có `iter_content`, thân là nhị phân chứ không JSON."""

    def iter_content(self, chunk_size=0):
        yield self.content


def test_tai_tep_voi_ma_2xx_khac_200_KHONG_duoc_bo_qua(tmp_path):
    """Bẫy do CHÍNH bản vá 2xx tạo ra, tìm thấy khi tự soi lại.

    `download_job_result` từng viết `if != 200: self._parse_response(resp);
    return` và dựa vào việc `_parse_response` **luôn ném**. Sau khi nới 2xx,
    `_parse_response` trả về dict cho mọi mã 2xx ⇒ nhánh đó rơi xuống
    `return` và hàm **lặng lẽ không tải gì**; người gọi tưởng có tệp.

    Đo bằng `206 Partial Content` — mã 2xx hợp lệ mà một proxy hay CDN chắn
    giữa đường có thể trả về. Bản cũ: ném "dữ liệu không đọc được" (sai
    nguyên nhân) và không có tệp. Bản mới: tải bình thường.
    """
    dich = tmp_path / "vocals.wav"
    c = _client(_TraLoiTai(206, None, raw=b"RIFF....WAVE"))
    c._load_token = lambda: "tok"
    c.download_job_result("job1", "vocals", str(dich))
    assert dich.read_bytes() == b"RIFF....WAVE"


def test_tai_tep_that_bai_thi_VAN_nem_loi_dung_nguyen_nhan(tmp_path):
    dich = tmp_path / "vocals.wav"
    c = _client(_TraLoiTai(404, {"code": "GONE", "message": "Tệp không còn"}))
    c._load_token = lambda: "tok"
    with pytest.raises(SaasError, match="Tệp không còn"):
        c.download_job_result("job1", "vocals", str(dich))
    assert not dich.exists(), "không được tạo tệp rỗng khi lượt tải hỏng"


def test_ba_cua_Phase_H_deu_tra_201():
    """Hồi quy có tên cụ thể: ba cửa này là thứ pilot đi qua.

    Đổi chúng về 200 để "cho an toàn" là chữa triệu chứng — `201` mới đúng
    chuẩn cho việc tạo mới, và chỗ hỏng nằm ở máy khách.
    """
    may_chu = _ma_thanh_cong_may_chu()
    for tep in ("brand-profiles.js", "flow-blueprints.js", "brand-scripts.js"):
        assert 201 in may_chu.get(tep, set()), f"{tep} không còn trả 201"
        assert _la_thanh_cong(201)
