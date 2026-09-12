/**
 * `request()`/`ApiError`/`adminRequest` là nền tảng của MỌI lượt gọi tiền
 * (đơn hàng, mã kích hoạt) và MỌI thao tác admin (cộng/trừ credit, khoá máy,
 * đổi nhà cung cấp AI) — hỏng ở đây thì mọi trang gọi API đều hỏng theo mà
 * không ai biết vì sao. Trọng tâm test: phân biệt đúng "mất mạng" (OFFLINE)
 * với "máy chủ từ chối" (code/status từ backend), vì hai UI khác nhau dùng
 * hai nhánh này để hiện thông báo khác nhau.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { adminApi, api, ApiError } from './client'

beforeEach(() => {
  global.fetch = vi.fn()
  sessionStorage.clear()
})
afterEach(() => { vi.restoreAllMocks() })

function fakeResponse(status, body, { ok } = {}) {
  return {
    ok: ok !== undefined ? ok : status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  }
}

describe('request() — thành công', () => {
  it('trả về đúng JSON khi máy chủ trả 200', async () => {
    global.fetch.mockResolvedValue(fakeResponse(200, { ok: true, vox: 5000 }))
    const result = await api.health()
    expect(result).toEqual({ ok: true, vox: 5000 })
  })

  it('204 hoặc phản hồi không phải JSON không throw, trả null', async () => {
    global.fetch.mockResolvedValue({
      ok: true, status: 204,
      json: () => Promise.reject(new Error('Unexpected end of JSON input')),
    })
    const result = await api.health()
    expect(result).toBeNull()
  })
})

describe('request() — mất mạng vs máy chủ từ chối', () => {
  it('fetch throw (mất mạng) -> ApiError code OFFLINE, không phải lỗi khác', async () => {
    global.fetch.mockRejectedValue(new TypeError('Failed to fetch'))
    await expect(api.health()).rejects.toMatchObject({
      code: 'OFFLINE',
    })
  })

  it('AbortError (huỷ request chủ động) không bị gói thành ApiError', async () => {
    const abort = new Error('aborted')
    abort.name = 'AbortError'
    global.fetch.mockRejectedValue(abort)
    await expect(api.health()).rejects.toBe(abort)
  })

  it('HTTP lỗi kèm code/message riêng của máy chủ được giữ nguyên', async () => {
    global.fetch.mockResolvedValue(
      fakeResponse(402, { message: 'Hết Vox', code: 'INSUFFICIENT_CREDIT' }))
    try {
      await api.health()
      expect.unreachable('phải throw')
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError)
      expect(err.code).toBe('INSUFFICIENT_CREDIT')
      expect(err.status).toBe(402)
      expect(err.message).toBe('Hết Vox')
    }
  })

  it('HTTP lỗi không có body JSON hợp lệ vẫn báo đúng mã trạng thái', async () => {
    global.fetch.mockResolvedValue({
      ok: false, status: 500,
      json: () => Promise.reject(new Error('not json')),
    })
    await expect(api.health()).rejects.toMatchObject({
      status: 500,
      message: 'Lỗi máy chủ (HTTP 500)',
    })
  })
})

describe('adminRequest — token từ sessionStorage', () => {
  it('gắn X-Admin-Token từ sessionStorage vào header', async () => {
    sessionStorage.setItem('voxdub_admin_token', 'phien-that')
    global.fetch.mockResolvedValue(fakeResponse(200, { ok: true }))
    await adminApi.whoami()
    const [, opts] = global.fetch.mock.calls[0]
    expect(opts.headers['X-Admin-Token']).toBe('phien-that')
  })

  it('chưa đăng nhập (sessionStorage rỗng) vẫn gọi được, header rỗng', async () => {
    global.fetch.mockResolvedValue(fakeResponse(401, { message: 'Thiếu token' }))
    await expect(adminApi.whoami()).rejects.toMatchObject({ status: 401 })
    const [, opts] = global.fetch.mock.calls[0]
    expect(opts.headers['X-Admin-Token']).toBe('')
  })

  it('qs() bỏ tham số rỗng/undefined/null, không gửi ?key= trống', async () => {
    global.fetch.mockResolvedValue(fakeResponse(200, { items: [] }))
    await adminApi.devices({ status: '', fingerprint: undefined, page: 2 })
    const [url] = global.fetch.mock.calls[0]
    expect(url).toContain('page=2')
    expect(url).not.toContain('status=')
    expect(url).not.toContain('fingerprint=')
  })
})
