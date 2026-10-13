# Lab 25B — Game Day report

**Họ tên / nhóm:** Võ Huy Hoàng / 2A202602548  
**Commit:** Chưa tạo commit nộp bài  
**Điểm tự động công khai:** 84/88 với seed 25, 26, 27; 4 điểm SLO dữ liệu ẩn chưa thể chấm tại máy này.

Các số dưới đây lấy từ `reports/gameday/`, `reports/cache/`, `reports/workflows.json`, `reports/slo.json` và `reports/experiments.json` với seed 25, trừ khi ghi khác. PASS là theo checks công khai của từng băng; không suy ra kết quả trên băng ẩn.

## 1. Game Day

| Băng | Client | Availability | p95 (s) | Amplification | Retry ratio | Cost/good turn | Recovery (s) | PASS |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| G1 | naive | 0.7194 | 7.157 | 7.738 | 6.738 | 2.163 | 4 | Không |
| G1 | resilient | 1.0000 | 4.780 | 1.063 | 0.001 | 2.104 | 0 | Có |
| G2 | naive | 0.4560 | 15.034 | 9.904 | 8.904 | 4.627 | 155 | Không |
| G2 | resilient | 1.0000 | 10.362 | 1.037 | 0.005 | 2.112 | 0 | Có |
| G3 | naive | 1.0000 | 4.768 | 1.164 | 0.164 | 2.328 | 0 | Không |
| G3 | resilient | 1.0000 | 4.621 | 1.058 | 0.030 | 2.140 | 0 | Có |
| G4 | naive | 1.0000 | 13.764 | 1.004 | 0.004 | 2.008 | 0 | Không |
| G4 | resilient | 1.0000 | 5.626 | 1.014 | 0.002 | 2.072 | 0 | Có |
| G5 | naive | 0.3699 | 5.359 | 17.030 | 16.030 | 2.124 | N/A | Không |
| G5 | resilient | 0.8179 | 5.477 | 1.003 | 0.002 | 2.504 | N/A | Có |
| G6 | naive | 0.5170 | 4.836 | 12.344 | 11.344 | 2.009 | 0 | Không |
| G6 | resilient | 1.0000 | 5.961 | 1.055 | 0.018 | 2.196 | 0 | Có |

Resilient đạt 6/6 trên seed 25 và 6/6 trên từng seed 25–27 của grader công khai. G1 có 0 `retry_after_violations`; G5 có 0 `client_error_retries` và 0 `unneeded_failovers`; G6 có 0 `incompatible_routes`. `recovery_s = N/A` ở G5 vì băng không khai báo thời điểm phục hồi.

## 2. Cấu hình client và quyết định lỗi

| Tham số | Giá trị | Căn cứ |
|---|---:|---|
| `attempt_timeout_s` | 8 s | G6: tăng lên 30 s làm availability giảm 1,0000 → 0,9488; 122 call GiveUp. |
| `max_attempts_per_provider` | 2 | Giới hạn một retry cùng provider; G2 amplification 1,037 so với naive 9,904. |
| `min_time_left_s` | 1 s | Không mở attempt khi deadline 30 s không còn thời gian tối thiểu. |
| `backoff_base_s`, `backoff_cap_s` | 0,25 s; 4 s | Full jitter cho lỗi transient; G1 không vi phạm `retry-after` và amplification 1,063. |
| `retry_budget_ratio`, `min_per_s`, `max_tokens` | 0,1; 0,5/s; 20 | G3 retry ratio 0,030. Khi cố ý tắt breaker, tắt budget khiến G2 amplification tăng 1,378 → 1,580. |
| `quota_cooldown_s` | 300 s | G5 quota của family A cạn; chuyển sang provider khác, availability 0,8179. |
| `breaker.window_size`, `min_calls` | 20; 10 | Chờ đủ mẫu và xét tỷ lệ; G5 lỗi 400 không mở breaker hay gây failover vô ích. |
| `failure_rate_threshold` | 0,5 | G2/G6 mở khi lỗi provider đủ nhiều; G2 recovery 0 s trên chỉ số của băng. |
| `slow_call_s`, `slow_rate_threshold` | 5 s; 0,6 | G4 không có lỗi nhưng p95 hạ từ 13,764 còn 5,626 s. |
| `open_duration_s` | 10 s | Thử phục hồi có kiểm soát; G2 primary share sau hồi phục 1,000. |
| `half_open_max_probes`, `half_open_successes` | 2; 2 | Giới hạn call thử khi HALF_OPEN, chỉ đóng sau hai thành công. |

