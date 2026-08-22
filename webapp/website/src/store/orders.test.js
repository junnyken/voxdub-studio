import { beforeEach, describe, expect, it } from 'vitest'

import {
  forgetOrder, getOrderToken, listOrders, markOrderPaid, rememberOrder,
} from './orders'

// accessToken chỉ được máy chủ trả về ĐÚNG MỘT LẦN (xem comment gốc trong
// orders.js) — mất nó là mất đường lấy mã kích hoạt. Test này bảo vệ đúng
// hành vi lưu/đọc/ghi đè đó qua localStorage thật (jsdom), không mock.
describe('orders store (localStorage)', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('rememberOrder rồi getOrderToken đọc lại đúng accessToken', () => {
    rememberOrder({ orderCode: 'VOX123456', accessToken: 'secret-token-1', amountVnd: 50000, vox: 5000 })
    expect(getOrderToken('VOX123456')).toBe('secret-token-1')
  })

  it('đơn không tồn tại trả về chuỗi rỗng, không throw', () => {
    expect(getOrderToken('KHONG-TON-TAI')).toBe('')
  })

  it('rememberOrder lại cùng orderCode thì GHI ĐÈ, không nhân đôi', () => {
    rememberOrder({ orderCode: 'VOX111111', accessToken: 'token-a', amountVnd: 10000, vox: 1000 })
    rememberOrder({ orderCode: 'VOX111111', accessToken: 'token-b', amountVnd: 10000, vox: 1000 })
    const orders = listOrders()
    expect(orders.filter((o) => o.orderCode === 'VOX111111')).toHaveLength(1)
    expect(getOrderToken('VOX111111')).toBe('token-b')
  })

  it('listOrders sắp mới nhất lên đầu', () => {
    rememberOrder({ orderCode: 'VOX000001', accessToken: 't1', amountVnd: 1, vox: 1 })
    rememberOrder({ orderCode: 'VOX000002', accessToken: 't2', amountVnd: 1, vox: 1 })
    const orders = listOrders()
    expect(orders[0].orderCode).toBe('VOX000002')
  })

  it('chỉ giữ tối đa 20 đơn gần nhất', () => {
    for (let i = 0; i < 25; i += 1) {
      rememberOrder({
        orderCode: `VOX${String(i).padStart(6, '0')}`, accessToken: `t${i}`,
        amountVnd: 1, vox: 1,
      })
    }
    expect(listOrders()).toHaveLength(20)
    // 5 đơn cũ nhất (000000-000004) phải bị loại — mất token là mất luôn.
    expect(getOrderToken('VOX000000')).toBe('')
    expect(getOrderToken('VOX000024')).toBe('t24')
  })

  it('markOrderPaid gắn keyCode + paidAt vào đúng đơn, không đụng đơn khác', () => {
    rememberOrder({ orderCode: 'VOX222222', accessToken: 't', amountVnd: 1, vox: 1 })
    rememberOrder({ orderCode: 'VOX333333', accessToken: 't', amountVnd: 1, vox: 1 })
    markOrderPaid('VOX222222', 'VOX-AAAA-BBBB-CCCC')
    const orders = listOrders()
    const paid = orders.find((o) => o.orderCode === 'VOX222222')
    const untouched = orders.find((o) => o.orderCode === 'VOX333333')
    expect(paid.keyCode).toBe('VOX-AAAA-BBBB-CCCC')
    expect(paid.paidAt).toBeTruthy()
    expect(untouched.keyCode).toBeUndefined()
  })

  it('markOrderPaid trên đơn không tồn tại không throw, không tạo đơn mới', () => {
    expect(() => markOrderPaid('KHONG-CO', 'X')).not.toThrow()
    expect(listOrders()).toHaveLength(0)
  })

  it('forgetOrder xoá đúng 1 đơn', () => {
    rememberOrder({ orderCode: 'VOX444444', accessToken: 't', amountVnd: 1, vox: 1 })
    rememberOrder({ orderCode: 'VOX555555', accessToken: 't', amountVnd: 1, vox: 1 })
    forgetOrder('VOX444444')
    const orders = listOrders()
    expect(orders).toHaveLength(1)
    expect(orders[0].orderCode).toBe('VOX555555')
  })

  it('localStorage rỗng/hỏng: listOrders trả mảng rỗng, không throw', () => {
    localStorage.setItem('voxdub_orders', 'không phải JSON')
    expect(listOrders()).toEqual([])
  })
})
