# Benchmark & Observability Report — Day 14

> Mọi con số được lấy trực tiếp từ report JSON / CSV / screenshot thật.

**Họ tên:** Nguyễn Mạnh Cường (2A202603904)
**Ngày chạy:** 2026-11-26
**Môi trường:** Windows + WSL2 (Ubuntu, Python 3.11) + Docker Desktop

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < `500` ms | Đảm bảo 95% người dùng nhận phản hồi dưới 0.5 giây (trải nghiệm hội thoại mượt mà, tránh chờ đợi lâu). |
| Error rate `/ask` | < `2` % | Cho phép error budget 2% để hấp thụ lỗi ngẫu nhiên từ upstream (`MOCK_ERROR_RATE=0.01`) mà không gây alert fatigue. |
| Accuracy trên golden dataset | ≥ `100` % (sau khi fix KB; gate mặc định ≥ `80`%) | Ngăn regression về chất lượng câu trả lời trước khi merge/deploy lên production. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4.12 | 193.2 | 226.1 | 1698.7 | 0.67% (0.0067) | PASS |
| 10 | 36.30 | 193.8 | 234.6 | 1706.4 | 1.00% (0.0100) | PASS |
| 50 | 77.18 | 254.8 | 1617.2 | 1826.4 | 2.00% (0.0200) | FAIL |
| 100 | 40.49 | 1172.9 | 5299.5 | 5723.0 | 0.67% (0.0067) | FAIL |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

RPS **không tăng tuyến tính** khi concurrency tăng cao: từ `c=1` (`4.12` RPS) lên `c=10` (`36.30` RPS) tăng gần 9x vì server còn dư tài nguyên CPU/event loop; từ `c=10` lên `c=50` tăng chậm lại (`77.18` RPS) và p95 vọt lên `1617.2 ms` (vượt SLO 500ms); đến `c=100` thì **RPS tụt xuống còn `40.49`** và p50/p95 tăng vọt (`1172.9 ms` / `5299.5 ms`) do nghẽn cổ chai ở 1 worker uvicorn local + hàng đợi kết nối (queueing delay).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 201.1 | 238.4 | 306.9 |
| 0.03 (mặc định) | 217.1 | 237.4 | 1701.7 |
| 0.1 | 358.3 | 1687.5 | 1720.7 |

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

