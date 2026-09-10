'use strict'

/**
 * Danh mục tác vụ của cổng trợ lý (mini-spec V89).
 *
 * Đây là DANH SÁCH ĐÓNG — app chỉ gửi TÊN tác vụ, không bao giờ gửi prompt.
 * Nhờ vậy chi phí đoán được, và sửa câu chữ hướng dẫn mô hình không cần phát
 * hành lại bản .exe.
 *
 * Mỗi tác vụ tự khai:
 *   - `costKey`     khoá giá trong cấu hình (đổi giá lúc chạy, không sửa mã)
 *   - `maxInput`    trần ký tự đầu vào — CẮT trước khi gọi, không trả tiền rồi
 *                   mới biết là quá dài
 *   - `maxResults`  số kết quả tối đa
 *   - `system`      vai trò của mô hình
 *   - `buildUser`   dựng phần dữ liệu từ input của app
 *
 * Mọi tác vụ trả về cùng một khuôn `{ results: [{ value, reason }] }`. Trường
 * `reason` là BẮT BUỘC: giao diện đã hiện lý do cho từng gợi ý (xem
 * `music_suggest.py` phía app), và người dùng cần biết vì sao máy đề xuất như
 * vậy thay vì tin một cái nhãn. Ép trong schema thì mô hình không bỏ qua được.
 */

/** Khuôn kết quả dùng chung — mọi tác vụ đều theo đúng khuôn này. */
function resultsSchema(maxResults) {
  return {
    type: 'object',
    required: ['results'],
    properties: {
      results: {
        type: 'array',
        minItems: 1,
        maxItems: maxResults,
        items: {
          type: 'object',
          required: ['value', 'reason'],
          properties: {
            value: { type: 'string' },
            reason: { type: 'string' },
          },
        },
      },
    },
  }
}

function cat(text, max) {
  const s = String(text == null ? '' : text).trim()
  return s.length > max ? `${s.slice(0, max)}…` : s
}

/**
 * Cắt CỨNG: kết quả không bao giờ dài quá `max` ký tự, kể cả dấu `…`.
 *
 * Khác `cat()` ở đúng một ký tự, mà một ký tự đó là ranh giới giữa chạy được
 * và vỡ: `cat(x, 1500)` trả về 1501 ký tự nên vẫn vượt `maxlength` của
 * Mongoose. `cat()` dựng cho việc cắt ĐẦU VÀO (dư một ký tự không ai chết);
 * hàm này dành cho văn bản sắp GHI XUỐNG một trường có giới hạn cứng.
 */
function catCung(text, max) {
  const s = String(text == null ? '' : text).trim()
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}

/**
 * Phiên bản của BỘ PROMPT. Sửa câu chữ hướng dẫn mô hình thì TĂNG số này.
 *
 * Hai việc phụ thuộc vào nó, cả hai đều hỏng âm thầm nếu quên tăng:
 *   - nhớ đệm theo nội dung (dưới đây) sẽ trả lại kết quả của prompt CŨ;
 *   - bảng theo dõi không tách được chất lượng trước/sau khi sửa prompt, nên
 *     sửa xong thấy tệ hơn cũng không quy được trách nhiệm.
 */
const PROMPT_VERSION = 1