| Lỗi | Breaker | Hành động |
|---|---|---|
| 400 và lỗi client khác | Release, không ghi lỗi sức khỏe | Dừng call; không retry/failover. |
| 429 `insufficient_quota` | Release | Cooldown dài, chuyển deployment. |
| 429 `rate_limit_exceeded` | Release | Cooldown đến hết `retry_after`, chuyển deployment; chỉ chờ cooldown ngắn nếu không còn nơi phù hợp. |
| 529/503, 5xx khác, timeout | Ghi failure | Retry cùng deployment với jitter khi còn budget và deadline; nếu không thì failover. |

## 3. Ba thí nghiệm đối chứng

Các ablation ở `scripts/run_experiments.py` dùng băng công khai seed 25, không đổi file simulator hay client chính.

1. **Budget khi breaker cấu hình sai.** Với `min_calls=1_000_000_000` và `max_attempts_per_provider=5`, G2 có budget: amplification 1,378, retry ratio 0,058, availability 0,9983, recovery 0 s. Tắt budget: 1,580; 0,378; 0,9754; recovery 24 s. G3 retry ratio tăng từ 0,068 lên 0,158 khi tắt budget. Breaker hoạt động đúng giúp giảm tải sớm, còn budget chặn retry bùng lên nếu breaker chưa trip hoặc bị cấu hình sai; hai cơ chế xử lý rủi ro khác nhau.
2. **Timeout 30 s.** G6 với timeout 8 s đạt availability 1,0000 và 0 GiveUp; timeout 30 s chỉ còn 0,9488 với 107 `deadline` và 15 `no_provider_available`. p95 của lượt *thành công* giảm 5,961 → 5,440 s do lượt treo thất bại bị loại khỏi mẫu p95; không thể đọc riêng p95 để kết luận tốt hơn. G4 hầu như không đổi: availability đều 1,0000, p95 5,626 so với 5,608 s, vì provider vẫn đáp ứng trước timeout. Timeout phải chừa đủ thời gian trong deadline 30 s cho failover, đồng thời đối chiếu p99 bình thường.
3. **Bỏ lọc tool calling.** G6 từ 0 lên 257 `incompatible_routes`; 257 call kết thúc với `incompatible_model_output`, availability từ 1,0000 xuống 0,8922. Với người dùng sản phẩm, đây là 257 yêu cầu cần xử lý bằng công cụ bị gửi đến model không có chức năng đó, nên hệ thống không hoàn thành lượt hỗ trợ dù model dự phòng còn hoạt động.

## 4. Workflow hoàn tiền

| Executor | Completion | Crashes | Refund trùng | Email trùng | Refund mất | Overpaid (cent) | Wasted LLM/crash |
|---|---:|---:|---:|---:|---:|---:|---:|
| naive | 1,000 | 81 | 128 | 81 | 0 | 1.496.700 | 1,123 |
| ours | 1,000 | 66 | 0 | 0 | 0 | 0 | 0,303 |

Idempotency key ổn định ngăn payment/email chạy hai lần sau timeout hoặc crash, nhưng riêng nó không tránh chạy lại các bước đọc và LLM đã xong. Checkpoint giúp resume và giảm tính toán lặp, nhưng riêng nó không ngăn side effect trùng nếu worker chết sau khi payment thành công mà trước khi checkpoint được ghi. Ghi checkpoint *trước* payment còn nguy hiểm hơn: lần resume tưởng đã hoàn tiền và bỏ qua payment, gây mất refund.

## 5. Alerting và error budget

| Sự cố | Mong đợi | Naive | Burn rate | Trễ phát hiện burn rate (phút) |
|---|---|---|---|---:|
| checkout_bug | page | page | page | 27 |
| provider_outage | page | page | page | 4 |
| deploy_blip | none | page sai | không | — |
| slow_leak | ticket | bỏ sót | ticket | 1337 |
| degraded_evening | page | page | page | 291 |
| night_spike | none | page sai | không | — |
| small_bump | none | page sai | không | — |

