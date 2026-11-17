# Judge audit

Chạy:
```bash
python -m lab9.judge --csv data/eval/judge_tone_public.csv --audit 10
python -m lab9.judge --csv data/eval/judge_helpful_public.csv --audit 10
```

| Tiêu chí | n | κ | Precision | Recall | Confusion (`{tp, fp, fn, tn}`, `FAIL` = positive) | Observed → Corrected Fail Rate | Đạt FLOORS (κ≥0.6, P≥0.8, R≥0.7)? | Quyết định |
|---|---|---|---|---|---|---|---|---|
| `tone_ok` (`judge_tone_public.csv`) | 100 | 0.757 | 0.857 | 0.800 | `{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}` | `0.280 → 0.300` | **ĐẠT** (0.757 ≥ 0.6, 0.857 ≥ 0.8, 0.800 ≥ 0.7) | **Dùng** (theo dõi/phụ trợ sau khi tinh chỉnh rubric) |
| `helpful` (`judge_helpful_public.csv`) | 100 | 0.375 | 1.000 | 0.300 | `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}` | `0.090 → 0.300` | **KHÔNG ĐẠT** (κ=0.375 < 0.6, R=0.300 < 0.7) | **Loại** (cấm dùng làm gate) |

## ≥5 case audit thủ công (tổng 12 case trên cả hai judge)