const TASKS = {
  /**
   * Gợi ý mô tả nhạc nền từ lời thoại.
   *
   * App đã có bản suy bằng luật (đếm chữ + dò từ khoá) chạy offline; tác vụ
   * này là bản nâng cấp khi người dùng có tài khoản. Vì vậy prompt phải đòi
   * MÔ TẢ ĐỂ ĐƯA THẲNG CHO MÁY SINH NHẠC, không phải lời bình luận.
   */
  music_suggest: {
    costKey: 'credit.cost.assist.music_suggest',
    maxInput: 4000,
    maxResults: 3,
    system: [
      'Bạn chọn nhạc nền cho video lồng tiếng Việt.',
      'Người dùng sẽ đưa mô tả của bạn thẳng cho một máy sinh nhạc, nên mỗi',
      'mô tả phải là một câu tả ÂM NHẠC: thể loại, nhạc cụ, tiết tấu, tâm',
      'trạng. Không nhắc tên bài hát hay nghệ sĩ có thật (máy sinh nhạc không',
      'dùng được, và dễ đụng bản quyền). Không mô tả hình ảnh video.',
      'Nhạc chỉ làm nền cho giọng đọc: tránh đề xuất thứ có giai điệu lấn át.',
      'Viết tiếng Việt, mỗi mô tả tối đa 20 chữ.',
      'Phần lý do: nói ngắn gọn dựa vào nội dung lời thoại, tối đa 15 chữ.',
    ].join(' '),
    buildUser: (input) => {
      const loi = cat(input.transcript, 4000)
      const tieu_de = cat(input.videoTitle, 200)
      return [
        tieu_de ? `Tiêu đề video: ${tieu_de}` : '',
        'Lời thoại (đã chép từ chính video này):',
        loi,
      ].filter(Boolean).join('\n')
    },
  },

  /**
   * Giải thích một dòng lỗi kỹ thuật thành việc người dùng làm được.
   *
   * Giá 0 Vox và chạy cả khi hết Vox — người đang gặp lỗi mà còn bị chặn vì
   * hết tiền thì đó là lúc tệ nhất để thu phí. Bù lại có hạn mức ngày riêng.
   */
  explain_error: {
    costKey: 'credit.cost.assist.explain_error',
    maxInput: 2000,
    maxResults: 1,
    system: [
      'Bạn giải thích lỗi của phần mềm lồng tiếng VoxDub Studio cho người',
      'dùng KHÔNG rành kỹ thuật, bằng tiếng Việt.',
      'Trường value: nói người dùng cần LÀM GÌ, tối đa 45 chữ, câu mệnh lệnh',
      'cụ thể. Trường reason: nói CHUYỆN GÌ đã xảy ra, tối đa 25 chữ.',
      'Không dùng từ kỹ thuật (traceback, exception, module, PATH, venv...),',
      'không nhắc tên tệp mã nguồn, không bảo người dùng đi báo lỗi trên',
      'GitHub. Nếu lỗi cho thấy thiếu một chương trình phụ trợ thì nói rõ tên',
      'chương trình đó theo cách người dùng nhận ra.',
      'Không chắc thì nói thẳng là chưa rõ nguyên nhân và đề xuất chạy lại,',
      'TUYỆT ĐỐI không bịa ra cách sửa nghe có vẻ hợp lý.',
    ].join(' '),
    buildUser: (input) => [
      `Bối cảnh: người dùng đang ở bước "${cat(input.step, 100) || 'không rõ'}".`,
      'Dòng lỗi phần mềm ghi lại:',
      cat(input.message, 2000),
    ].join('\n'),
  },

  /**
   * Tóm tắt video thành vài câu + từ khoá.
   *
   * Dùng cho người vừa chép lời xong và cần biết video nói gì mà không phải
   * đọc hết. Từ khoá phải LẤY TỪ lời thoại, không tự nghĩ ra — đây là chỗ mô
   * hình hay bịa nhất.
   */
  video_summary: {
    costKey: 'credit.cost.assist.video_summary',
    maxInput: 8000,
    maxResults: 4,
    system: [
      'Bạn tóm tắt nội dung video dựa trên lời thoại đã chép, bằng tiếng Việt.',
      'Trả về đúng 4 mục theo thứ tự: mục 1 là bản tóm tắt tối đa 3 câu',
      '(value = tóm tắt, reason = "tóm tắt"); ba mục còn lại mỗi mục là MỘT',
      'từ khoá (value = từ khoá, reason = câu trong lời thoại chứa nó).',
      'Từ khoá phải xuất hiện trong lời thoại — không tự nghĩ thêm.',
      'Lời thoại do máy chép nên có thể sai chính tả; tóm ý, đừng trích y',
      'nguyên chỗ nghe nhầm. Không bịa chi tiết không có trong lời thoại.',
    ].join(' '),
    buildUser: (input) => [
      cat(input.videoTitle, 200) ? `Tiêu đề: ${cat(input.videoTitle, 200)}` : '',
      'Lời thoại:',
      cat(input.transcript, 8000),
    ].filter(Boolean).join('\n'),
  },

  /**
   * Đặt tên cho nhân vật dựa trên chính lời họ nói.
   *
   * Người dùng đang phải tự nghĩ tên cho từng người nói mà bước tách giọng
   * tìm ra ("Người nói 1", "Người nói 2"). Tên gợi ý phải NGẮN để còn hiện
   * vừa trong bảng hồ sơ.
   */
  character_name: {
    costKey: 'credit.cost.assist.character_name',
    maxInput: 3000,
    maxResults: 3,
    system: [
      'Bạn đặt tên gọi cho một nhân vật trong video, dựa trên chính lời người',
      'đó nói. Tên phải NGẮN (tối đa 3 chữ), tiếng Việt, dễ nhớ, và nói lên',
      'vai trò hoặc đặc điểm nhận ra được — ví dụ "Người dẫn", "Ông chủ quán".',
      'Nếu trong lời thoại có tên riêng của chính người đó thì ưu tiên dùng.',
      'Không đặt tên xúc phạm, không đoán giới tính khi lời thoại không cho',
      'biết. Phần reason: nói dựa vào đâu, tối đa 12 chữ.',
    ].join(' '),
    buildUser: (input) => [
      `Nhân vật này nói ${Number(input.lineCount) || 0} câu trong video.`,
      'Một số câu của họ:',
      cat(input.lines, 3000),
    ].join('\n'),
  },

  /**
   * Dựng quy ước dịch cho cả series: xưng hô + thuật ngữ cố định.
   *
   * Đây là thứ người dùng đang gõ tay từng dòng ở trang Hồ sơ nhân vật, và
   * là thứ quyết định các tập sau có dịch nhất quán hay không.
   */
  series_glossary: {
    costKey: 'credit.cost.assist.series_glossary',
    maxInput: 8000,
    maxResults: 5,
    system: [
      'Bạn dựng quy ước dịch cho một series video sắp lồng tiếng Việt.',
      'Mục 1: cách xưng hô giữa các nhân vật (value = "tôi – anh" chẳng hạn,',
      'reason = dựa vào đâu). Các mục sau: mỗi mục một thuật ngữ cần dịch cố',
      'định, value viết đúng dạng "gốc = dịch", reason nói vì sao cần cố định.',
      'Chỉ lấy thuật ngữ CÓ trong lời thoại và thật sự lặp lại — thuật ngữ',
      'dịch mỗi lúc một kiểu mới là thứ làm người xem khó theo.',
      'Không đưa từ thông thường ai cũng dịch giống nhau.',
    ].join(' '),
    buildUser: (input) => [
      cat(input.seriesName, 200) ? `Series: ${cat(input.seriesName, 200)}` : '',
      'Lời thoại gốc:',
      cat(input.transcript, 8000),
    ].filter(Boolean).join('\n'),
  },

  /**
   * Viết ngắn lại một câu dịch quá dài so với chỗ trống.
   *
   * Câu dài buộc giọng đọc phải tăng tốc cho kịp, nghe méo — đây là lỗi chất
   * lượng đứng đầu bảng xếp hạng "đáng sửa trước" (mini-spec V64).
   */
  tighten_line: {
    costKey: 'credit.cost.assist.tighten_line',
    maxInput: 1200,
    maxResults: 2,
    system: [
      'Bạn rút gọn một câu thoại tiếng Việt để đọc kịp trong thời lượng cho',
      'phép, giữ NGUYÊN ý và giữ nguyên mọi con số, tên riêng, đơn vị.',
      'Mỗi phương án phải NGẮN HƠN câu gốc rõ rệt, đọc lên vẫn tự nhiên như',
      'lời nói, không viết tắt, không bỏ dấu câu cần thiết.',
      'Phần reason: nói đã lược bỏ gì, tối đa 12 chữ.',
      'Nếu câu gốc đã ngắn gọn hết mức thì nói thẳng trong reason là không',
      'rút thêm được, và trả lại chính câu đó.',
    ].join(' '),
    buildUser: (input) => [
      `Câu gốc (đọc mất ${Number(input.needSeconds) || 0} giây):`,
      cat(input.line, 1200),
      `Chỗ trống chỉ có ${Number(input.roomSeconds) || 0} giây.`,
      `Cần ngắn hơn khoảng ${Number(input.trimPercent) || 20}%.`,
    ].join('\n'),
  },

  /**
   * So ảnh sản phẩm THẬT với ảnh do AI dựng lại — mini-spec C1.
   *
   * Vì sao cần: TikTok Shop cưỡng chế theo chính sách "quảng bá sản phẩm không
   * nhất quán" — video phải khớp sản phẩm đang bán về màu, kích thước, chất
   * liệu, thiết kế. Máy của họ quét bằng thị giác máy tính rồi so với ảnh
   * listing; sai khác nhỏ cũng tính vi phạm, và 6 lần cùng loại trong 90 ngày
   * là mất quyền bán bất kể điểm CHR.
   *
   * Nên tác vụ này KHÔNG chấm điểm giống nhau bằng một con số. Nó trả về:
   *   value  = "SAFE" hoặc "CONCEPT"
   *   reason = ĐÃ ĐỔI CÁI GÌ, bằng lời người đọc hiểu
   * Con số 0,58 thì seller không cãi được với TikTok; câu "chữ trên nhãn khác
   * bản gốc" thì đọc là biết ngay phải sửa gì.
   *
   * Ảnh gửi lên theo thứ tự CỐ ĐỊNH: [0] ảnh gốc, [1] ảnh AI dựng.
   */
  packaging_check: {
    costKey: 'credit.cost.assist.packaging_check',
    maxInput: 500,
    maxResults: 1,
    nhanAnh: true,
    soAnhToiDa: 2,
    system: [
      'Bạn kiểm tra xem một ảnh sản phẩm do AI dựng lại có còn khớp với sản',
      'phẩm THẬT hay không. Ảnh thứ nhất là sản phẩm thật; ảnh thứ hai là ảnh',
      'AI dựng.',
      'Trả về đúng một mục.',
      'value = "SAFE" khi sản phẩm trong hai ảnh là MỘT: cùng bao bì, cùng',
      'chữ và hình trên nhãn, cùng màu, cùng kiểu dáng, cùng loại đóng gói —',
      'chỉ khác bối cảnh, ánh sáng, góc chụp hoặc nền.',
      'value = "CONCEPT" khi có BẤT KỲ khác biệt nào về chính sản phẩm: nhãn',
      'khác chữ, khác bố cục, khác màu bao bì, khác kiểu bao bì, thêm hoặc bớt',
      'chi tiết, đổi khối lượng ghi trên bao bì.',
      'Không chắc thì chọn CONCEPT — đoán sai theo hướng an toàn.',
      'reason: nói NGẮN GỌN đã khác chỗ nào (tối đa 20 chữ), tiếng Việt.',
      'Nếu là SAFE thì reason nói rõ chỉ đổi gì (ví dụ "chỉ đổi nền và ánh sáng").',
    ].join(' '),
    buildUser: (input) => [
      'Ảnh 1: sản phẩm thật đang bán. Ảnh 2: ảnh do AI dựng.',
      cat(input.note, 500) ? `Ghi chú của người bán: ${cat(input.note, 500)}` : '',
      'Hai ảnh này có phải cùng MỘT sản phẩm để đăng bán không?',
    ].filter(Boolean).join('\n'),
  },

  // --- mini-spec C7 -------------------------------------------------------
  // `packaging_check` so ảnh cảnh với ảnh GỐC. Nó không thấy được chuyện các
  // cảnh lệch NHAU: mỗi cảnh là một lượt gọi độc lập, mô hình không có trí
  // nhớ giữa các lượt, nên góc máy và tỉ lệ sản phẩm có thể trôi mỗi cảnh một
  // kiểu dù cảnh nào cũng khớp ảnh gốc.
  //
  // Đây là lớp CẢNH BÁO, không phải lớp chặn: lệch liên tục là chuyện xem có
  // mượt hay không, còn lệch bao bì mới là chuyện bị sàn phạt. Trộn hai mức
  // đó làm một là dạy người dùng bỏ qua cả hai.
  scene_continuity: {
    costKey: 'credit.cost.assist.scene_continuity',
    maxInput: 400,
    maxResults: 1,
    nhanAnh: true,
    // Một lượt cho CẢ mẻ, không so từng cặp: so cặp thì chi phí nhân theo
    // bình phương số cảnh để đổi lấy một câu trả lời không khác gì mấy.
    soAnhToiDa: 6,
    system: [
      'Bạn xem một loạt ảnh sẽ được ghép liên tiếp thành một video ngắn về',
      'CÙNG MỘT sản phẩm. Việc của bạn là xét chúng có nhìn như một mạch hay',
      'không: cỡ sản phẩm trong khung, góc máy, tông màu, hướng ánh sáng.',
      'KHÔNG xét bối cảnh khác nhau — các cảnh CỐ Ý khác bối cảnh.',
      'KHÔNG xét bao bì đúng hay sai — việc đó đã có bước khác lo.',
      'Trả về đúng một mục.',
      'value = "MUOT" khi các cảnh nhìn như một mạch.',
      'value = "LECH" khi có cảnh trông lạc khỏi phần còn lại.',
      'reason: nếu LECH thì nói rõ ẢNH SỐ MẤY lạc và lạc ở điểm nào',
      '(ví dụ "ảnh 3: sản phẩm nhỏ hơn hẳn và ám vàng"). Tiếng Việt, tối đa',
      '25 chữ. Nếu MUOT thì nói ngắn vì sao nhìn liền mạch.',
    ].join(' '),
    buildUser: (input) => [
      'Các ảnh dưới đây sẽ được ghép liên tiếp theo đúng thứ tự này.',
      cat(input.note, 400) ? `Ghi chú: ${cat(input.note, 400)}` : '',
      'Chúng có nhìn như một mạch không?',
    ].filter(Boolean).join('\n'),
  },

  // Gợi ý kịch bản — CHỈ gợi ý. Không có đường nào tự dán câu này vào video:
  // câu chữ bán hàng là thứ người bán chịu trách nhiệm, không phải mô hình.
  scene_script: {
    costKey: 'credit.cost.assist.scene_script',
    // Gửi kèm ảnh thì mô hình tốn gấp nhiều lần token so với chỉ đọc tên bối
    // cảnh, nên có khoá giá RIÊNG (mini-spec C20). Không thu thêm là để hở
    // biên: người dùng trả một giá, ta trả nhiều giá khác nhau.
    costKeyAnh: 'credit.cost.assist.scene_script.co_anh',
    maxInput: 600,
    maxResults: 6,
    // Ảnh là TUỲ CHỌN ở tác vụ này — khác `packaging_check` (bắt buộc). Xem
    // ảnh cho câu dẫn bám vào thứ thật sự trong khung, nhưng không có ảnh
    // thì vẫn chạy được bằng tên bối cảnh.
    nhanAnh: true,
    soAnhToiDa: 6,
    system: [
      'Bạn viết gợi ý kịch bản cho một video ngắn ghép từ vài ảnh sản phẩm.',
      'Mỗi mục ứng với MỘT cảnh, theo đúng thứ tự được đưa.',
      'Nếu có ảnh kèm theo thì ảnh thứ N là cảnh thứ N — bám vào thứ NHÌN',
      'THẤY trong ảnh, đừng tả những gì không có trong khung.',
      'value = câu dẫn ngắn hiện trên cảnh đó (tối đa 12 chữ, tiếng Việt,',
      'nói về lợi ích hoặc cảm giác, KHÔNG hứa hẹn công dụng chữa bệnh,',
      'KHÔNG dùng từ tuyệt đối như "tốt nhất", "số một").',
      'reason = gợi ý nhịp cho cảnh đó: giữ lâu hay lướt nhanh, và vì sao.',
      'Trả về đúng số mục bằng số cảnh được đưa.',
    ].join(' '),
    buildUser: (input) => {
      const canh = Array.isArray(input.scenes) ? input.scenes.slice(0, 8) : []
      return [
        cat(input.product, 200)
          ? `Sản phẩm: ${cat(input.product, 200)}` : '',
        `Có ${canh.length} cảnh, theo thứ tự:`,
        ...canh.map((c, i) => `${i + 1}. ${cat(String(c), 60)}`),
      ].filter(Boolean).join('\n')
    },
  },

  /**
   * Phân tích cấu trúc video tham khảo thành Flow Blueprint — mini-spec H2
   * (docs/PLAN.md, Phase H mới "Viral Flow Clone & Brand Rewrite").
   *
   * KHÁC HẲN mọi tác vụ ở trên: output là `beats[]` có cấu trúc (timeline +
   * vocabulary đóng), không phải `{results:[{value,reason}]}` — dùng
   * `outputSchema`/`parseResult` riêng (xem `assist()` trong
   * ai-gateway.service.js: hai trường này CHỈ tác vụ này khai, 9 tác vụ còn
   * lại không đổi hành vi).
   *
   * KHÔNG đọc BrandProfile, không sinh kịch bản/ảnh/voice-over — H2 chỉ mô
   * tả CẤU TRÚC của video nguồn. H3 (chưa làm) mới kết hợp với BrandProfile.
   */
  viral_flow_blueprint: {
    costKey: 'credit.cost.assist.viral_flow_blueprint',
    // Trần theo dữ liệu ĐÃ GỘP (client gộp quan sát OCR trùng lặp liên tiếp
    // trước khi gửi — xem `autodub/flow_blueprint.py`), không phải OCR thô.
    maxInput: 8000,
    // Không dùng resultsSchema(maxResults) — outputSchema() ở dưới thay thế.
    outputSchema: () => flowBlueprintOutputSchema(),
    // `input` (đối số 2) là NGUYÊN VĂN dữ liệu route đã gửi — dùng để so
    // khớp sao chép (transcript + OCR text là bằng chứng nguồn cần so).
    parseResult: (data, input) => parseFlowBlueprintResult(data, [
      ...(Array.isArray(input && input.transcript) ? input.transcript.map((d) => d.text) : []),
      ...(Array.isArray(input && input.ocrEvidence) ? input.ocrEvidence.map((o) => o.text) : []),
    ]),
    system: [
      'Bạn phân tích CẤU TRÚC KỂ CHUYỆN của một video ngắn (tối đa 90 giây),',
      'dựa trên bằng chứng ASR (lời nói, có mốc thời gian) và OCR (chữ hiện',
      'trên hình, có mốc thời gian). Mục tiêu là tạo "Flow Blueprint": chia',
      'video thành các đoạn (beat) theo VAI TRÒ KỂ CHUYỆN — hook, mở vấn đề,',
      'bằng chứng, cao trào, lời kêu gọi hành động, v.v.',
      '',
      'QUY TẮC TUYỆT ĐỐI — KHÔNG SAO CHÉP NỘI DUNG NGUỒN:',
      'Bạn PHÂN TÍCH chức năng và nhịp, KHÔNG dịch hay trích dẫn nguyên văn.',
      'KHÔNG được chép lại câu thoại/caption gốc (kể cả một phần dài) vào',
      'bất kỳ trường nào. Mô tả bằng NHẬN XÉT TRỪU TƯỢNG, ví dụ đúng:',
      '"câu cảnh báo ngắn kèm lời hứa lợi ích" — ví dụ SAI: chép lại nguyên',
      'câu thoại đó. Vi phạm quy tắc này khiến toàn bộ kết quả bị huỷ.',
      '',
      'BẰNG CHỨNG CÓ THỂ KHÔNG CHÍNH XÁC:',
      'ASR (chép lời tự động) có thể nghe nhầm. OCR chữ tiếng Việt có thể',
      'MẤT DẤU THANH hoặc sai ký tự dù nhãn "unconfirmed" hay không đi kèm —',
      'coi OCR tiếng Việt là tín hiệu về NHỊP/VỊ TRÍ chữ xuất hiện, không',
      'phải văn bản chính xác. Nếu bằng chứng thiếu/không chắc ở một đoạn,',
      'đặt evidence_status phù hợp cho đoạn đó thay vì bịa nội dung.',
      '',
      'NGUỒN TIẾNG ANH:',
      'Nếu bằng chứng ASR là tiếng Anh: đại từ "you" thường mang nghĩa CHUNG',
      'CHUNG (không chỉ đích danh người xem), câu hay dùng cụm động từ',
      '(phrasal verbs) và lời nói rút gọn — hiểu đúng Ý ĐỊNH giao tiếp rồi mô',
      'tả bằng tiếng Việt tự nhiên, KHÔNG dịch sát từng chữ.',
      '',
      'ĐẦU RA: LUÔN bằng tiếng Việt (kể cả nguồn tiếng Anh), theo đúng',
      'vocabulary beat_type đóng đã cho — không tự bịa loại beat mới. Mỗi',
      'beat có mốc thời gian bắt đầu/kết thúc rõ ràng, không chồng nhau',
      'quá mức. Không nhận xét chung chung kiểu "hook hay" — phải nói RÕ',
      'vai trò kể chuyện, nhịp dựng, và pattern overlay/lời nói ở mức trừu',
      'tượng (ví dụ: "chữ lớn giữa khung, xuất hiện đột ngột" — không phải',
      '"chữ ABC hiện lên").',
    ].join(' '),
    buildUser: (input) => {
      // Trần THEO DÒNG chỉ tránh một dòng bất thường dài — không tự giới
      // hạn TỔNG (video càng dài, ASR/OCR càng nhiều dòng). Trần cứng cuối
      // hàm (`cat(..., maxInput)`) mới là thứ thật sự giữ đúng cam kết
      // `maxInput` khai ở trên, bất kể video dài bao nhiêu.
      const doan = Array.isArray(input.transcript) ? input.transcript.slice(0, 120) : []
      const ocr = Array.isArray(input.ocrEvidence) ? input.ocrEvidence.slice(0, 120) : []
      const ngonNgu = cat(input.languageSourceDetected, 20) || 'không rõ'
      const dong = [
        `Ngôn ngữ nguồn (ASR nhận ra): ${ngonNgu}.`,
        `Chính sách lấy mẫu OCR đã dùng: ${cat(input.samplingPolicyUsed, 200) || 'không rõ'}.`,
        '',
        'BẰNG CHỨNG LỜI NÓI (ASR, có mốc thời gian):',
      ]
      if (!doan.length) {
        dong.push('(không có — ASR không chạy được hoặc video không có lời nói)')
      } else {
        for (const d of doan) {
          dong.push(`[${cat(d.start_s, 10)}s-${cat(d.end_s, 10)}s] ${cat(d.text, 100)}`)
        }
      }
      dong.push('', 'BẰNG CHỨNG CHỮ TRÊN HÌNH (OCR, có mốc thời gian và trạng thái):')
      if (!ocr.length) {
        dong.push('(không có quan sát OCR nào)')
      } else {
        for (const o of ocr) {
          dong.push(`[${cat(o.start_s, 10)}s-${cat(o.end_s, 10)}s, ${cat(o.status, 20)}] `
            + cat(o.text, 80))
        }
      }
      // Trần cứng: giữ đúng cam kết maxInput ở trên dù video dài/nhiều bằng
      // chứng tới đâu — cắt ở CUỐI (mất phần OCR/khung sau, không phải đầu
      // video) là đánh đổi hợp lý vì hook/mở đầu luôn cần đủ bằng chứng nhất.
      // Hằng số lặp lại giá trị `maxInput` khai ở trên (không tham chiếu
      // ngược `TASKS` — object literal chưa xong lúc hàm này được ĐỊNH
      // NGHĨA, dù gọi lúc chạy thì an toàn nhờ closure; lặp lại số cho rõ
      // ràng hơn là dựa vào chi tiết thời điểm đó).
      return cat(dong.join('\n'), 8000)
    },
  },

  /**
   * Đọc NGUYÊN VĂN chữ overlay trên khung hình video — mini-spec H2b
   * (09/09/2026), sinh ra từ khiếu nại thật của chủ dự án: "dịch ra tiếng
   * Việt mà không có dấu".
   *
   * Vì sao một việc tưởng là của OCR lại phải nhờ mô hình nhìn ảnh: bộ OCR
   * chạy trên máy (RapidOCR, model bundled `ch_PP-OCRv4_rec_infer.onnx`) có
   * từ điển đầu ra 6.623 ký tự mà CHỈ 2 ký tự thuộc bộ tiếng Việt có dấu
   * (`É`, `Ó`). Các chữ `ă â đ ê ô ơ ư` và mọi dấu thanh KHÔNG nằm trong từ
   * điển ⇒ model không thể phát ra, dù ảnh nét tới đâu. Đo thật 09/09:
   * "Đăng ký kênh để không bỏ lỡ video mới!" → "Dang ky kenh de khong bo lo
   * video moi", confidence VẪN 0,84-0,99 (sai một cách tự tin — không dùng
   * confidence để phát hiện được). Đây là giới hạn TỪ ĐIỂN, không tham số
   * nào chỉnh được; các từ điển thay thế của PaddleOCR cũng không đủ
   * (`latin_dict` thiếu 102/134 ký tự Việt, `vi_dict` thiếu 66 chữ HOA có
   * dấu). Mô hình nhìn ảnh đọc đúng 100% trên cùng bộ khung hình đó.
   *
   * App KHÔNG gửi mọi khung hình lên đây. Nó chạy OCR cục bộ trước để biết
   * khung nào ĐỔI chữ — việc RapidOCR làm tốt dù đọc mất dấu — rồi chỉ gửi
   * MỘT khung đại diện cho mỗi đoạn chữ khác nhau (video 60 giây: ~152
   * khung lấy mẫu còn ~15 khung gửi đi). Xem `autodub/media/doc_chu_may_chu.py`.
   */
  doc_chu_khung_hinh: {
    costKey: 'credit.cost.assist.doc_chu_khung_hinh',
    maxInput: 200,
    nhanAnh: true,
    // Trần 6 = đúng trần schema của route `/v1/ai/assist`, không phải con số
    // tự nghĩ. Gộp nhiều khung vào MỘT lượt gọi nhanh gấp ~4 lần gọi lẻ (đo
    // thật 09/09: 0,74s/khung khi gộp 4, so với 2,3-5,1s/khung gọi từng cái).
    soAnhToiDa: 6,
    // Khuôn output RIÊNG (như `viral_flow_blueprint`): cần giữ được ánh xạ
    // ảnh↔chữ theo VỊ TRÍ. Khuôn chung `{results:[{value,reason}]}` lọc bỏ
    // mục có `value` rỗng, mà "khung này không có chữ" là câu trả lời HỢP LỆ
    // và thường gặp — lọc mất nó là lệch toàn bộ ánh xạ khung phía sau.
    outputSchema: () => docChuOutputSchema(),
    parseResult: (raw, input) => parseDocChuResult(raw, input),
    system: [
      'Bạn là máy đọc chữ trên ảnh. Việc DUY NHẤT của bạn là chép lại chữ',
      'nhìn thấy trong ảnh, đúng NGUYÊN VĂN.',
      'Giữ NGUYÊN dấu tiếng Việt (ă â đ ê ô ơ ư và mọi dấu thanh) — đây là',
      'yêu cầu quan trọng nhất; chép thiếu dấu bị coi là đọc sai.',
      'KHÔNG dịch sang ngôn ngữ khác. Chữ tiếng Anh thì giữ tiếng Anh, chữ',
      'tiếng Trung thì giữ tiếng Trung.',
      'KHÔNG tóm tắt, KHÔNG diễn giải, KHÔNG sửa lỗi chính tả của chữ gốc.',
      'KHÔNG mô tả cảnh vật, người, hay bất cứ thứ gì không phải chữ.',
      'KHÔNG đoán chữ bị che khuất hay quá mờ — không đọc được thì bỏ qua.',
      'Mỗi dòng chữ trong ảnh là một phần tử của mảng "dong", theo thứ tự từ',
      'trên xuống dưới.',
      'Ảnh thứ N ứng với "anh" = N. Trả về ĐỦ mọi ảnh được đưa, theo đúng thứ tự.',
      'Ảnh không có chữ nào thì vẫn trả về mục của nó với "dong" là mảng rỗng',
      '— đây là câu trả lời hợp lệ, đừng bịa chữ cho đủ.',
    ].join(' '),
    buildUser: (input) => {
      const soAnh = Number(input && input.soAnh) || 0
      return [
        `Có ${soAnh} ảnh, là các khung hình cắt từ một video.`,
        'Chép lại nguyên văn chữ hiển thị trên từng ảnh.',
      ].join('\n')
    },
  },

  /**
   * Viết lại kịch bản cho brand từ Flow Blueprint — mini-spec H3.
   *
   * Đầu vào là **mô tả trừu tượng** (Blueprint chỉ có vai trò kể chuyện từng
   * đoạn, không có câu chữ gốc — H2 đã chặn điều đó bằng mã) cộng hồ sơ
   * brand. Model viết nội dung MỚI, không dịch lại thứ gì.
   *
   * Lời dặn "đừng sao chép" trong prompt là **lớp phòng ĐẦU, không phải lớp
   * chặn**. Bước chặn thật nằm ở `services/kiem-kich-ban.service.js` chạy sau
   * khi có output — vì model "hứa" đã viết khác không có nghĩa nó thực sự
   * khác (luật cứng số 2 của H3).
   */
  brand_script_rewrite: {
    costKey: 'credit.cost.assist.brand_script_rewrite',
    maxInput: 6000,
    outputSchema: () => brandScriptOutputSchema(),
    parseResult: (raw, input) => parseBrandScriptResult(raw, input),
    system: [
      'Bạn là người viết kịch bản video ngắn cho một thương hiệu.',
      'Bạn được cho: (1) bộ khung nhịp kể chuyện của một video tham khảo —',
      'CHỈ là mô tả vai trò từng đoạn, KHÔNG phải lời thoại; và (2) hồ sơ',
      'thương hiệu cần viết cho.',
      'Việc của bạn: viết kịch bản HOÀN TOÀN MỚI cho thương hiệu đó, giữ đúng',
      'số đoạn và đúng vai trò kể chuyện của từng đoạn.',
      'Bộ khung chỉ để học NHỊP. Tuyệt đối KHÔNG diễn đạt lại nó thành câu,',
      'KHÔNG mượn cấu trúc câu đặc trưng của nó, KHÔNG coi nó là văn bản để',
      'dịch lại. Nội dung phải nói về sản phẩm của thương hiệu này.',
      'Bám sát mô tả sản phẩm, đối tượng khách, giọng điệu và USP được cho.',
      'Tránh mọi cụm từ bị cấm được liệt kê — không dùng chúng dù dưới dạng',
      'biến thể.',
      'KHÔNG hứa công dụng chữa bệnh. KHÔNG dùng từ tuyệt đối kiểu "tốt nhất",',
      '"số một" trừ khi hồ sơ thương hiệu cho phép rõ ràng.',
      'Mỗi đoạn trả về ba thứ: loi_doc (lời đọc, tiếng Việt tự nhiên như người',
      'nói, không phải văn viết), caption (chữ overlay ngắn gọn), va',
      'visual_brief (tả BẰNG LỜI cần quay/dựng hình gì — bạn KHÔNG sinh ảnh).',
      'Trả đúng số đoạn được yêu cầu, theo đúng thứ tự.',
    ].join(' '),
    buildUser: (input) => {
      const brand = input?.brand || {}
      const beats = Array.isArray(input?.beats) ? input.beats : []
      const cam = Array.isArray(brand.rangBuocKhongDuocNoi)
        ? brand.rangBuocKhongDuocNoi.filter(Boolean) : []
      const dong = [
        `Thương hiệu: ${cat(brand.tenBrand, 120)}`,
        brand.moTaSanPham ? `Sản phẩm: ${cat(brand.moTaSanPham, 1200)}` : '',
        brand.doiTuongKhach ? `Đối tượng khách: ${cat(brand.doiTuongKhach, 600)}` : '',
        brand.toneGiong ? `Giọng điệu cần giữ: ${cat(brand.toneGiong, 200)}` : '',
        brand.usp ? `Điểm mạnh cần làm nổi bật: ${cat(brand.usp, 600)}` : '',
        cam.length
          ? `TUYỆT ĐỐI KHÔNG được nói (kể cả biến thể):\n${cam.map((c) => `- ${cat(String(c), 200)}`).join('\n')}`
          : '',
        '',
        `Bộ khung nhịp gồm ${beats.length} đoạn, theo thứ tự:`,
        ...beats.map((b, i) => [
          `${i + 1}. [${b?.beatType || 'unknown'}]`,
          b?.narrativeFunctionVi ? `vai trò: ${cat(b.narrativeFunctionVi, 300)}` : '',
          b?.pacingNoteVi ? `nhịp: ${cat(b.pacingNoteVi, 200)}` : '',
        ].filter(Boolean).join(' | ')),
        ...phanVietLai(input),
      ].filter(Boolean)
      return cat(dong.join('\n'), 6000)
    },
  },
}

