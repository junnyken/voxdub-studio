/**
 * Trang thử API lồng tiếng ngay trên trình duyệt (mini-spec V49).
 *
 * Vì sao cần: hạ tầng lồng tiếng chạy hoàn toàn trên máy chủ (V34b) đã sống
 * thật, nhưng cách DUY NHẤT để chạm vào nó là gõ `curl` — nên trên thực tế
 * chưa ai dùng. Trang này biến đúng những endpoint đã có thành thứ bấm được:
 * chọn file, chọn ngôn ngữ, xem tiến trình, tải kết quả.
 *
 * Phạm vi CỐ Ý hẹp: người dùng tự dán API key của mình. KHÔNG có chế độ
 * "dùng thử không cần key" — cái đó nghĩa là cho chạy ASR/TTS/ghép video
 * miễn phí cho người lạ, tức là quyết định chi phí + chống lạm dụng của chủ
 * dự án, không phải hệ quả kỹ thuật của mini-spec này (xem Remaining Limits
 * trong docs/PLAN.md V49).
 *
 * Key chỉ nằm trong bộ nhớ của tab (KHÔNG lưu localStorage): trang này chạy
 * chung origin với trang bán hàng, và một API key rò rỉ là tiền thật của
 * người khác.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { api } from '../api/client'
import { Badge, ErrorBox, Spinner } from '../components/ui'

const POLL_MS = 3000

/** Ước lượng phút để khai `estimatedMinutes` — chỉ để giữ chỗ quota, tiền
 * thật vẫn tính lại theo thời lượng worker đo được. Không có ffprobe trong
 * trình duyệt nên đọc metadata từ thẻ <video>; đọc không được thì bỏ trống
 * và để máy chủ dùng mặc định. */
function readDurationMinutes(file) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(file)
    const video = document.createElement('video')
    video.preload = 'metadata'
    video.onloadedmetadata = () => {
      URL.revokeObjectURL(url)
      const s = Number(video.duration)
      resolve(Number.isFinite(s) && s > 0 ? Math.max(1, Math.ceil(s / 60)) : 0)
    }
    video.onerror = () => { URL.revokeObjectURL(url); resolve(0) }
    video.src = url
  })
}

function formatBytes(n) {
  if (!n) return '0 B'
  const mb = n / 1024 / 1024
  return mb >= 1 ? `${mb.toFixed(1)} MB` : `${Math.round(n / 1024)} KB`
}