| # | Case | Judge nói | Người nói | Ai đúng? | Ghi chú & Hành động sửa rubric / hệ thống |
|---|---|---|---|---|---|
| 1 | `H-008` (`tone_ok`): *"Em đã hoàn tiền cho anh rồi nha, anh check giúp em."* | PASS | FAIL | **Người đúng** | Câu trả lời xưng "em" và dùng từ ngữ suồng sã ("nha", "check giúp em"). Judge bị đánh lừa bởi giọng điệu thân thiện. **Hành động sửa rubric:** Quy định rõ chuẩn xưng hô CSKH của LogiX phải dùng *"LogiX"* và *"anh/chị"*, kết thúc bằng *"ạ"*; cấm xưng *"em/bạn"* hoặc dùng khẩu ngữ *"nha/nhé"*. |
| 2 | `H-017` (`tone_ok`): *"Dạ, bạn ơi LogiX đã hoàn 25.000đ cho đơn O-606 rồi nha."* | PASS | FAIL | **Người đúng** | Có từ "Dạ" nhưng gọi khách là "bạn ơi" và dùng "nha", không phù hợp chuẩn mực CSKH với khách hàng lớn tuổi. **Hành động sửa rubric:** Bổ sung danh sách từ cấm xưng hô (*"bạn"*, *"bạn ơi"*, *"cậu"*, *"nha"*) vào rubric của `tone_ok`, kể cả khi đầu câu có *"Dạ"*. |
| 3 | `H-029` (`tone_ok`): *"Dạ, vui lòng chờ. Hệ thống đang xử lý, không cần nhắn thêm."* | PASS | FAIL | **Người đúng** | Mắc lỗi *surface politeness bias*: có chữ "Dạ, vui lòng" ở đầu nhưng vế sau mang giọng mệnh lệnh, đuổi khách (*"không cần nhắn thêm"*). **Hành động sửa rubric:** Yêu cầu judge kiểm tra toàn bộ câu tìm mệnh lệnh cách hoặc câu ngăn cản khách liên hệ, không chỉ dựa vào từ lịch sự ở đầu câu. |
| 4 | `H-042` (`tone_ok`): *"Dạ, đơn O-808 đã hoàn 120.000đ. Tiền về trong 3–5 ngày ạ."* | FAIL | PASS | **Người đúng** | Câu trả lời lịch sự, ngắn gọn, đầy đủ thông tin đơn, số tiền và thời gian nhận tiền. Judge phạt oan (FP) vì không thấy câu xin lỗi dài dòng. **Hành động sửa rubric:** Ghi rõ trong rubric: khi yêu cầu đã được giải quyết (`resolved`), câu trả lời ngắn gọn có *"Dạ ... ạ"* và đủ thông tin là PASS, không bắt buộc phải có câu xin lỗi. |
| 5 | `H-051` (`tone_ok`): *"Dạ, LogiX đã refund 90.000đ cho đơn O-202 ạ."* | FAIL | PASS | **Người đúng** | Judge phạt oan (FP) vì dùng từ tiếng Anh *"refund"*, trong khi quy định CSKH của LogiX cho phép thuật ngữ *"refund"*. **Hành động sửa rubric:** Đưa các thuật ngữ nghiệp vụ được phép (*"refund"*, *"order"*, *"voucher"*) vào allowlist trong rubric để tránh báo lỗi giả. |
| 6 | `H-063` (`tone_ok`): *"Dạ, LogiX đã hoàn 20.000đ và sẽ hoàn thêm cho anh/chị ạ."* | PASS | FAIL | **Người đúng** | Agent tự ý hứa hẹn *"sẽ hoàn thêm"* ngoài kết quả của hệ thống (cam kết tài chính trái phép). **Hành động sửa rubric:** Thêm quy tắc FAIL ngay lập tức nếu reply tự hứa hẹn bồi thường bổ sung ngoài giao dịch đã ghi nhận; đồng thời kết hợp grader code kiểm tra số tiền. |
| 7 | `H-070` (`tone_ok`): *"Dạ, LogiX đã hoàn 90.000đ cho đơn O-909 ạ 😂😂"* | PASS | FAIL | **Người đúng** | Dùng emoji cười (`😂😂`) hoàn toàn lệch ngữ cảnh giải quyết khiếu nại. **Hành động sửa rubric:** Cấm sử dụng emoji đùa cợt trong phản hồi khiếu nại (hoặc bắt bằng regex/code filter trước khi qua judge). |
| 8 | `H-081` (`tone_ok`): *"Dạ, đơn O-107 chưa đủ điều kiện hoàn theo chính sách hiện hành ạ."* | FAIL | PASS | **Judge đúng** (sửa nhãn người) | Ghi chú audit cho thấy người gán nhãn đọc nhầm ticket nên gán sai nhãn; cần rà soát lại quy trình gán nhãn chuẩn (gold label) của con người và cập nhật nhãn đúng trong bộ calibration. |
| 9 | `H-088` (`tone_ok`): *"Dạ, dạ, LogiX đã hoàn 40.000đ cho đơn O-233 ạ."* | FAIL | PASS | **Người đúng** | Lỗi lặp từ nhẹ (*"Dạ, dạ"*) không làm mất tính lịch sự nhưng judge quá khắt khe đánh FAIL. **Hành động sửa rubric:** Phân biệt lỗi chính tả/lặp từ nhẹ (minor typo = vẫn PASS về tone) với lỗi thái độ/xúc phạm (FAIL). |
| 10 | `H-094` (`tone_ok`): *"Da, LogiX da hoan 40.000đ cho don O-341, xin loi vi su bat tien."* | PASS | FAIL | **Người đúng** | Văn bản mất toàn bộ dấu tiếng Việt. **Hành động sửa rubric:** Bổ sung yêu cầu bắt buộc tiếng Việt có dấu chuẩn vào rubric (hoặc dùng hàm kiểm tra tỉ lệ ký tự có dấu bằng code). |
| 11 | `HL-016` (`helpful`): *"Dạ, LogiX thành thật xin lỗi anh/chị... LogiX đã hoàn 55.000đ cho đơn O-404..."* (ledger ghi 35.000đ) | PASS | FAIL | **Người đúng** | **Lỗi nghiêm trọng (FM-08):** Reply báo hoàn 55.000đ trong khi ledger chỉ ghi 35.000đ, kèm câu xin lỗi lặp lại dài dòng (verbosity bias). Judge `helpful` chỉ đọc câu chữ trôi chảy nên chấm PASS. **Hành động:** Không bao giờ dùng LLM judge không có quyền truy cập ledger để chấm tính đúng đắn của số tiền; chuyển sang code grader `ReplyAmountMatchesLedger`. |
| 12 | `HL-047` (`helpful`): *"Ok bạn, đơn O-515 xử lý rồi nhé."* | PASS | FAIL | **Người đúng** | Câu trả lời vừa sai xưng hô (*"Ok bạn... nhé"*), vừa thiếu thông tin cốt lõi (không nêu kết quả hoàn bao nhiêu tiền hay từ chối). **Hành động:** Tách bạch tiêu chí "đủ thông tin kết quả giao dịch" (kiểm bằng code grader dựa trên `status` và `snapshot.refund_vnd`) khỏi tiêu chí văn phong (`tone_ok`). |

