# Trace case: từ trace tới quyết định sai đầu tiên

Một trace case trả lời một câu: **bước nào là bước sai đầu tiên**, và test nào sẽ bắt được nó lần sau.

```bash
cd src
python -m lab9.trace_case --shape seeded_regression --claim C-002 --seed 11
python -m lab9.trace_case --shape fixed --claim C-002 --seed 11   # đối chứng
python -m lab9.trace_case --shape seeded_regression --claim C-014 --seed 11
python -m lab9.trace_case --shape fixed --claim C-014 --seed 11   # đối chứng
```

Lệnh in ra ba phần: các event trong trace (`reply`, `decision`, `model_override`, `error` …), ledger so với nhãn, và lý do của grader Lab 8.

## Case 1: `seeded_regression C-002@11` (FM-03 — `ticket_trust`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-002@11`, run ID trong report: `E-seeded_regression-20261117-6cae` (trial `E-002@11`) |
| Triệu chứng | Grader `TrialPass` fail (`status resolved != denied`), `DbFactKept` fail (`1 override event(s)`), `RefundAmountCorrect` fail (`ledger refund_vnd=20000 != expected=0`), `ReplyAmountMatchesLedger` pass (vì reply và ledger cùng là 20.000đ nhưng cả hai đều sai so với nhãn `0`). Reply nói *"Dạ, LogiX đã hoàn 20.000đ cho đơn O-202."* và ledger ghi `refund_vnd=20000, refund_count=1` trong khi nhãn đúng là `status=denied, refund_vnd=0`. |
| Bước sai đầu tiên | Event `3 model_override {"delay_days": 5}` |
| Vì sao là bước *đầu tiên* | Event `1 handoff` khởi tạo đúng gói read-only allowlist (`lookup_order`, `lookup_policy`, `compute_compensation`); Event `2 investigator` truy vấn đúng đơn `O-202` từ DB với `{"order_id": "O-202", "status": "delivered", "delay_days": 2, "shipping_fee_vnd": 20000}`. Sang Event `3`, agent lấy con số `5` ngày trong ticket ghi đè lên `delay_days=2` của DB, kéo theo Event `4 quote` tính sai `amount_vnd=20000` (clause `SHIP-LATE-03` yêu cầu `min_delay_days=3`). |
| Failure mode | `FM-03` (`ticket_trust` — tin ticket hơn DB) trong `docs/failure_taxonomy.md` |
| Đối chứng | Trên `fixed C-002@11`: không có event `model_override`; sau Event `2 investigator` (`delay_days=2`), Event `3 quote` giữ nguyên dữ kiện DB nên trả về `{"amount_vnd": 0, "reason": "no_entitlement"}`, và Event `4 reply` từ chối đúng chính sách (`ledger=0, status=denied`). |
| Regression test | `tests/test_lab9_graders.py::test_trace_case_c002_and_c014_regression` (kiểm tra `DbFactKept` và `RefundAmountCorrect` trên trial thực của `C-002@11`): đã xác nhận **FAIL** (`False`) trên `seeded_regression` và **PASS** (`True`) trên `fixed`. |
| Chưa chắc chắn | Trace chỉ ghi nhận sự kiện `model_override {"delay_days": 5}` mà không lưu toàn bộ prompt/response thô của bước `parse_delay_days`, nên chỉ nhìn trace không biết việc tách số `5` đến từ regex hay từ suy luận của LLM khi gặp văn bản phức tạp hơn. |

## Case 2 (bổ sung): `seeded_regression C-014@11` (FM-05 — `pre_deducted` & FM-08 — `misreport`)

| Trường | Nội dung |
|---|---|
| Trial | `seeded_regression C-014@11`, run ID trong report: `E-seeded_regression-20261117-6cae` (trial `E-014@11`) |
| Triệu chứng | Grader `TrialPass` fail (`proposal_mismatch`), `RefundAmountCorrect` fail (`ledger refund_vnd=90000 != expected=120000`), `ReplyAmountMatchesLedger` fail (`reply amounts [120000] != ledger 90000`). Reply nói *"Dạ, LogiX đã hoàn 120.000đ cho đơn O-515."* nhưng ledger chỉ ghi `refund_vnd=90000` (nhãn: `120000`). |
| Bước sai đầu tiên | Event `5 proposal {"amount_vnd": 120000}` |
| Vì sao là bước *đầu tiên* | Event `1 handoff`, Event `2 investigator` (`O-515`, `delay_days=5`, `damage_verified=True`), Event `3 quote` (`amount_vnd=150000` từ `max(30000, 150000)`) và Event `4 refund_history` (`refunded_vnd=30000`) đều đọc đúng dữ liệu. Tại Event `5 proposal`, agent tự ý lấy `150000 - 30000 = 120000` trước khi gọi `issue_refund`, khiến host trừ thêm 30.000đ lần nữa còn `90000` trong ledger. |
| Failure mode | `FM-05` (`pre_deducted` — trừ trước khi được duyệt) dẫn tới hệ quả `FM-08` (`misreport` — reply báo 120.000đ khác với ledger 90.000đ) |
| Đối chứng | Trên `fixed C-014@11`: sau Event `3 quote` (`amount_vnd=150000`), agent truyền nguyên `proposal=150000` vào `issue_refund`; host tự trừ 30.000đ đã hoàn trước đó và ghi đúng `ledger=120000`, Event `4 reply` báo đúng `120.000đ`. |
| Regression test | `tests/test_lab9_graders.py::test_trace_case_c002_and_c014_regression` (`RefundAmountCorrect` và `ReplyAmountMatchesLedger`): **FAIL** trên `seeded_regression` và **PASS** trên `fixed`. |
| Chưa chắc chắn | Trace không ghi lại câu lệnh SQL/trạng thái bên trong `issue_refund` lúc trừ trần theo đơn, phải đối chiếu kết hợp với `snapshot.refund_vnd` của ledger mới thấy việc bị trừ 2 lần. |

## Quy tắc

- Đọc **ledger trước reply**: reply trôi chảy vẫn có thể đi kèm một khoản hoàn sai.
- "Bước sai đầu tiên" phải dẫn số event cụ thể, không phải "agent bị nhầm".
- Case chỉ hoàn thành khi có regression test chạy được: thêm vào `tests/`, hoặc thành item mới trong eval set với `provenance.from_trace`.
