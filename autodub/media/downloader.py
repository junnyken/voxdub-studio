"""Video download via yt-dlp, with Douyin routed through Playwright."""
import os
import re
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import yt_dlp

from autodub.utils import setup_logging, ensure_dir, save_json_atomic

logger = setup_logging("autodub.downloader")


def _save_meta(output_dir: str, title: str, uploader: str = "") -> None:
    """Lưu title/uploader vào ``data/video_meta.json`` cạnh video tải về.

    Title là ngữ cảnh miễn phí, giá trị cao cho bước phân tích/dịch/metadata —
    trước đây bị vứt đi ngay sau khi tải. Best-effort: lỗi ghi không được
    làm hỏng lượt tải.
    """
    title = (title or "").strip()
    if not title:
        return
    try:
        from autodub.workdir import data_path
        save_json_atomic({"title": title, "uploader": (uploader or "").strip()},
                         data_path(output_dir, "video_meta.json",
                                   create_dir=True))
    except OSError as e:
        logger.warning(f"Không lưu được video_meta.json: {e}")


def normalize_url(url: str) -> str:
    """Rewrite non-canonical Douyin/TikTok URLs to a form yt-dlp can extract.

    Douyin's web app uses modal-style routes (e.g. /jingxuan?modal_id=<id>,
    /discover?modal_id=<id>) where the actual video id lives in the query
    string. yt-dlp's douyin extractor expects /video/<id>, so we rewrite.
    """
    if not url:
        return url
    # Tách địa chỉ khỏi đoạn chia sẻ trước MỌI thứ khác (mini-spec C30): nút
    # Chia sẻ của Douyin/TikTok sinh ra cả một đoạn chữ có liên kết nằm giữa,
    # và mọi phép kiểm bên dưới (`urlparse`, `netloc`) đều trượt nếu chuỗi
    # còn dính chữ.
    from autodub.utils import tach_lien_ket

    url = tach_lien_ket(url)
    # Thêm lược đồ khi người dùng gõ tay `www.youtube.com/…`. Làm ở đây để
    # mọi khâu sau (chọn extractor, cắt tham số playlist, `urlparse`) nhìn
    # thấy một địa chỉ đầy đủ — `urlparse` không có lược đồ thì đẩy cả tên
    # miền vào `path` và mọi phép kiểm theo `netloc` đều trượt.
    from autodub.utils import looks_like_bare_url
    if looks_like_bare_url(url):
        url = "https://" + url
    parsed = urlparse(url)
    host = parsed.netloc.lower()

    if "douyin.com" in host:
        qs = parse_qs(parsed.query)
        modal_id = qs.get("modal_id", [None])[0]
        if modal_id and modal_id.isdigit():
            return f"https://www.douyin.com/video/{modal_id}"

    # YouTube: bỏ các tham số NGỮ CẢNH DANH SÁCH PHÁT — mini-spec V73.
    #
    # `noplaylist` chưa đủ. Đo bằng yt-dlp thật (2026.03.17):
    #   youtu.be/<id>?list=…            + noplaylist → OK, ra đúng video
    #   youtube.com/shorts/<id>?list=…  + noplaylist → HỎNG, "This playlist
    #                                     type is unviewable"
    # Vì thấy `list=` là yt-dlp đẩy sang extractor `youtube:tab` (playlist)
    # ngay từ khâu chọn extractor, trước cả lúc `noplaylist` có tiếng nói.
    # Cắt tham số đi thì mọi dạng liên kết đi chung một đường.
    #
    # Không đụng tới `/playlist` — `ensure_single_video_url` chặn theo ĐƯỜNG
    # DẪN nên vẫn bắt được, và biến nó thành liên kết video giả là sai.
    if "youtube.com" in host or "youtu.be" in host:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        bo = [k for k in ("list", "start_radio", "index") if k in qs]
        if bo and not parsed.path.rstrip("/").lower().endswith("/playlist"):
            for k in bo:
                qs.pop(k)
            return urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    return url


class PlaylistUrlError(ValueError):
    """Liên kết trỏ tới cả một danh sách phát chứ không phải một video."""