export default function TryDub() {
  const [cfg, setCfg] = useState(null)
  const [cfgError, setCfgError] = useState(null)

  const [apiKey, setApiKey] = useState('')
  const [me, setMe] = useState(null)
  const [keyError, setKeyError] = useState(null)
  const [checking, setChecking] = useState(false)

  const [file, setFile] = useState(null)
  const [sourceLang, setSourceLang] = useState('en-US')
  const [targetLang, setTargetLang] = useState('vi')
  const [bgMode, setBgMode] = useState('none')

  const [uploadPct, setUploadPct] = useState(0)
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [resultUrl, setResultUrl] = useState('')

  const pollRef = useRef(null)

  useEffect(() => {
    api.appConfig().then(setCfg).catch(setCfgError)
    return () => clearInterval(pollRef.current)
  }, [])

  const dub = cfg && cfg.cloudDub

  const checkKey = useCallback(async () => {
    setChecking(true)
    setKeyError(null)
    setMe(null)
    try {
      const resp = await fetch('/api/v1/me', {
        headers: { authorization: `Bearer ${apiKey.trim()}` },
      })
      const data = await resp.json()
      if (!resp.ok) throw new Error(data.message || 'API key không dùng được.')
      setMe(data)
    } catch (err) {
      setKeyError(err.message || String(err))
    } finally {
      setChecking(false)
    }
  }, [apiKey])

  const pollJob = useCallback((jobId) => {
    clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const resp = await fetch(`/api/v1/dub/${jobId}`, {
          headers: { authorization: `Bearer ${apiKey.trim()}` },
        })
        const data = await resp.json()
        setJob(data)
        if (data.status === 'done' || data.status === 'failed') {
          clearInterval(pollRef.current)
          setBusy(false)
        }
      } catch {
        // Mất mạng tạm thời không được phép giết vòng theo dõi — job vẫn
        // đang chạy trên máy chủ, lượt poll sau sẽ bắt lại được.
      }
    }, POLL_MS)
  }, [apiKey])

  async function submit(e) {
    e.preventDefault()
    if (!file || !apiKey.trim()) return
    setError(null)
    setResultUrl('')
    setJob(null)
    setBusy(true)
    setUploadPct(0)

    const minutes = await readDurationMinutes(file)
    const params = new URLSearchParams({ sourceLang, targetLang, bgMode })
    if (minutes) params.set('estimatedMinutes', String(minutes))

    const form = new FormData()
    form.append('file', file)

    // XHR chứ không fetch: chỉ XHR báo được tiến trình TẢI LÊN, mà file vài
    // trăm MB thì thanh tiến trình là khác biệt giữa "đang chạy" và "hình như
    // treo rồi".
    const xhr = new XMLHttpRequest()
    xhr.open('POST', `/api/v1/dub?${params.toString()}`)
    xhr.setRequestHeader('Authorization', `Bearer ${apiKey.trim()}`)
    xhr.upload.onprogress = (ev) => {
      if (ev.lengthComputable) setUploadPct(Math.round((ev.loaded / ev.total) * 100))
    }
    xhr.onload = () => {
      let data = {}
      try { data = JSON.parse(xhr.responseText) } catch { /* để rơi xuống nhánh lỗi */ }
      if (xhr.status === 200 && data.jobId) {
        setJob({ jobId: data.jobId, status: data.status })
        pollJob(data.jobId)
      } else {
        setBusy(false)
        setError(data.message || `Máy chủ trả lỗi ${xhr.status}.`)
      }
    }
    xhr.onerror = () => {
      setBusy(false)
      setError('Mất kết nối khi đang tải file lên.')
    }
    xhr.send(form)
  }

  async function fetchResult() {
    setError(null)
    try {
      const resp = await fetch(`/api/v1/dub/${job.jobId}/result`, {
        headers: { authorization: `Bearer ${apiKey.trim()}` },
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.message || `Không tải được kết quả (${resp.status}).`)
      }
      // Kết quả bị XOÁ ngay sau lượt tải đầu tiên (chính sách dữ liệu V9) —
      // giữ blob lại để người dùng xem/lưu nhiều lần mà không gọi lại
      // server (gọi lại sẽ ra 410, trông như hỏng).
      const blob = await resp.blob()
      setResultUrl(URL.createObjectURL(blob))
    } catch (err) {
      setError(err.message || String(err))
    }
  }

  if (cfgError) return <ErrorBox error={cfgError} />

  const tooBig = file && dub && file.size > dub.maxUploadMb * 1024 * 1024
  const price = bgMode === 'demucs' ? dub && dub.voxPerMinuteDemucs : dub && dub.voxPerMinute

  return (
    <div className="mx-auto max-w-3xl px-4 py-10">
      <h1 className="text-3xl font-bold">Thử API lồng tiếng</h1>
      <p className="mt-2 text-slate-600">
        Gửi một video lên máy chủ VoxDub và nhận về bản đã lồng tiếng — không cần cài
        gì, không cần gõ lệnh. Trang này gọi đúng API công khai
        {' '}<code className="rounded bg-slate-100 px-1">/api/v1/dub</code>.
      </p>

      {dub && !dub.enabled && (
        <p className="mt-4 rounded border border-amber-300 bg-amber-50 p-3 text-amber-900">
          Tính năng lồng tiếng trên máy chủ đang tắt.
        </p>
      )}

      <section className="mt-8 rounded-lg border border-slate-200 p-5">
        <h2 className="font-semibold">1. API key của bạn</h2>
        <p className="mt-1 text-sm text-slate-600">
          Dạng <code>vx_live_…</code>, do quản trị cấp. Key chỉ nằm trong tab này,
          không được lưu lại sau khi bạn đóng trang.
        </p>
        <div className="mt-3 flex gap-2">
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder="vx_live_..."
            className="flex-1 rounded border border-slate-300 px-3 py-2 font-mono text-sm"
          />
          <button
            type="button"
            onClick={checkKey}
            disabled={!apiKey.trim() || checking}
            className="rounded bg-slate-900 px-4 py-2 text-white disabled:opacity-40"
          >
            {checking ? <Spinner className="h-4 w-4" /> : 'Kiểm tra'}
          </button>
        </div>
        {keyError && <p className="mt-2 text-sm text-rose-600">{keyError}</p>}
        {me && (
          <p className="mt-2 text-sm text-slate-700">
            <Badge tone="muted">{me.orgName}</Badge>{' '}
            còn <b>{me.dubMinutesRemaining}</b> phút lồng tiếng
            {me.dubMinutesReserved > 0 && ` (đang giữ chỗ ${me.dubMinutesReserved} phút)`}
            {me.dubMinutesQuota === 0 && ' — key này chưa được cấp quota phút nào.'}
          </p>
        )}
      </section>

      <form onSubmit={submit} className="mt-6 rounded-lg border border-slate-200 p-5">
        <h2 className="font-semibold">2. Video và ngôn ngữ</h2>

        <input
          type="file"
          accept="video/*"
          onChange={(e) => setFile(e.target.files[0] || null)}
          className="mt-3 block w-full text-sm"
        />
        {file && (
          <p className={`mt-1 text-sm ${tooBig ? 'text-rose-600' : 'text-slate-600'}`}>
            {file.name} — {formatBytes(file.size)}
            {tooBig && ` (vượt hạn mức ${dub.maxUploadMb} MB)`}
          </p>
        )}

        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <label className="text-sm">
            Ngôn ngữ nguồn
            <select
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-2 py-2"
            >
              {(dub ? dub.sourceLangs : []).map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
          <label className="text-sm">
            Ngôn ngữ đích
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-2 py-2"
            >
              {(dub ? dub.targetLangs : []).map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
          <label className="text-sm">
            Nhạc nền
            <select
              value={bgMode}
              onChange={(e) => setBgMode(e.target.value)}
              className="mt-1 w-full rounded border border-slate-300 px-2 py-2"
            >
              <option value="none">Bỏ nhạc nền gốc</option>
              <option value="demucs">Giữ nhạc nền gốc (Demucs)</option>
            </select>
          </label>
        </div>

        {dub && (
          <p className="mt-3 text-sm text-slate-600">
            Giá: <b>{price}</b> Vox mỗi phút video. Tính theo thời lượng thật đo được
            sau khi xử lý xong, không phải theo con số ước lượng lúc gửi.
          </p>
        )}

        <button
          type="submit"
          disabled={!file || !apiKey.trim() || busy || tooBig || (dub && !dub.enabled)}
          className="mt-4 rounded bg-indigo-600 px-5 py-2 font-medium text-white disabled:opacity-40"
        >
          {busy ? 'Đang xử lý…' : 'Lồng tiếng video này'}
        </button>
      </form>

      {(busy || job) && (
        <section className="mt-6 rounded-lg border border-slate-200 p-5">
          <h2 className="font-semibold">3. Tiến trình</h2>

          {uploadPct > 0 && uploadPct < 100 && (
            <p className="mt-2 text-sm text-slate-700">Đang tải lên… {uploadPct}%</p>
          )}

          {job && (
            <div className="mt-2 space-y-1 text-sm text-slate-700">
              <p>Mã job: <code>{job.jobId}</code></p>
              <p>
                Trạng thái: <b>{job.status}</b>
                {job.status === 'queued' && ' — đang chờ máy xử lý nhận việc'}
                {job.status === 'running' && ' — đang nghe-chép, dịch và đọc lại'}
              </p>
              {job.error && <p className="text-rose-600">{job.error}</p>}
              {job.costVox != null && <p>Đã tính: {job.costVox} Vox</p>}
            </div>
          )}

          {job && job.status === 'done' && !resultUrl && (
            <button
              type="button"
              onClick={fetchResult}
              className="mt-3 rounded bg-emerald-600 px-4 py-2 text-white"
            >
              Tải video kết quả
            </button>
          )}

          {resultUrl && (
            <div className="mt-3">
              {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
              <video src={resultUrl} controls className="w-full rounded" />
              <a
                href={resultUrl}
                download={`dubbed_${job.jobId}.mp4`}
                className="mt-2 inline-block text-indigo-600 underline"
              >
                Lưu về máy
              </a>
              <p className="mt-1 text-xs text-slate-500">
                Máy chủ đã xoá bản này ngay sau khi tải (chính sách dữ liệu) — hãy lưu
                lại trước khi rời trang.
              </p>
            </div>
          )}

          {error && <p className="mt-3 text-sm text-rose-600">{error}</p>}
        </section>
      )}
    </div>
  )
}