/**
 * Phần thêm vào lời nhắc khi người dùng bấm "viết lại đoạn N".
 *
 * Không có phần này thì lượt gọi lại có đầu vào **y hệt** lượt trước, và mô
 * hình trả về gần như y hệt — nút "viết lại" trông như hỏng, người dùng bấm
 * mãi và trả tiền mỗi lần. Đưa các đoạn hiện có vào cũng để đoạn viết lại còn
 * ăn khớp với những đoạn đang giữ, thay vì rời rạc.
 */
function phanVietLai(input) {
  const so = Number(input?.vietLaiDoan)
  if (!Number.isInteger(so) || so < 1) return []
  const dangCo = Array.isArray(input?.doanDangCo) ? input.doanDangCo : []
  const ly_do = cat(input?.lyDoVietLai, 200)
  return [
    '',
    `YÊU CẦU LÀM LẠI: viết lại ĐOẠN ${so}.`,
    ly_do ? `Lý do phải làm lại: ${ly_do}` : '',
    'Đoạn mới phải KHÁC HẲN bản cũ về câu chữ, không phải sửa vài từ.',
    'Các đoạn còn lại đang được giữ nguyên, viết sao cho ăn khớp với chúng:',
    ...dangCo.map((d, i) => `${i + 1}. ${cat(String(d || ''), 200)}`),
  ].filter(Boolean)
}