def ensure_single_video_url(url: str) -> None:
    """Chặn liên kết DANH SÁCH PHÁT thuần — mini-spec V73.

    Cả ứng dụng chỉ xử lý MỘT video mỗi lượt (`_resolve_filepath` trả về đúng
    một file). Liên kết dạng `watch?v=…&list=…` đã được `noplaylist` cắt về
    đúng video đang mở, nhưng liên kết `playlist?list=…` thì không có video
    nào để cắt về — `noplaylist` không đụng tới nó. Không chặn ở đây thì
    yt-dlp lặng lẽ tải cả trăm video rồi mới hỏng ở bước tìm file, và người
    dùng chỉ thấy một lỗi vô nghĩa sau khi chờ rất lâu.
    """
    parsed = urlparse((url or "").strip())
    host = parsed.netloc.lower()
    if "youtube.com" not in host and "youtu.be" not in host:
        return
    duong = parsed.path.rstrip("/").lower()
    # Chặn HẸP: chỉ hai dạng chắc chắn không có video nào để tải. Mọi dạng
    # khác cho đi qua.
    #
    # Không được suy ra "có `list=` là danh sách phát" — id video của YouTube
    # nằm ở ĐƯỜNG DẪN chứ không phải lúc nào cũng ở tham số `v=`:
    # `youtu.be/<id>?list=…`, `youtube.com/shorts/<id>?list=…`,
    # `/embed/<id>`, `/live/<id>`. Chính nút Chia sẻ của YouTube sinh ra
    # `youtu.be/<id>?list=…` khi video đang nằm trong playlist — chặn theo
    # `list=` là chặn đúng loại liên kết người dùng hay dán nhất.
    khong_co_video = (
        duong.endswith("/playlist")
        or (duong.endswith("/watch") and not parse_qs(parsed.query).get("v", [""])[0].strip())
    )
    if khong_co_video:
        raise PlaylistUrlError(
            "Đây là liên kết DANH SÁCH PHÁT, không phải một video. Mở video "
            "bạn muốn rồi sao chép liên kết của riêng nó (dạng "
            "youtube.com/watch?v=… hoặc youtu.be/…).")


def cookie_opts_from(settings) -> dict:
    """Tham số cookie lấy từ Settings — mini-spec V67.

    File tường minh THẮNG trình duyệt: người vừa xuất `cookies.txt` ra là
    người đang cố sửa một lỗi cụ thể, còn "đọc từ Chrome" là đường tự đoán và
    hay hỏng lặng lẽ (trình duyệt đang mở khoá hồ sơ, sai profile...).
    """
    if settings is None:
        return {}
    f = str(getattr(settings, "cookies_file", "") or "").strip()
    if f:
        return {"cookies_file": f}
    b = str(getattr(settings, "cookies_from_browser", "") or "").strip()
    return {"cookies_from_browser": b} if b else {}


def download_video(url: str, output_dir: str, settings=None) -> str:
    if not url:
        raise ValueError("URL cannot be empty")

    # Tách liên kết khỏi đoạn chia sẻ NGAY ĐẦU (mini-spec C31).
    #
    # C30 tách bên trong `normalize_url`, nhưng phép hỏi `is_douyin_url` nằm
    # TRƯỚC đó — nên dán nguyên đoạn chia sẻ Douyin thì câu hỏi "đây có phải
    # Douyin không" nhận cả cụm chữ và trả lời KHÔNG. Đường tải Douyin riêng
    # (dựng ra vì bộ tải Douyin của yt-dlp hỏng sẵn ở thượng nguồn) bị bỏ qua,
    # rơi xuống yt-dlp rồi chết với "Fresh cookies are needed".
    from autodub.utils import tach_lien_ket

    url = tach_lien_ket(url)
    ensure_dir(output_dir)

    # Douyin's yt-dlp extractor is broken upstream (requires `a_bogus`
    # signature). Route Douyin URLs (including v.douyin.com short links)
    # through the Playwright-based fallback.
    from autodub.media.douyin import is_douyin_url, download_douyin
    if is_douyin_url(url):
        logger.info(f"Routing to Playwright Douyin extractor: {url}")
        try:
            info = download_douyin(url, output_dir)
        except Exception as e:  # noqa: BLE001 — còn một đường nữa để thử
            # Douyin đã đóng mọi cửa ẩn danh (mini-spec C33): trang chia sẻ
            # không còn địa chỉ video, API `iteminfo` trả rỗng, API `detail`
            # trả 403, và trang chia sẻ đẩy khách sang video gợi ý.
            #
            # Đường CÒN LẠI là cookie của chính người dùng — đúng thứ yt-dlp
            # đòi ("Fresh cookies … are needed"). Trước đây Douyin bị định
            # tuyến TRÁNH yt-dlp nên ô cookie trong Cài đặt không có tác dụng
            # gì với Douyin. Nay thử nốt đường đó thay vì bỏ cuộc.
            if not cookie_opts_from(settings):
                raise
            logger.warning(
                f"Đường trình duyệt hỏng ({str(e)[:100]}) — thử lại bằng "
                "cookie trình duyệt bạn đã chọn trong Cài đặt.")
        else:
            _save_meta(output_dir, info.get("title", ""), info.get("uploader", ""))
            return info["filepath"]

    canonical = normalize_url(url)
    if canonical != url:
        logger.info(f"Normalized URL: {url} -> {canonical}")
    ensure_single_video_url(canonical)

    _ck = cookie_opts_from(settings)

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": False,
        # CHỈ video đang mở, không phải cả danh sách phát. Liên kết sao chép
        # từ YouTube lúc đang nghe Mix/playlist luôn kèm `&list=…`; thiếu cờ
        # này yt-dlp tải sạch danh sách (Mix thường ~200 video) rồi hỏng ở
        # bước tìm file vì nó trả về info của playlist chứ không của video.
        "noplaylist": True,
        # Mạng chập chờn: tự thử lại thay vì fail cả video trong batch.
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }
    if _ck.get("cookies_file"):
        ydl_opts["cookiefile"] = _ck["cookies_file"]
    elif _ck.get("cookies_from_browser"):
        ydl_opts["cookiesfrombrowser"] = (_ck["cookies_from_browser"],)

    logger.info(f"Downloading video from: {canonical}")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(canonical, download=True)
        video_id = info.get("id", "video")
        ext = info.get("ext", "mp4")
        filepath = (_ydl_reported_path(info)
                    or os.path.join(output_dir, f"{video_id}.{ext}"))

        if not os.path.exists(filepath):
            for f in sorted(os.listdir(output_dir)):
                if f.startswith(video_id) and not _is_partial_name(f):
                    filepath = os.path.join(output_dir, f)
                    break

    if not os.path.exists(filepath):
        raise RuntimeError(f"Download failed: file not found at {filepath}")

    _save_meta(output_dir, info.get("title", ""), info.get("uploader", ""))
    logger.info(f"Downloaded: {filepath}")
    return filepath


