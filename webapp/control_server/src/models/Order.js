'use strict'

/**
 * Đơn mua Vox qua PayOS. Dựng lại từ billing.service.js/admin.js — xem ghi
 * chú trong Device.js.
 */
const mongoose = require('mongoose')

const orderSchema = new mongoose.Schema({
  orderCode: {
    type: String, required: true, unique: true, uppercase: true, trim: true,
  },
  payosOrderCode: { type: Number, required: true, unique: true },
  amountVnd: { type: Number, required: true },
  vox: { type: Number, required: true },
  packageId: { type: String, default: '' },
  packageLabel: { type: String, default: '' },
  email: { type: String, default: '' },
  accessToken: { type: String, required: true },
  status: {
    type: String,
    enum: ['pending', 'paid', 'cancelled', 'expired'],
    default: 'pending',
  },
  keyCode: { type: String, default: '' },
  paidAmountVnd: { type: Number, default: 0 },
  bankRefId: { type: String, default: '' },
  bankGateway: { type: String, default: '' },
  paidAt: { type: Date, default: null },
  expiresAt: { type: Date, required: true },
  payosPaymentLinkId: { type: String, default: '' },
  checkoutUrl: { type: String, default: '' },
  qrCode: { type: String, default: '' },
  createdIp: { type: String, default: '' },
}, { timestamps: true })

module.exports = mongoose.models.Order || mongoose.model('Order', orderSchema)