/** Vocabulary đóng của beat_type — dùng chung cho schema VÀ validate. Đồng
 * bộ với `models/FlowBlueprint.js` (nguồn thật của danh sách này) — import
 * lười (require ở nơi dùng) để tránh vòng lặp require lúc nạp module. */
function beatTypes() {
  return require('../models/FlowBlueprint').BEAT_TYPES
}

/** JSON schema cho output của `viral_flow_blueprint` — ép mô hình trả đúng
 * cấu trúc timeline, không phải chuỗi tự do. */
function flowBlueprintOutputSchema() {
  return {
    type: 'object',
    required: ['beats'],
    properties: {
      beats: {
        type: 'array',
        minItems: 1,
        maxItems: 40,
        items: {
          type: 'object',
          required: ['start_s', 'end_s', 'beat_type', 'narrative_function_vi',
            'pacing_note_vi', 'overlay_pattern_abstract_vi', 'spoken_pattern_abstract_vi'],
          properties: {
            start_s: { type: 'number' },
            end_s: { type: 'number' },
            beat_type: { type: 'string', enum: beatTypes() },
            narrative_function_vi: { type: 'string' },
            pacing_note_vi: { type: 'string' },
            overlay_pattern_abstract_vi: { type: 'string' },
            spoken_pattern_abstract_vi: { type: 'string' },
          },
        },
      },
    },
  }
}

