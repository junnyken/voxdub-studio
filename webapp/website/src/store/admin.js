/**
 * Phiên đăng nhập admin.
 *
 * Token nằm trong `sessionStorage` chứ không phải `localStorage`: máy quản
 * trị thường là máy dùng chung hoặc máy để bàn ở văn phòng, và token này mở
 * được toàn bộ hệ thống (cộng tiền, khóa máy, đổi mô hình). Đóng tab là hết
 * phiên — đánh đổi một chút bất tiện lấy việc không để token nằm lại trên
 * đĩa vô thời hạn.
 */
import { create } from 'zustand'

import { adminApi } from '../api/client'

const TOKEN_KEY = 'voxdub_admin_token'

export const useAdminAuth = create((set) => ({
  token: sessionStorage.getItem(TOKEN_KEY) || '',
  checking: false,
  authed: false,

  /** Thử token với máy chủ; chỉ lưu khi máy chủ xác nhận đúng. */
  async login(token) {
    sessionStorage.setItem(TOKEN_KEY, token)
    set({ checking: true })
    try {
      await adminApi.whoami()
      set({ token, authed: true, checking: false })
      return { ok: true }
    } catch (err) {
      // Token sai thì không giữ lại — để nguyên sẽ khiến mọi request sau
      // đều 401 và người dùng không hiểu vì sao trang trắng.
      sessionStorage.removeItem(TOKEN_KEY)
      set({ token: '', authed: false, checking: false })
      return { ok: false, message: err.message }
    }
  },

  /** Kiểm tra lại token đã lưu khi mở lại tab admin. */
  async restore() {
    const token = sessionStorage.getItem(TOKEN_KEY) || ''
    if (!token) { set({ authed: false, checking: false }); return false }
    set({ checking: true })
    try {
      await adminApi.whoami()
      set({ token, authed: true, checking: false })
      return true
    } catch (err) {
      // Mất mạng tạm thời KHÔNG có nghĩa token sai — xoá token ở đây sẽ đăng
      // xuất admin đang dùng token còn hợp lệ chỉ vì một lượt chớp mạng.
      // Chỉ xoá token khi máy chủ THẬT SỰ từ chối nó.
      if (err.code === 'OFFLINE') {
        set({ checking: false })
        return false
      }
      sessionStorage.removeItem(TOKEN_KEY)
      set({ token: '', authed: false, checking: false })
      return false
    }
  },

  logout() {
    sessionStorage.removeItem(TOKEN_KEY)
    set({ token: '', authed: false })
  },
}))