Trên 25.901.755 request của dữ liệu 30 ngày, budget lỗi là 129.508,8 request; 55.618 lỗi đã tiêu 42,95%, còn 57,05%. Availability là 99,7853%, vì vậy **không freeze release** theo quy tắc hết budget. `small_bump` tồn tại 20 phút với 12% lỗi nhưng không vượt đồng thời ngưỡng cửa sổ dài và ngắn của các luật page; naive đã gây một false page.

## 6. Postmortem G2 — client naive

![G2 attempts và success ratio](gameday/G2_overload_storm.png)

**Tóm tắt.** Trong băng 600 giây, `alpha` mất 75% năng lực từ t=120 đến t=300. Client naive gửi 34.475 attempts cho 3.481 logical calls (amplification 9,904), gây hàng đợi và 429 kéo dài sau khi năng lực provider hồi phục. Chỉ 1.077/2.362 lượt thành công (availability 45,60%) và recovery mất 155 giây kể từ t=300.

**Ảnh hưởng.** Có 1.285 lượt user thất bại; vùng suy giảm bắt đầu sau t=120 và chỉ đạt lại ngưỡng recovery ở khoảng t=455. Nếu giả sử 4 lượt/s suốt 30 ngày và tháng không có lỗi khác, monthly error budget ở SLO 99,5% là 10.368.000 × 0,005 = 51.840 lượt; sự cố này tiêu 1.285/51.840 = **2,48% budget tháng**. Đây là ngoại suy theo tải giả định, không phải số request thực tế của dữ liệu SLI 30 ngày.

**Timeline:** số attempts là tổng 4 deployment trong đúng giây `t`; success là tỷ lệ `calls_ok/calls_done` trong cửa sổ 10 giây kết thúc tại `t`, lấy từ CSV.

| t (s) | Sự kiện | Attempts/s | Success 10 s |
|---:|---|---:|---:|
| 119 | Ngay trước sự cố | 9 | 1,000 |
| 120 | `alpha` mất 75% GPU | 5 | 1,000 |
| 150 | Retry bùng lên | 163 | 0,000 |
| 180 | Hàng đợi và rate limit tiếp diễn | 138 | 0,000 |
| 299 | Cuối khoảng mất GPU | 136 | 0,000 |
| 300 | GPU phục hồi | 115 | 0,000 |
| 330 | Tải giảm nhưng call cũ vẫn thất bại | 6 | 0,000 |
| 420 | Vẫn chưa phục hồi theo SLI | 53 | 0,000 |
| 455 | Mốc recovery theo metric 30 s | 13 | 0,300 |
| 480 | Cửa sổ 10 s đã phục hồi | 8 | 1,000 |

**Trigger và nguyên nhân gốc.** Trigger là mất năng lực GPU trong 180 giây. Nguyên nhân gốc phía client là ba tầng retry chồng nhau, delay cố định, không budget, không breaker và không fallback. Timeout chỉ kết thúc chờ phía client; provider vẫn xử lý attempt cũ. Retry mới chen thêm vào hàng đợi, gây timeout và 429, rồi lại sinh retry. Vì thế t=300 provider có lại GPU nhưng backlog gồm cả công việc user đã bỏ chờ vẫn giữ tải cao: một vòng quá tải tự duy trì.

**Điều giúp và điều làm tệ hơn.** Phục hồi GPU giúp dọn hàng đợi cuối cùng, nhưng không ngăn được 155 giây recovery trễ. Naive vi phạm `retry-after` 28.381 lần và chỉ gửi đến `alpha`, khiến cùng deployment phải gánh toàn bộ lượng retry; resilient có 0 vi phạm, amplification 1,037 và recovery 0 giây trên cùng băng.