/** Số ảnh tối đa một lượt `doc_chu_khung_hinh` — lặp lại `soAnhToiDa` của
 * tác vụ (object literal chưa xong lúc hàm này được ĐỊNH NGHĨA). */
const SO_ANH_DOC_CHU_TOI_DA = 6

/** Trần số đoạn của một kịch bản brand — khớp `maxItems` của `beats` trong
 * `flowBlueprintOutputSchema()`: kịch bản có đúng số đoạn của Blueprint nên
 * không thể dài hơn nguồn. */
const SO_DOAN_KICH_BAN_TOI_DA = 40

/**
 * Giới hạn độ dài từng trường của một đoạn kịch bản, **đọc thẳng từ
 * `models/BrandScript.js`** — MỘT nguồn sự thật duy nhất.
 *
 * Trước đây con số nằm ở hai chỗ (schema Mongoose và bước chuẩn hoá này) và
 * chỉ có một test canh chúng khớp nhau. Nhưng test chỉ báo SAU KHI ai đó đã
 * sửa lệch; đọc thẳng thì không có cách nào lệch được. Nới `maxlength` trong
 * model là chỗ cắt tự đi theo.
 *
 * Nhập lười (require ở trong hàm) để tránh vòng lặp require lúc nạp module —
 * cùng cách `beatTypes()` đang làm với `FlowBlueprint`.
 */