## Kết luận
1. **Tiêu chí bị loại (`helpful`) và lý do:**
   - Trên tập calibration (`n = 100`), `judge_helpful` chỉ đạt **κ = 0.375** (< 0.6) và **Recall = 0.300** (< 0.7), với ma trận nhầm lẫn `{'tp': 9, 'fp': 0, 'fn': 21, 'tn': 70}`.
   - Judge bỏ lọt tới **21/30 ca lỗi thực tế (FN = 21)**, làm tỉ lệ lỗi quan sát được chỉ là **9.0%** trong khi tỉ lệ lỗi thực sau hiệu chỉnh Rogan-Gladen là **30.0%**.
   - Nguyên nhân gốc rễ:
     1. **Mù dữ liệu sự thật (Ledger blindness):** 18/21 ca FN (như `HL-015`, `HL-016`, `HL-020`, `HL-028`, `HL-035`, `HL-041`, `HL-043`, `HL-053`, `HL-058`...) là lỗi nói sai số tiền so với ledger (`FM-08`). Judge chỉ nhìn văn bản reply nên không thể biết con số đúng trong database.
     2. **Thiên kiến độ dài & sự lịch sự bề mặt (Verbosity & Politeness bias):** Những câu lặp lại lời xin lỗi sáo rỗng 2 lần liên tiếp nhưng báo sai tiền đều được `judge_helpful` chấm PASS tuyệt đối.
     3. **Định nghĩa "helpful" quá mơ hồ:** Trộn lẫn thái độ xưng hô (`HL-047`, `HL-091`, `HL-097`) với độ chính xác nghiệp vụ.
   - Do đó, **tuyệt đối không dùng `judge_helpful` làm CI gate**. Phần kiểm tra số tiền trong reply phải tách thành code grader (`ReplyAmountMatchesLedger`).
2. **Tiêu chí được giữ (`tone_ok`):**
   - Đạt cả 3 ngưỡng sàn: **κ = 0.757 ≥ 0.6**, **Precision = 0.857 ≥ 0.8**, **Recall = 0.800 ≥ 0.7** (`{'tp': 24, 'fp': 4, 'fn': 6, 'tn': 66}`). Tỉ lệ lỗi quan sát `0.280` gần sát tỉ lệ hiệu chỉnh Rogan-Gladen `0.300`.
   - Tuy nhiên, `tone_ok` chỉ dùng để đánh giá văn phong/thái độ (sau khi cập nhật rubric theo 10 điểm audit trên), không dùng để quyết định tính đúng đắn của tiền và approval.
3. **Rủi ro còn lại:**
   - Judge hiện chỉ được kiểm định trên tập dữ liệu replay đã công khai (`n = 100`). Nếu tinh chỉnh prompt/rubric theo đúng 10 ca bất đồng trên tập này rồi đo lại ngay trên đó thì sẽ bị overfit vào tập calibration. Cần thu thập và gán nhãn người mới trên một tập **held-out độc lập** trước khi đưa judge vào sản xuất.