**p99** (và tiếp theo là **p95** khi tỉ lệ chậm vượt 5%) nhạy nhất với request chậm: ở `MOCK_SLOW_RATE=0.03`, giá trị `avg` chỉ tăng nhẹ từ `201.1 ms` lên `217.1 ms` và `p95` gần như không đổi (`237.4 ms`), nhưng `p99` đã nhảy vọt lên `1701.7 ms` (~5.5 lần). Khi `MOCK_SLOW_RATE=0.1`, `p95` cũng vọt lên `1687.5 ms` và vi phạm SLO. Do đó, SLO không nên đặt theo `average` vì số trung bình bị các request nhanh kéo xuống, che giấu trải nghiệm tệ của nhóm người dùng gặp tail latency.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.2 | 109.1 | 113.0 |
| Tổng cost (USD) | $0.000405 | $0.000762 | $0.000785 |
| Cost / câu đúng (USD) | $0.00040515 | $0.00003627 | $0.00003413 |
| Quality gate | FAIL | PASS (gate ≥80%) | PASS (gate ≥100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` | `token`, `hết hạn`, `chữ ký` | Bổ sung entry `(["jwt", "json web token"], ...)` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` giải thích JWT có chữ ký số và thời gian hết hạn. |
| `scaling-03` | `cpu`, `memory`, `custom metrics` | Bổ sung entry `(["hpa", "kubernetes"], ...)` vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py` giải thích Kubernetes HPA scale theo CPU, memory hoặc custom metrics. |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

Agent `v2` (có bước retrieval từ `KNOWLEDGE_BASE`) tốn nhiều token hơn (~`113.0` vs `57.2` tokens/câu) và p50 latency nhỉnh hơn một chút (`194.9 ms` vs `162.1 ms`) do chèn thêm context vào prompt và tốn thêm ~20ms bước retrieval. Tuy nhiên, độ chính xác tăng vượt bậc từ `4.3%` lên `100.0%`, khiến **cost / câu đúng** của `v2` (`$0.00003413`) **rẻ hơn ~11.9 lần** so với `v1` (`$0.00040515`).

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals) — `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian) — `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger (có event `exception`) — `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với ít nhất 2 alert đang **firing** — `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

*(Đã bật đồng thời `MOCK_ERROR_RATE=0.2` và `MOCK_SLOW_RATE=0.3` trong thí nghiệm A+B để 2 alert cùng firing trên Prometheus)*

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (`> 5%`, `for: 1m`) | ~1–1.5 phút | Error rate (Golden Signals) & LLM calls ok/error |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (`> 1s`, `for: 2m`) | ~2–2.5 phút | p95 Latency (Golden Signals) & Latency p50/p95/p99 |
| C | `LLM_MODEL=mock-llm-large` | `LLMCostBurnRateHigh` (`> $2/h`, `for: 2m`) | Chưa chạy riêng (theo rule `for: 2m`) | Cost USD/giờ & LLM p95 |
| D | `docker pause` 1 instance | `AgentInstanceDown` (`up == 0`, `for: 30s`) | Chưa chạy riêng (theo rule `for: 30s`) | Instances Up |
| E | `AGENT_VERSION=v1` | Không có alert nào firing | N/A | Retrieval hit ratio giảm về 0, tokens/s giảm |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Alert hạ tầng (error rate, p95, `up`) chỉ đo xem hệ thống **có chạy nhanh và không lỗi HTTP 5xx** hay không, chứ không biết agent trả lời **đúng hay sai**. Để phát hiện sự cố chất lượng (regression khi đổi `AGENT_VERSION=v1`, đổi prompt hoặc model), cần:
1. Chạy **Eval tự động trên golden dataset** (`eval/run_eval.py --min-accuracy 0.8 --baseline ...`) làm **quality gate trong CI/CD** trước khi deploy.
2. Theo dõi các **metric chất lượng/RAG** trên dashboard (như `retrieval hit ratio`, `avg tokens/request`) và thu thập **feedback người dùng** (thumbs up/down) kết hợp đánh giá định kỳ (LLM-as-a-judge) trên traffic thật.

### 4.3 Debug bằng trace

- **Trace chậm trong Jaeger (`screenshots/jaeger-slow-trace.png`):**
  - `trace_id`: `97e33f4d5d36d97d90c4bd8bed8e4234`
  - Tổng thời gian: `1.7 s` (`~1700 ms`)
  - Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (`~1.67 s`, chiếm `~98%` tổng thời gian; trong khi `agent.retrieve_context` chỉ mất `26.7 ms`).
- **Dòng log JSON liên kết `trace_id` (từ `docker compose -p k5-day14-observability logs agent`):**
  - Trace lỗi `trace_id`: `bca7af49dc65afcb4d7b19f1412cdf76`

```json
{"ts": "2026-11-26T19:43:00.074400+00:00", "level": "INFO", "service": "observable-agent", "instance": "57751162c725", "event": "llm_error", "trace_id": "bca7af49dc65afcb4d7b19f1412cdf76", "span_id": "35371e9117487f3c", "request_id": "81e4b7b9309d", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

*(Số liệu lấy từ dòng `Aggregated` trong `scale_1_stats.csv` và `scale_3_stats.csv`)*

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 63.39 | 200 | 820 | 1700 | 76 / 7551 (1.01%) |
| 3 | 66.16 | 190 | 260 | 1700 | 68 / 7879 (0.86%) |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

Scale từ 1 lên 3 instance **cải thiện rất rõ p95** (giảm từ `820 ms` xuống `260 ms`, và p95 của `/health` giảm từ `230 ms` xuống `25 ms`) vì tải 100 users đồng thời được Nginx chia đều cho 3 container thay vì dồn hàng đợi vào 1 process. Tuy nhiên **`p99` vẫn giữ nguyên ở `1700 ms`** vì nút thắt của `p99` nằm ở **tail latency của upstream LLM** (`MOCK_SLOW_RATE=0.03` cộng thêm `1500 ms`), không thể triệt tiêu bằng cách scale thêm instance; đồng thời RPS chỉ tăng nhẹ (`63.39 → 66.16`) do kịch bản Locust có `wait_time = between(0.5, 2)` giới hạn tốc độ gửi từ phía client.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. **Không dùng `average` để đặt SLO latency:** Số trung bình che giấu tail latency (`p99` nhảy vọt 5.5x ở `MOCK_SLOW_RATE=0.03` trong khi `avg` chỉ tăng 16ms); cần đo theo `p95`/`p99`.
  2. **Đánh giá chất lượng bằng `cost / câu đúng` và CI quality gate:** Agent `v2` tốn nhiều token hơn `v1` nhưng accuracy đạt 100% nên `cost / câu đúng` rẻ hơn ~11.9 lần; cần chạy `eval` tự động để chặn regression mà alert hạ tầng không bắt được.
  3. **Liên kết 3 trụ cột Metrics → Traces → Logs:** Prometheus/Grafana phát hiện bất thường (p95/error rate tăng, alert firing), Jaeger khoanh vùng chính xác span chậm (`chat mock-llm-small`), và `trace_id` giúp truy ra đúng dòng log JSON chi tiết.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Thêm **retrieval latency / empty-context rate** để phát hiện sớm vector DB chậm hoặc trả về 0 tài liệu.
  - Thêm **rate limit / cost guard rejection rate** (`429`, `402`) và **synthetic monitoring** (probe từ bên ngoài qua Load Balancer/Nginx để phát hiện lỗi 502/504 mà bản thân container agent không tự ghi nhận được).

