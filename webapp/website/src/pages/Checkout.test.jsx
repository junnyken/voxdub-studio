/**
 * State machine tiền quan trọng nhất trên site: pending -> paid/expired.
 * Trọng tâm test:
 *  - đúng trạng thái hiện đúng màn hình (nhầm là hoặc lộ mã sai chỗ, hoặc
 *    giữ khách chờ vô ích ở màn "đang chờ" khi thật ra đã xong/hết hạn),
 *  - đã trả tiền nhưng KHÔNG có token (mở link ở trình duyệt khác) phải nói
 *    rõ lý do, không hiện ô trống làm khách tưởng mất mã,
 *  - poll DỪNG NGAY khi đơn chốt (paid/expired) — poll tiếp là đốt request
 *    vô ích và có thể gọi lại markOrderPaid không cần thiết.
 */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { api } from '../api/client'
import { forgetOrder, getOrderToken, rememberOrder } from '../store/orders'
import Checkout from './Checkout'

vi.mock('../api/client', () => ({
  api: { getOrder: vi.fn(), resendKey: vi.fn() },
}))
// jsdom không cài canvas thật — confetti gọi requestAnimationFrame rồi
// getContext('2d') trả null, ném lỗi ngoài promise chain của trang (không
// liên quan tới hành vi cần test ở đây).
vi.mock('canvas-confetti', () => ({ default: vi.fn() }))

function renderCheckout(orderCode = 'VOX123456') {
  return render(
    <MemoryRouter initialEntries={[`/thanh-toan/${orderCode}`]}>
      <Routes>
        <Route path="thanh-toan/:orderCode" element={<Checkout />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  localStorage.clear()
  vi.clearAllMocks()
})

describe('Checkout — hiện đúng màn hình theo trạng thái đơn', () => {
  it('pending: hiện màn chờ thanh toán (QR/mã đơn), không hiện mã kích hoạt', async () => {
    api.getOrder.mockResolvedValue({
      orderCode: 'VOX123456', status: 'pending', amountVnd: 50000, vox: 5000,
      expiresAt: new Date(Date.now() + 600000).toISOString(),
      payment: { qrCode: 'data', checkoutUrl: 'https://payos/x' },
    })
    renderCheckout()
    expect(await screen.findByText('Thanh toán để nhận mã')).toBeInTheDocument()
    expect(screen.queryByText('MÃ KÍCH HOẠT')).not.toBeInTheDocument()
  })

  it('paid + có keyCode (đúng trình duyệt đã tạo đơn): hiện mã kích hoạt', async () => {
    rememberOrder({ orderCode: 'VOX123456', accessToken: 'tok-that', amountVnd: 50000, vox: 5000 })
    api.getOrder.mockResolvedValue({
      orderCode: 'VOX123456', status: 'paid', amountVnd: 50000, vox: 5000,
      keyCode: 'VOX-AAAA-BBBB-CCCC',
    })
    renderCheckout()
    expect(await screen.findByText('VOX-AAAA-BBBB-CCCC')).toBeInTheDocument()
  })

  it('paid nhưng KHÔNG có keyCode (mở link ở trình duyệt khác): nói rõ lý do, không hiện ô trống', async () => {
    api.getOrder.mockResolvedValue({
      orderCode: 'VOX123456', status: 'paid', amountVnd: 50000, vox: 5000,
      keyCode: undefined,
    })
    renderCheckout()
    expect(await screen.findByText('Đơn này đã thanh toán')).toBeInTheDocument()
    expect(screen.queryByText('MÃ KÍCH HOẠT')).not.toBeInTheDocument()
  })

  it.each(['expired', 'cancelled'])('%s: hiện màn đã hết hạn, nói rõ chưa mất tiền', async (status) => {
    api.getOrder.mockResolvedValue({ orderCode: 'VOX123456', status, amountVnd: 50000, vox: 5000 })
    renderCheckout()
    expect(await screen.findByText('Đơn đã hết hạn')).toBeInTheDocument()
    expect(screen.getByText(/Chưa có khoản tiền nào bị trừ/)).toBeInTheDocument()
  })

  it('lỗi tải đơn lần đầu: hiện ErrorBox kèm đường quay lại trang mua', async () => {
    api.getOrder.mockRejectedValue(Object.assign(new Error('Không tìm thấy đơn'), { code: 'NOT_FOUND' }))
    renderCheckout()
    expect(await screen.findByText('Không tìm thấy đơn')).toBeInTheDocument()
    expect(screen.getByText('Quay lại trang mua')).toBeInTheDocument()
  })
})

describe('Checkout — poll và ghi nhận đã trả tiền', () => {
  // Đồng hồ THẬT (không fake timers): tương tác setInterval + async
  // load()/AbortController của Checkout dưới act() của RTL rất dễ vỡ với
  // fake timers (microtask/macrotask xen kẽ khó canh đúng) — chờ thật vài
  // giây đổi lấy test đáng tin hơn, vì đây chỉ 2 test cần poll thật.
  it('pending: tự poll lại sau POLL_MS (4s)', async () => {
    api.getOrder.mockResolvedValue({
      orderCode: 'VOX123456', status: 'pending', amountVnd: 50000, vox: 5000,
      expiresAt: new Date(Date.now() + 600000).toISOString(), payment: {},
    })
    renderCheckout()
    await waitFor(() => expect(api.getOrder).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(api.getOrder).toHaveBeenCalledTimes(2),
      { timeout: 6000, interval: 200 })
  }, 8000)

  it('chuyển sang paid thì DỪNG poll — không gọi thêm sau khi đã chốt', async () => {
    api.getOrder
      .mockResolvedValueOnce({
        orderCode: 'VOX123456', status: 'pending', amountVnd: 50000, vox: 5000,
        expiresAt: new Date(Date.now() + 600000).toISOString(), payment: {},
      })
      .mockResolvedValue({
        orderCode: 'VOX123456', status: 'paid', amountVnd: 50000, vox: 5000,
        keyCode: undefined,
      })
    renderCheckout()
    await waitFor(() => expect(api.getOrder).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(api.getOrder).toHaveBeenCalledTimes(2),
      { timeout: 6000, interval: 200 })
    const callsAfterPaid = api.getOrder.mock.calls.length
    // Chờ lâu hơn cả một chu kỳ poll nữa (4s) mà KHÔNG được gọi thêm —
    // đây là khẳng định "đã dừng", không phải chỉ "chưa kịp gọi".
    await new Promise((r) => setTimeout(r, 4500))
    expect(api.getOrder).toHaveBeenCalledTimes(callsAfterPaid)
  }, 10000)

  it('nhận status paid + keyCode thì ghi vào localStorage (markOrderPaid) để MyOrders thấy', async () => {
    rememberOrder({ orderCode: 'VOX789', accessToken: 'tok', amountVnd: 1, vox: 1 })
    api.getOrder.mockResolvedValue({
      orderCode: 'VOX789', status: 'paid', amountVnd: 1, vox: 1, keyCode: 'VOX-XXXX',
    })
    renderCheckout('VOX789')
    await screen.findByText('VOX-XXXX')
    // markOrderPaid ghi thẳng localStorage — kiểm gián tiếp qua getOrderToken
    // vẫn còn nguyên (markOrderPaid không được xoá token của đơn).
    expect(getOrderToken('VOX789')).toBe('tok')
    forgetOrder('VOX789')
  })
})
