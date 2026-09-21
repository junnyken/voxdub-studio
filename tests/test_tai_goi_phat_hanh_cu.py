"""I0-FDE — bước tải gói phát hành CŨ (`scripts/tai_goi_phat_hanh_cu.py`).

Bước này là vật liệu của cổng nâng cấp liên phiên bản: hỏng ở đây mà đi tiếp
thì cổng I0-E dựng "bản cũ" từ một tệp sai hoặc cụt, rồi mọi kết luận sau đó
đều vô nghĩa — nhưng vẫn xanh. Nên khoá bốn ca:

* chọn nhầm asset (hoặc im lặng chọn bừa khi có nhiều cái khớp);
* tải thiếu byte mà tệp vẫn mang đúng tên;
* chuyển hướng sang kho đối tượng của GitHub mà còn mang theo token;
* không chuyển được đường dẫn sang bước sau.

Chạy hoàn toàn ngoại tuyến: mọi lượt gọi mạng bị thay bằng bản giả.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import tai_goi_phat_hanh_cu as tai  # noqa: E402


NOI_DUNG = b"PK\x03\x04 gi\xe1\xbA\xa3 l\xe1\xba\xadp" + b"x" * 5000


def _phat_hanh(ten="VoxDub-Studio-v3.17.19-win64.zip", co=len(NOI_DUNG),
               them=()) -> dict:
    assets = [{"name": ten, "size": co, "id": 565214095,
               "url": "https://api.github.com/repos/x/y/releases/assets/1"}]
    assets += list(them)
    return {"tag_name": "v3.17.19", "published_at": "2026-09-15T07:59:52Z",
            "html_url": "https://github.com/x/y/releases/tag/v3.17.19",
            "assets": assets}


class _Tra(io.BytesIO):
    """Đối tượng trả về của `_mo` — vừa đọc được vừa dùng được với `with`."""

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()
        return False


def _thay_mang(monkeypatch, phat_hanh: dict, noi_dung: bytes = NOI_DUNG,
               ghi_lai: list | None = None):
    def _mo_gia(url, token, accept):
        if ghi_lai is not None:
            ghi_lai.append((url, token, accept))
        if "/releases/tags/" in url:
            return _Tra(json.dumps(phat_hanh).encode("utf-8"))
        return _Tra(noi_dung)
    monkeypatch.setattr(tai, "_mo", _mo_gia)


# ----------------------------------------------------------- chọn asset ---

def test_chon_dung_goi_windows():
    ph = _phat_hanh(them=[{"name": "ghi-chu.txt", "size": 3, "url": "u"}])
    assert tai.chon_asset(ph)["name"].endswith("-win64.zip")


def test_khong_co_asset_thi_noi_ro_dang_co_gi():
    ph = {"tag_name": "v9.9.9", "assets": [{"name": "doc.pdf"}]}
    with pytest.raises(tai.KhongTaiDuoc, match="doc.pdf"):
        tai.chon_asset(ph)


def test_nhieu_asset_khop_thi_KHONG_doan_bua():
    ph = _phat_hanh(them=[{"name": "VoxDub-Studio-v3.17.19-beta-win64.zip",
                           "size": 1, "url": "u"}])
    with pytest.raises(tai.KhongTaiDuoc, match="không đoán bừa"):
        tai.chon_asset(ph)


# -------------------------------------------------------------- tải về ----

def test_tai_ve_ghi_du_bang_chung_nguon_goc(tmp_path, monkeypatch):
    _thay_mang(monkeypatch, _phat_hanh())
    ho_so = tai.tai_ve("junnyken/voxdub-studio", "v3.17.19", str(tmp_path), "t")

    tep = tmp_path / "VoxDub-Studio-v3.17.19-win64.zip"
    assert tep.read_bytes() == NOI_DUNG
    # Số đo phải ĐO TỪ TỆP, không chép của API.
    assert ho_so["sha256"] == hashlib.sha256(NOI_DUNG).hexdigest()
    assert ho_so["byte"] == len(NOI_DUNG)
    for truong in ("tag", "ten_asset", "url_release", "url_asset",
                   "phat_hanh_luc", "tai_luc", "duong_dan"):
        assert ho_so[truong], truong
    assert os.path.isabs(ho_so["duong_dan"])


def test_tai_thieu_byte_la_DO_va_khong_de_lai_tep_cut(tmp_path, monkeypatch):
    """Tệp cụt mang đúng tên là ca hỏng im lặng — bước sau sẽ chẩn nhầm."""
    _thay_mang(monkeypatch, _phat_hanh(co=len(NOI_DUNG) + 999))
    with pytest.raises(tai.KhongTaiDuoc, match="cụt"):
        tai.tai_ve("x/y", "v3.17.19", str(tmp_path), "t")
    assert not (tmp_path / "VoxDub-Studio-v3.17.19-win64.zip").is_file()


def test_token_duoc_gui_khi_goi_api(tmp_path, monkeypatch):
    lan_goi = []
    _thay_mang(monkeypatch, _phat_hanh(), ghi_lai=lan_goi)
    tai.tai_ve("x/y", "v3.17.19", str(tmp_path), "token-bi-mat")
    assert lan_goi[0][1] == "token-bi-mat"
    assert lan_goi[1][2] == "application/octet-stream", (
        "thiếu Accept này thì GitHub trả JSON mô tả asset chứ không trả tệp — "
        "và 'gói' tải về sẽ là vài trăm byte JSON")


def test_chuyen_huong_KHONG_mang_token_sang_kho_doi_tuong():
    """Mang Authorization sang S3 là lỗi 400 ở một khâu trông chẳng liên quan."""
    bo = tai._BoChuyenHuongKhongMangToken()
    req = bo.redirect_request(
        None, None, 302, "Found", {},
        "https://objects.githubusercontent.com/abc?token=chu-ky-san")
    assert "Authorization" not in req.headers
    assert not any(k.lower() == "authorization" for k in req.headers)


# ------------------------------------------------- chuyển sang bước sau ---

def test_ghi_duong_dan_sang_buoc_sau(tmp_path, monkeypatch):
    ra = tmp_path / "gh-output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(ra))
    tai._ghi_output_ci({"duong_dan": r"D:\a\ban-cu\goi.zip", "tag": "v3.17.19"})
    chu = ra.read_text(encoding="utf-8")
    assert "duong_dan=D:\\a\\ban-cu\\goi.zip" in chu
    assert "tag=v3.17.19" in chu


def test_khong_co_GITHUB_OUTPUT_thi_khong_no(monkeypatch):
    """Chạy tay dưới máy không có biến đó — không được chết vì chuyện phụ."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    tai._ghi_output_ci({"duong_dan": "x", "tag": "v1.0"})


def test_main_tra_ma_1_khi_khong_tai_duoc(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tai, "tai_ve", lambda *a, **k: (_ for _ in ()).throw(
        tai.KhongTaiDuoc("HTTP 404 Not Found")))
    ma = tai.main(["--tag", "v0.0.1", "--repo", "x/y", "--ra", str(tmp_path)])
    assert ma == 1
    assert "404" in capsys.readouterr().err