function tranDoDaiBeat() {
  const beatSchema = require('../models/BrandScript').schema.path('beats').schema
  const ra = {}
  for (const ten of ['voiceoverTextVi', 'captionSuggestionVi', 'visualBriefVi']) {
    const max = beatSchema.path(ten).options.maxlength
    if (!max) throw new Error(`models/BrandScript.js: ${ten} thiếu maxlength`)
    ra[ten] = max
  }
  return ra
}

/** JSON schema cho output của `brand_script_rewrite`. */
function brandScriptOutputSchema() {
  return {
    type: 'object',
    required: ['doan'],
    properties: {
      doan: {
        type: 'array',
        minItems: 1,
        maxItems: SO_DOAN_KICH_BAN_TOI_DA,
        items: {
          type: 'object',
          required: ['loi_doc', 'caption', 'visual_brief'],
          properties: {
            loi_doc: { type: 'string' },
            caption: { type: 'string' },
            visual_brief: { type: 'string' },
          },
        },
      },
    },
  }
}

/**
 * Chuẩn hoá output thô của `brand_script_rewrite` sang khuôn camelCase.
 *
 * **Ép đúng số đoạn của Blueprint.** Model trả thiếu hoặc thừa đoạn là kịch
 * bản không còn khớp nhịp nguồn — mà `beatType` của mỗi đoạn lấy từ Blueprint
 * theo VỊ TRÍ, nên lệch một đoạn là mọi đoạn sau đó gắn sai vai trò. Thà báo
 * lỗi để gọi lại còn hơn lưu một kịch bản lệch khung mà không ai biết.
 *
 * Cờ nguyên gốc/tuân thủ **không** đặt ở đây — chúng do
 * `services/kiem-kich-ban.service.js` tính sau, trên chính văn bản này.
 */
