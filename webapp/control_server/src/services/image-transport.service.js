'use strict'

/**
 * Ba cách gọi mô hình sinh ảnh (mini-spec C3).
 *
 * "Chuẩn OpenAI" là một cái tên gây hiểu nhầm: với phần CHỮ thì các nhà cung
 * cấp thật sự nói chung một giọng (`/chat/completions`), nhưng với phần ẢNH
 * thì mỗi nhà một kiểu — khác đường dẫn, khác tên trường mang ảnh vào, khác
 * chỗ đặt ảnh ra. Gộp cả ba vào một nhánh `if` là cách chắc chắn nhất để nhận
 * về `404` mà không hiểu vì sao.
 *
 *   google           POST {base}/models/{model}:generateContent
 *                    ảnh vào: contents[].parts[].inlineData
 *                    ảnh ra:  candidates[0].content.parts[].inlineData
 *
 *   openrouter_images POST {base}/images
 *                    ảnh vào: input_references[].image_url.url  (data URI)
 *                    ảnh ra:  data[0].b64_json
 *
 *   openai_images    POST {base}/images/edits   (thân JSON, không multipart)
 *                    ảnh vào: image  (data URI)
 *                    ảnh ra:  data[0].b64_json
 *
 * Tách hẳn khỏi `ai-gateway.service.js` để **dựng yêu cầu và đọc trả lời đều
 * test được mà không cần mạng** — `control_server` cố ý chỉ có test thuần, và
 * đọc nhầm một trường thì hệ thống báo "mô hình không trả về ảnh" y hệt lúc
 * mô hình từ chối vẽ thật.
 */

/** Những giao thức sinh được ảnh, kèm nhãn hiện trong trang quản trị. */
const GIAO_THUC = {
  google: 'Google Gemini',
  openrouter_images: 'OpenRouter (Images API)',
  openai_images: 'OpenAI / Grok / tương thích (Images API)',
  custom_images: 'Tự khai (nền tảng khác)',
}

/**
 * Chỗ điền được trong mẫu tự khai. `image_data_uri` và `image_base64` là hai
 * cách khác nhau để đưa ẢNH GỐC vào — mẫu thiếu cả hai nghĩa là nhà cung cấp
 * sẽ vẽ sản phẩm từ đầu thay vì dựng lại ảnh có sẵn, nên `loiMauTuKhai()`
 * chặn thẳng trường hợp đó.
 */
const CHO_DIEN = ['model', 'prompt', 'image_data_uri', 'image_base64',
  'image_mime', 'api_key']
const CHO_DIEN_ANH = ['image_data_uri', 'image_base64']

/** Thay {{cho_dien}} trong một chuỗi, có thoát ký tự cho đúng JSON. */
function dienMau(mau, gia_tri) {
  return String(mau).replace(/\{\{\s*([a-z_]+)\s*\}\}/g, (nguyen, ten) => {
    if (!Object.prototype.hasOwnProperty.call(gia_tri, ten)) return nguyen
    // Câu lệnh có thể chứa dấu nháy và xuống dòng; nhét thẳng vào JSON là hỏng
    // cả thân yêu cầu. `JSON.stringify` rồi bỏ hai dấu nháy ngoài = đúng phần
    // thoát ký tự mà JSON cần.
    return JSON.stringify(String(gia_tri[ten])).slice(1, -1)
  })
}

/** Đọc theo đường dẫn kiểu "data.0.b64_json". */
function theoDuong(goc, duong) {
  if (!duong) return undefined
  return String(duong).split('.').reduce(
    (cho, khoa) => (cho == null ? undefined : cho[khoa]), goc)
}

/**
 * Mẫu tự khai có dùng được không. Trả `null` nếu ổn, hoặc câu tiếng Việt.
 *
 * Phép kiểm quan trọng nhất là **mẫu phải mang ảnh gốc đi theo**. Không có nó
 * thì nhà cung cấp vẫn trả về một tấm ảnh đẹp — nhưng là sản phẩm do mô hình
 * tưởng tượng ra, đúng thứ tính năng này sinh ra để chống, và nó hỏng theo
 * kiểu KHÔNG có triệu chứng nào.
 */
