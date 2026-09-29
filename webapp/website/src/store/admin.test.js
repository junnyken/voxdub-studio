/**
 * Phiên đăng nhập admin — token này mở được toàn bộ hệ thống (cộng/trừ
 * credit, khoá máy, đổi nhà cung cấp AI). Trọng tâm test: phân biệt đúng
 * "token sai" (phải đăng xuất, xoá token) với "mất mạng tạm thời" (KHÔNG
 * được đăng xuất một phiên còn hợp lệ chỉ vì chớp mạng) — bug thật phát
 * hiện khi viết test này: `restore()` cũ coi mọi lỗi (kể cả OFFLINE) là
 * "token sai", nên admin đang có phiên hợp lệ mở lại tab đúng lúc mạng
 * chập chờn sẽ bị đăng xuất oan, phải nhập lại token dù token vẫn còn dùng
 * được.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { adminApi } from '../api/client'
import { useAdminAuth } from './admin'

vi.mock('../api/client', () => ({
  adminApi: { whoami: vi.fn() },
}))

const TOKEN_KEY = 'voxdub_admin_token'

beforeEach(() => {
  sessionStorage.clear()
  useAdminAuth.setState({ token: '', checking: false, authed: false })
  vi.clearAllMocks()
})

describe('login()', () => {
  it('token đúng: máy chủ xác nhận -> lưu token, authed=true', async () => {
    adminApi.whoami.mockResolvedValue({ ok: true })
    const result = await useAdminAuth.getState().login('token-dung')
    expect(result).toEqual({ ok: true })
    expect(useAdminAuth.getState().authed).toBe(true)
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('token-dung')
  })

  it('token sai: máy chủ từ chối -> KHÔNG lưu token, authed=false', async () => {
    const err = Object.assign(new Error('Token không đúng'), { code: 'INVALID_TOKEN' })
    adminApi.whoami.mockRejectedValue(err)
    const result = await useAdminAuth.getState().login('token-sai')
    expect(result).toEqual({ ok: false, message: 'Token không đúng' })
    expect(useAdminAuth.getState().authed).toBe(false)
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })
})

describe('restore() — mở lại tab admin', () => {
  it('chưa từng đăng nhập (sessionStorage rỗng) -> authed=false, không gọi máy chủ', async () => {
    const ok = await useAdminAuth.getState().restore()
    expect(ok).toBe(false)
    expect(adminApi.whoami).not.toHaveBeenCalled()
  })

  it('token đã lưu còn hợp lệ -> authed=true', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'phien-cu-con-hop-le')
    adminApi.whoami.mockResolvedValue({ ok: true })
    const ok = await useAdminAuth.getState().restore()
    expect(ok).toBe(true)
    expect(useAdminAuth.getState().authed).toBe(true)
    expect(useAdminAuth.getState().token).toBe('phien-cu-con-hop-le')
  })

  it('máy chủ THẬT SỰ từ chối token -> xoá token, đăng xuất', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'token-bi-thu-hoi')
    const err = Object.assign(new Error('Token đã bị thu hồi'), { code: 'INVALID_TOKEN' })
    adminApi.whoami.mockRejectedValue(err)
    const ok = await useAdminAuth.getState().restore()
    expect(ok).toBe(false)
    expect(useAdminAuth.getState().authed).toBe(false)
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
  })

  it('mất mạng tạm thời (OFFLINE) -> KHÔNG đăng xuất, giữ nguyên token để thử lại', async () => {
    sessionStorage.setItem(TOKEN_KEY, 'phien-hop-le-nhung-mat-mang')
    const err = Object.assign(new Error('Không kết nối được máy chủ.'), { code: 'OFFLINE' })
    adminApi.whoami.mockRejectedValue(err)
    const ok = await useAdminAuth.getState().restore()
    expect(ok).toBe(false)
    // Chưa xác thực được LƯỢT NÀY, nhưng token vẫn còn nguyên để lượt sau
    // (khi mạng có lại) thử lại — không phải trạng thái "đăng xuất".
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('phien-hop-le-nhung-mat-mang')
    expect(useAdminAuth.getState().checking).toBe(false)
  })
})

describe('logout()', () => {
  it('xoá token khỏi sessionStorage và state', () => {
    sessionStorage.setItem(TOKEN_KEY, 'dang-dang-nhap')
    useAdminAuth.setState({ token: 'dang-dang-nhap', authed: true })
    useAdminAuth.getState().logout()
    expect(sessionStorage.getItem(TOKEN_KEY)).toBeNull()
    expect(useAdminAuth.getState().authed).toBe(false)
    expect(useAdminAuth.getState().token).toBe('')
  })
})