function parseBrandScriptResult(raw, input) {
  const doan = raw && Array.isArray(raw.doan) ? raw.doan : null
  if (!doan) return null

  const beatsNguon = Array.isArray(input?.beats) ? input.beats : []
  if (!beatsNguon.length) return null
  if (doan.length !== beatsNguon.length) return null

  // Cắt theo ĐÚNG `maxlength` của `models/BrandScript.js` (đọc thẳng từ đó,
  // không chép lại con số). JSON schema gửi mô hình không chặn độ dài, nên
  // một lượt trả lời dài dòng sẽ làm Mongoose ném lỗi validation lúc lưu —
  // SAU KHI đã trừ Vox: người dùng mất tiền, sổ máy chủ ghi "thành công", app
  // nhận 500 không hiểu nổi (đúng lớp lỗi mà `models/JobResult.js` đã cảnh
  // báo). Cắt ở đây là chỗ rẻ nhất.
  const tran = tranDoDaiBeat()
  const beats = doan.map((d, i) => ({
    beatType: beatsNguon[i]?.beatType || 'unknown',
    voiceoverTextVi: catCung(d?.loi_doc, tran.voiceoverTextVi),
    captionSuggestionVi: catCung(d?.caption, tran.captionSuggestionVi),
    visualBriefVi: catCung(d?.visual_brief, tran.visualBriefVi),
  }))

  // Đoạn rỗng hoàn toàn = model bỏ trống một nhịp. Không lưu, để bên gọi
  // biết mà gọi lại — im lặng nhận là ra một kịch bản thủng giữa chừng.
  if (beats.some((b) => !b.voiceoverTextVi && !b.captionSuggestionVi)) return null

  return { beats }
}

/** JSON schema cho output của `doc_chu_khung_hinh`. Ép mô hình gắn số thứ tự
 * ảnh vào TỪNG mục thay vì tin vào thứ tự mảng: mô hình bỏ sót một ảnh không
 * chữ là mọi ảnh sau đó bị gán nhầm chữ, và không có cách nào phát hiện. */
function docChuOutputSchema() {
  return {
    type: 'object',
    required: ['khung'],
    properties: {
      khung: {
        type: 'array',
        minItems: 1,
        maxItems: SO_ANH_DOC_CHU_TOI_DA,
        items: {
          type: 'object',
          required: ['anh', 'dong'],
          properties: {
            anh: { type: 'integer' },
            dong: { type: 'array', maxItems: 12, items: { type: 'string' } },
          },
        },
      },
    },
  }
}

/**
 * Chuẩn hoá output thô của `doc_chu_khung_hinh`.
 *
 * Trả về đúng khuôn `{ results: [...] }` để route `/v1/ai/assist` dùng lại
 * được y nguyên (route đọc `result.results` như một mảng đục, không ép hình
 * dạng phần tử) — không phải sửa route cho một tác vụ mới.
 *
 * LUÔN trả đủ `soAnh` mục theo đúng thứ tự 1..soAnh: ảnh mô hình không nhắc
 * tới thành `dong: []` ("không có chữ"). Thà nói "khung này không chữ" còn
 * hơn để khuyết một mục rồi bên gọi tự suy ra sai khung.
 */
function parseDocChuResult(raw, input) {
  const khung = raw && Array.isArray(raw.khung) ? raw.khung : null
  if (!khung) return null

  const soAnh = Math.min(
    Math.max(Number(input && input.soAnh) || 0, 0), SO_ANH_DOC_CHU_TOI_DA)
  if (!soAnh) return null

  const theoSo = new Map()
  for (const muc of khung) {
    const so = Number(muc && muc.anh)
    if (!Number.isInteger(so) || so < 1 || so > soAnh) continue
    // Mô hình lặp lại cùng một số ảnh: giữ mục ĐẦU, bỏ các mục sau. Gộp lại
    // thì một lần "ảo giác" lặp sẽ nhân đôi chữ của khung đó.
    if (theoSo.has(so)) continue
    const dong = (Array.isArray(muc.dong) ? muc.dong : [])
      .map((d) => String(d == null ? '' : d).trim())
      .filter(Boolean)
      .slice(0, 12)
    theoSo.set(so, dong)
  }

  const results = []
  for (let i = 1; i <= soAnh; i += 1) {
    results.push({ anh: i, dong: theoSo.get(i) || [] })
  }
  return { results }
}

/**
 * Phép chuẩn hoá dùng cho mọi so khớp chống sao chép. Định nghĩa nằm ở
 * `services/dau-van-tay.service.js` (mini-spec H2c) — MỘT nguồn sự thật duy
 * nhất, vì gate H2 dưới đây và bộ kiểm của H3 phải chuẩn hoá y hệt nhau; hai
 * bản song song là bảo đảm chúng trôi lệch nhau sau vài lần sửa, và lúc đó
 * không ai biết bộ chặn nào mới là bộ đang bảo vệ mình.
 *
 * CẢNH BÁO hành vi (từ khi H2b `doc_chu_khung_hinh` bật): trước đây OCR tiếng
 * Việt MẤT dấu nên một câu có dấu gần như không bao giờ khớp bằng chứng —
 * người ta từng coi đó là "model đang diễn giải, không sao chép". Lý lẽ đó
 * KHÔNG còn đúng: bằng chứng nay có dấu đầy đủ nên bộ chặn nhạy hơn hẳn với
 * tiếng Việt (đúng ý đồ gốc của Guardrail 2/6/7, nhưng là thay đổi thật —
 * một beat chép nguyên văn caption tiếng Việt trước đây LỌT, nay huỷ cả kết
 * quả). Chủ dự án đã chốt GIỮ NGUYÊN mức chặt này (09/09).
 */
const { chuanHoaSoKhop } = require('../services/dau-van-tay.service')

/**
 * Bắt lỗi SAO CHÉP NGUYÊN VĂN: chuỗi N từ liên tiếp trở lên trong text kiểm
 * tra trùng với MỘT chuỗi N từ liên tiếp bất kỳ trong bằng chứng nguồn.
 *
 * Guardrail 2/6/7 của H2: model được PHÂN TÍCH, không được TRÍCH DẪN. Ngưỡng
 * 6 từ đủ dài để không bắt oan các cụm ngắn trùng ngẫu nhiên ("không hứa
 * điều gì"), nhưng đủ nhạy để bắt một câu hook/CTA bị chép nguyên văn.
 */
const NGUONG_TU_LIEN_TIEP = 6

function timNgram(tuList, n) {
  const ra = new Set()
  for (let i = 0; i + n <= tuList.length; i += 1) {
    ra.add(tuList.slice(i, i + n).join(' '))
  }
  return ra
}