def build_ydl_opts(
    output_dir: str,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
) -> dict:
    """yt-dlp options for the standalone `autodub download` command."""
    opts = {
        # Use extractor + id as filename so TikTok/Douyin/YouTube don't collide
        "outtmpl": os.path.join(output_dir, "%(extractor_key)s_%(id)s.%(ext)s"),
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "quiet": False,
        "no_warnings": False,
        "noprogress": False,
        # Xem chú thích ở `download_video` — chỉ video đang mở, bỏ qua `&list=`.
        "noplaylist": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
    }
    if cookies_from_browser:
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    if cookies_file:
        opts["cookiefile"] = cookies_file
    return opts


def _ydl_reported_path(info: dict) -> str | None:
    """The file path yt-dlp itself reports for the finished download."""
    try:
        path = (info.get("requested_downloads") or [{}])[0].get("filepath")
    except (AttributeError, IndexError, TypeError):
        return None
    return path if path and os.path.exists(path) else None


def _is_partial_name(name: str) -> bool:
    """True for yt-dlp intermediate files (.part, .ytdl, .f299.mp4...)."""
    lower = name.lower()
    if lower.endswith((".part", ".ytdl", ".temp")):
        return True
    # Pre-merge single streams look like <id>.f<format_id>.<ext>
    return bool(re.search(r"\.f\d+\.\w+$", lower))


def _resolve_filepath(info: dict, output_dir: str) -> str:
    """yt-dlp may rename during merge; locate the actual saved file."""
    # yt-dlp tells us the real path — trust it first (also covers ids with
    # characters that were sanitized out of the filename).
    reported = _ydl_reported_path(info)
    if reported:
        return reported

    extractor = info.get("extractor_key", info.get("extractor", "video"))
    video_id = info.get("id", "video")
    ext = info.get("ext", "mp4")

    expected = os.path.join(output_dir, f"{extractor}_{video_id}.{ext}")
    if os.path.exists(expected):
        return expected

    prefix = f"{extractor}_{video_id}"
    for f in sorted(os.listdir(output_dir)):
        # .part/.fNNN là file trung gian — trả về chúng là đưa file hỏng
        # vào pipeline.
        if f.startswith(prefix) and not _is_partial_name(f):
            return os.path.join(output_dir, f)

    raise RuntimeError(f"Downloaded but file not found (prefix={prefix})")


def download_one(
    url: str,
    output_dir: str,
    cookies_from_browser: str | None = None,
    cookies_file: str | None = None,
    settings=None,
) -> dict:
    """Download a single URL and return metadata + saved filepath.

    Douyin URLs (including short-link v.douyin.com/...) are routed to a
    Playwright-based extractor because yt-dlp's Douyin path is broken upstream.
    All other sites continue through yt-dlp.
    """
    # Cùng lý do như `download_video` — xem mini-spec C31.
    from autodub.utils import tach_lien_ket

    url = tach_lien_ket(url)

    from autodub.media.douyin import is_douyin_url, download_douyin
    if is_douyin_url(url):
        logger.info(f"Routing to Playwright Douyin extractor: {url}")
        return download_douyin(url, output_dir)

    canonical = normalize_url(url)
    if canonical != url:
        logger.info(f"Normalized: {url} -> {canonical}")
    ensure_single_video_url(canonical)

    # V67 — caller không truyền cookie tay thì lấy từ Settings. Truyền tay vẫn
    # thắng: chỗ gọi biết rõ hơn cấu hình chung.
    if not cookies_from_browser and not cookies_file:
        _ck = cookie_opts_from(settings)
        cookies_file = _ck.get("cookies_file") or None
        cookies_from_browser = _ck.get("cookies_from_browser") or None
    ydl_opts = build_ydl_opts(output_dir, cookies_from_browser, cookies_file)

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(canonical, download=True)

    filepath = _resolve_filepath(info, output_dir)

    return {
        "input_url": url,
        "canonical_url": canonical,
        "platform": info.get("extractor_key", info.get("extractor", "")),
        "video_id": info.get("id", ""),
        "title": info.get("title", ""),
        "uploader": info.get("uploader", ""),
        "duration": info.get("duration", 0),
        "filepath": filepath,
    }