function loiMauTuKhai(p) {
  const mau = String(p?.imageBodyTemplate || '').trim()
  if (!mau) return 'Thiếu "Mẫu thân yêu cầu" cho giao thức tự khai.'
  if (!String(p?.imagePath || '').trim()) {
    return 'Thiếu "Đường dẫn cửa gọi" (ví dụ /images/edits).'
  }
  if (!String(p?.imageResponsePath || '').trim()) {
    return 'Thiếu "Đường dẫn tới ảnh trong trả lời" (ví dụ data.0.b64_json).'
  }
  try {
    JSON.parse(dienMau(mau, Object.fromEntries(CHO_DIEN.map((k) => [k, 'x']))))
  } catch {
    return 'Mẫu thân yêu cầu không phải JSON hợp lệ.'
  }
  if (!CHO_DIEN_ANH.some((k) => mau.includes(`{{${k}}}`))) {
    return 'Mẫu không chứa ảnh gốc ({{image_data_uri}} hoặc {{image_base64}}). '
      + 'Thiếu nó thì mô hình vẽ sản phẩm từ đầu chứ không dựng lại ảnh của '
      + 'bạn — đúng thứ tính năng này sinh ra để chống.'
  }
  return null
}

/** Ảnh dạng {mimeType, data} → data URI mà hai API kiểu OpenAI đòi. */
function dataUri(image) {
  return `data:${image.mimeType};base64,${image.data}`
}

function _base(provider, macDinh) {
  return String(provider.baseUrl || macDinh).replace(/\/+$/, '')
}

/**
 * Dựng lượt gọi mạng: trả `{ url, body, headers }`.
 *
 * Không tự gọi để nơi dùng vẫn giữ được retry/ghi nhận lỗi của nó, và để
 * test dựng được yêu cầu rồi soi từng trường mà không chạm mạng.
 */
function dungYeuCau({ provider, prompt, image }) {
  const key = provider.apiKey

  if (provider.type === 'google') {
    const base = _base(provider, 'https://generativelanguage.googleapis.com/v1beta')
    return {
      url: `${base}/models/${provider.model}:generateContent`,
      headers: { 'Content-Type': 'application/json', 'x-goog-api-key': key },
      body: {
        contents: [{
          role: 'user',
          parts: [
            { text: prompt },
            { inlineData: { mimeType: image.mimeType, data: image.data } },
          ],
        }],
      },
    }
  }

  if (provider.type === 'openrouter_images') {
    const base = _base(provider, 'https://openrouter.ai/api/v1')
    return {
      url: `${base}/images`,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${key}`,
      },
      body: {
        model: provider.model,
        prompt,
        // Ảnh gốc là THAM CHIẾU, không phải ảnh mẫu phong cách: đây là chỗ
        // giữ cho sản phẩm trong ảnh ra vẫn là sản phẩm thật của người bán.
        input_references: [
          { type: 'image_url', image_url: { url: dataUri(image) } },
        ],
      },
    }
  }

  if (provider.type === 'custom_images') {
    if (loiMauTuKhai(provider)) return null
    const base = _base(provider, '')
    const duong = String(provider.imagePath).startsWith('/')
      ? provider.imagePath : `/${provider.imagePath}`
    const than = dienMau(provider.imageBodyTemplate, {
      model: provider.model,
      prompt,
      image_data_uri: dataUri(image),
      image_base64: image.data,
      image_mime: image.mimeType,
      api_key: key,
    })
    const tenHeader = provider.authHeaderName || 'Authorization'
    const giaTriHeader = dienMau(provider.authHeaderValue || 'Bearer {{api_key}}',
      { api_key: key })
    return {
      url: `${base}${duong}`,
      headers: { 'Content-Type': 'application/json', [tenHeader]: giaTriHeader },
      body: JSON.parse(than),
    }
  }

  if (provider.type === 'openai_images') {
    const base = _base(provider, 'https://api.openai.com/v1')
    return {
      url: `${base}/images/edits`,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${key}`,
      },
      // Dùng SỬA ẢNH, không phải sinh ảnh mới: `/images/generations` không
      // nhận ảnh vào, nên sản phẩm sẽ do mô hình bịa ra hoàn toàn.
      body: { model: provider.model, prompt, image: dataUri(image) },
    }
  }

  return null
}