//: Caption/hook/CTA thật thường NGẮN hơn hẳn một câu thoại đầy đủ (2-4 từ,
//: vd "STOP SCROLLING", "SHOP NOW") — ngưỡng N-gram 6 từ không bao giờ bắt
//: được ca này vì bản THÂN dòng bằng chứng đã ngắn hơn cả ngưỡng (đo thật
//: khi viết test: bỏ sót hoàn toàn nếu chỉ dùng N-gram). Với dòng bằng
//: chứng NGẮN hơn ngưỡng, chuyển sang kiểm CHỨA NGUYÊN VẸN (substring) thay
//: vì N-gram — nhưng chỉ áp dụng khi dòng đó đủ dài để không phải một chữ
//: chung chung tình cờ trùng (dưới đây: tối thiểu 2 từ).
const TOI_THIEU_TU_DE_KIEM_NGAN = 2

function coSaoChepNguyenVan(vanBanKiemTra, cacNguonBangChung, n = NGUONG_TU_LIEN_TIEP) {
  const kiemTraChuanHoa = chuanHoaSoKhop(vanBanKiemTra)
  const tuKiemTra = kiemTraChuanHoa.split(' ').filter(Boolean)
  if (!tuKiemTra.length) return false
  const ngramKiemTra = tuKiemTra.length >= n ? timNgram(tuKiemTra, n) : null

  for (const nguon of cacNguonBangChung) {
    const nguonChuanHoa = chuanHoaSoKhop(nguon)
    const tuNguon = nguonChuanHoa.split(' ').filter(Boolean)
    if (tuNguon.length >= n) {
      if (!ngramKiemTra) continue   // câu kiểm ngắn hơn ngưỡng thì không có ngram để so
      const ngramNguon = timNgram(tuNguon, n)
      for (const g of ngramKiemTra) {
        if (ngramNguon.has(g)) return true
      }
    } else if (tuNguon.length >= TOI_THIEU_TU_DE_KIEM_NGAN) {
      // Dòng bằng chứng NGẮN (caption/hook/CTA điển hình) — chỉ cần beat
      // CHỨA NGUYÊN VẸN dòng đó là đủ khả nghi, không cần đủ độ dài N-gram.
      if (kiemTraChuanHoa.includes(nguonChuanHoa)) return true
    }
  }
  return false
}

/**
 * Validate + chuẩn hoá output thô của mô hình cho `viral_flow_blueprint`.
 *
 * Trả `null` nếu output không dùng được (khuôn sai, beat rỗng, hoặc PHÁT
 * HIỆN SAO CHÉP NGUYÊN VĂN) — `assist()` coi `null` là lỗi mô hình (502),
 * đúng nguyên tắc "trả sai khuôn là LỖI, không im lặng trả kết quả rỗng"
 * đã áp dụng cho mọi tác vụ khác.
 *
 * ``bangChungNguon``: mảng text bằng chứng (transcript + OCR) — truyền từ
 * `input` gốc để so khớp sao chép. Tách khỏi `parseResult(data)` (chữ ký cố
 * định do `assist()` gọi) bằng closure trong `viral_flow_blueprint.parseResult`
 * phía trên — thấy ở đó `input` được đóng gói sẵn qua `assist()`.
 */
function parseFlowBlueprintResult(data, bangChungNguon) {
  const beats = Array.isArray(data && data.beats) ? data.beats : []
  if (!beats.length) return null

  const cacTruongVanBan = ['narrative_function_vi', 'pacing_note_vi',
    'overlay_pattern_abstract_vi', 'spoken_pattern_abstract_vi']
  const sach = []
  for (const b of beats) {
    if (!b || typeof b !== 'object') continue
    const startS = Number(b.start_s)
    const endS = Number(b.end_s)
    if (!Number.isFinite(startS) || !Number.isFinite(endS) || endS <= startS) continue
    if (!beatTypes().includes(b.beat_type)) continue
    for (const truong of cacTruongVanBan) {
      if (coSaoChepNguyenVan(String(b[truong] || ''), bangChungNguon || [])) {
        return null   // sao chép nguyên văn — huỷ TOÀN BỘ kết quả, không vá riêng beat này
      }
    }
    sach.push({
      startS, endS, beatType: b.beat_type,
      narrativeFunctionVi: String(b.narrative_function_vi || '').trim().slice(0, 500),
      pacingNoteVi: String(b.pacing_note_vi || '').trim().slice(0, 300),
      overlayPatternAbstractVi: String(b.overlay_pattern_abstract_vi || '').trim().slice(0, 300),
      spokenPatternAbstractVi: String(b.spoken_pattern_abstract_vi || '').trim().slice(0, 300),
    })
  }
  if (!sach.length) return null
  return { beats: sach }
}

/** Tên tác vụ hợp lệ — dùng cho schema của route và cho test. */
const TASK_NAMES = Object.keys(TASKS)

function getTask(name) {
  return Object.prototype.hasOwnProperty.call(TASKS, name) ? TASKS[name] : null
}

/**
 * Khoá nhớ đệm theo NỘI DUNG câu hỏi.
 *
 * `jobId` chống gọi trùng do mạng chập chờn, nhưng người dùng bấm lại nút thì
 * `jobId` mới → trả tiền lần nữa cho câu hỏi y hệt. Khoá này băm (tác vụ +
 * phiên bản prompt + dữ liệu vào) nên bấm lại là dùng lại, còn sửa prompt thì
 * nhớ đệm tự hết hiệu lực.
 */
function cacheKey(task, input, images) {
  const crypto = require('node:crypto')
  // Sắp khoá trước khi băm: {a,b} và {b,a} là cùng một câu hỏi.
  const chuan = JSON.stringify(input || {}, Object.keys(input || {}).sort())
  // Ảnh PHẢI nằm trong khoá: đổi ảnh mà khoá không đổi thì lần kiểm sau trả
  // lại kết luận của ảnh cũ — đúng thứ nguy hiểm nhất với một cổng kiểm tra
  // tuân thủ (mini-spec C1).
  const bamAnh = (images || [])
    .map((a) => crypto.createHash('sha1').update(a.data || '').digest('hex').slice(0, 16))
    .join(',')
  const bam = crypto.createHash('sha1')
    .update(`${task}|${PROMPT_VERSION}|${chuan}|${bamAnh}`).digest('hex').slice(0, 32)
  return `assist-cache-${bam}`
}

module.exports = {
  TASKS, TASK_NAMES, getTask, resultsSchema, cat, cacheKey, PROMPT_VERSION,
  // mini-spec H2 — lộ ra để test đơn vị (chống sao chép nguyên văn, schema).
  coSaoChepNguyenVan, parseFlowBlueprintResult, flowBlueprintOutputSchema,
  // mini-spec H2b — đọc chữ overlay bằng mô hình nhìn ảnh.
  docChuOutputSchema, parseDocChuResult, SO_ANH_DOC_CHU_TOI_DA,
  // mini-spec H3 — viết lại kịch bản cho brand.
  brandScriptOutputSchema, parseBrandScriptResult, SO_DOAN_KICH_BAN_TOI_DA,
  tranDoDaiBeat, catCung,
}