| # | Hành động | Loại | Owner | Cách kiểm chứng |
|---|---|---|---|---|
| 1 | Chỉ giữ một tầng retry, thêm jitter, budget và tôn trọng `retry-after` | Prevent | Client/backend | CI chạy G1/G2: `retry_after_violations=0`, G2 amplification ≤1,6. |
| 2 | Theo dõi attempts/call, queue wait, timeout và 429 theo deployment | Detect | SRE/on-call | Alert khi amplification tăng kéo dài; dashboard hiển thị G2 spike 163 attempts/s tại t=150. |
| 3 | Breaker theo lỗi và call chậm, giới hạn probe và failover có kiểm tra tool | Mitigate | Platform AI | CI chạy G2/G4/G6: recovery ≤30 s, G4 p95 ≤10 s, incompatible routes=0. |

Postmortem tập trung vào cơ chế hệ thống và kiểm soát triển khai; không quy trách nhiệm cho cá nhân.

## 7. Điểm yếu còn lại

G2 của resilient vẫn có p95 10,362 s, cao hơn G1 4,780 s, dù availability đạt 100%. Breaker cần đủ mẫu để nhận diện chậm/quá tải nên một số lượt đầu vẫn chờ ở `alpha`; failover qua `beta` có chi phí 1,4/call thay vì 1,0. Bước tiếp theo là thử giới hạn số attempt đang bay theo deployment và ngưỡng latency động, rồi đo đồng thời p95, availability, primary share và cost trên băng ẩn; hiện chưa có bằng chứng để khẳng định sẽ tốt hơn.

## 8. Semantic cache

| Client | Availability | FAQ availability | Hit ratio | Stale served | Wrong | Outdated | Cost/good turn | PASS |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| resilient, không cache | 0,8373 | 0,8424 | 0 | 0 | 0 | 0 | 1,386 | Không |
| cached | 0,9124 | 0,9645 | 0,652 | 157 | 0 | 3 | 0,915 | Có |

| Tham số | Giá trị | Căn cứ |
|---|---:|---|
| `similarity_threshold` | 0,90 | 0,80 cho 175 câu sai do `other_question`; 0,90 cho 0 sai và hit ratio 0,652. |
| `ttl_s` | 60 s | Thay đổi shipping không có webhook: TTL 300 s cho 95 outdated; TTL 60 s còn 3, hit ratio 0,652. |
| `max_stale_s` | 300 s | Phủ sự cố 120 s của mọi provider; 157 stale served, FAQ availability 0,9645. |
| `max_entries` | 500 | Giới hạn bộ nhớ bằng LRU; băng C1 không báo áp lực dung lượng để biện minh giảm thêm. |

**Đối chứng ngưỡng.** 0,80 / 0,90 / 0,97 lần lượt cho hit ratio 0,659 / 0,652 / 0,579, wrong answers 175 / 0 / 0 và cost/good turn 0,978 / 0,915 / 0,965. `other_question` là các câu gần nghĩa vector nhưng khác ý, ví dụ hỏi *chính sách hoàn tiền* so với *thời gian nhận tiền*, hoặc phí ship nội thành so với đi tỉnh. Ngưỡng quá cao làm mất hit hợp lệ, ngưỡng quá thấp ghép nhầm intent.

**Đối chứng TTL.** TTL 30 / 60 / 300 s cho outdated 2 / 3 / 95 và hit ratio 0,592 / 0,652 / 0,731. Webhook ở t=150 chỉ thông báo `policy/refund`; thay đổi `policy/shipping` ở t=480 không có thông báo nên không thể invalidate theo sự kiện. TTL giới hạn khoảng thời gian câu trả lời cũ tiếp tục được xem là fresh.

**Đối chứng stale.** Với `max_stale_s=0`, FAQ availability giảm từ 0,9645 xuống 0,8733 và stale served từ 157 xuống 0. Khi mọi provider sập, chỉ phục vụ stale đã qua kiểm tra scope, tuổi và invalidation; không cache câu hỏi cá nhân. Dù cache theo từng user, trạng thái đơn, refund hoặc điểm vẫn có thể thay đổi ngay sau khi lưu; trả dữ liệu cũ có thể sai hoặc lộ dữ liệu khi định danh/ủy quyền thay đổi. Dashboard cần alert trên **provider error rate, GiveUp, stale served và tuổi cache**, không chỉ availability tổng, vì cache có thể giữ FAQ xanh khi provider đang ngừng hoạt động.