/**
 * Rút ảnh khỏi trả lời. Trả `{ mimeType, data }`, hoặc `null` nếu không có
 * ảnh — kèm `{ lyDo }` khi mô hình có nói lý do (từ chối vẽ, vi phạm chính
 * sách nội dung…), vì "không có ảnh" và "từ chối vì lý do X" là hai chuyện
 * người dùng phải phân biệt được.
 */
function docTraLoi({ type, data, provider }) {
  if (type === 'custom_images') {
    const b64 = theoDuong(data, provider?.imageResponsePath)
    if (typeof b64 === 'string' && b64) {
      return {
        image: {
          mimeType: theoDuong(data, provider?.imageMimePath) || 'image/png',
          data: b64,
        },
      }
    }
    return { image: null, lyDo: data?.error?.message || '' }
  }

  if (type === 'google') {
    const parts = data?.candidates?.[0]?.content?.parts || []
    const anh = parts.find((x) => x.inlineData)
    if (anh) {
      return { image: { mimeType: anh.inlineData.mimeType, data: anh.inlineData.data } }
    }
    return { image: null, lyDo: parts.find((x) => x.text)?.text || '' }
  }

  // Hai API kiểu OpenAI trả về cùng một chỗ: `data[0].b64_json`.
  const muc = data?.data?.[0]
  const b64 = muc?.b64_json
  if (b64) {
    return {
      image: {
        // OpenRouter nói `media_type`, OpenAI thì tuỳ `output_format`. Không
        // ai nói thì mặc định PNG — cả hai đều trả PNG khi để mặc định.
        mimeType: muc.media_type || muc.mime_type
          || (muc.output_format ? `image/${muc.output_format}` : 'image/png'),
        data: b64,
      },
    }
  }
  // Một số nhà trả `url` thay vì base64 khi không xin b64_json. Nói rõ ra
  // thay vì báo chung chung "không trả về ảnh".
  if (muc?.url) {
    return {
      image: null,
      lyDo: 'Mô hình trả về đường dẫn ảnh thay vì dữ liệu ảnh. Chọn mô hình '
        + 'trả base64 (b64_json).',
    }
  }
  return { image: null, lyDo: data?.error?.message || '' }
}


/**
 * Vai trò và giao thức có đi được với nhau không.
 *
 * Chặn ngay lúc LƯU thay vì lúc chạy: sai cặp thì lượt gọi đầu tiên mới lộ,
 * mà lúc đó người cấu hình đã rời trang từ lâu. Đây đúng lớp lỗi của V94 —
 * cấu hình sai mà hệ thống không nói được sai ở đâu.
 *
 * Trả `null` nếu hợp lệ, hoặc một câu tiếng Việt nói rõ phải chọn gì.
 */
function loiCapVaiGiaoThuc(role, type) {
  const sinhAnh = Object.prototype.hasOwnProperty.call(GIAO_THUC, type)
  if (role === 'image') {
    if (!sinhAnh) {
      return 'Vai "Sinh ảnh" cần giao thức sinh được ảnh: '
        + `${Object.values(GIAO_THUC).join(', ')}. Giao thức "Chuẩn OpenAI" `
        + 'chỉ gọi được phần chữ (/chat/completions).'
    }
    return null
  }
  // Vai chữ: các API ảnh thuần tuý không có đường gọi /chat/completions.
  // Suy ra từ chính bảng giao thức thay vì liệt kê tay — liệt kê tay thì thêm
  // một giao thức ảnh mới là quên một chỗ, và test đã bắt được đúng lỗi đó.
  if (type !== 'google' && Object.prototype.hasOwnProperty.call(GIAO_THUC, type)) {
    return `Giao thức "${GIAO_THUC[type]}" chỉ sinh ảnh, không dùng được cho `
      + `vai "${role}". Chọn "Chuẩn OpenAI" hoặc "Google Gemini".`
  }
  return null
}

module.exports = {
  GIAO_THUC, CHO_DIEN, dungYeuCau, docTraLoi, dataUri,
  loiCapVaiGiaoThuc, loiMauTuKhai, dienMau, theoDuong,
}
