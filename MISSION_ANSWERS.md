# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
Trong `01-localhost-vs-production/develop/app.py` có các anti-pattern sau:

1. **Hardcode secrets trong source code (dòng 17–18):**
   - `develop/app.py` gán trực tiếp `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` và `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"`. Nếu push lên GitHub public sẽ bị lộ key và mật khẩu DB ngay lập tức.
   - **Cách `production/` sửa:** Trong `01-localhost-vs-production/production/config.py` (dòng 27, 32), các secret được đọc từ biến môi trường qua `os.getenv("OPENAI_API_KEY", "")` và `os.getenv("AGENT_API_KEY", "")`.
2. **Không quản lý cấu hình qua environment variables (dòng 21–22, 51–53):**
   - `develop/app.py` hardcode `DEBUG = True`, `MAX_TOKENS = 500`, `host="localhost"`, `port=8000`, `reload=True`. `host="localhost"` khiến app không nhận kết nối từ bên ngoài container/server; `port=8000` không tương thích với nền tảng cloud tự inject `PORT`; `reload=True` gây tốn tài nguyên và không an toàn trên production.
   - **Cách `production/` sửa:** `production/config.py` (dòng 17–19, 29) đọc `HOST` (mặc định `0.0.0.0`), `PORT` (mặc định `8000`), `DEBUG` (mặc định `false`) từ env var và truyền vào `uvicorn.run(...)` ở `production/app.py` (dòng 194–199).
3. **Dùng `print()` và log lộ secret (dòng 33–34, 38):**
   - `develop/app.py` dùng `print()` khó thu thập/phân tích trên hệ thống log tập trung, đặc biệt dòng 34 còn in thẳng `OPENAI_API_KEY` ra stdout.
   - **Cách `production/` sửa:** `production/app.py` (dòng 28–32, 111–122) cấu hình `logging` theo chuẩn structured JSON và chỉ log metadata (`question_length`, `client_ip`, `response_length`), tuyệt đối không log secret.
4. **Thiếu health check / readiness endpoint (dòng 42–43):**
   - `develop/app.py` không có `/health` hay `/ready`, nên cloud platform hoặc load balancer không biết container còn sống hay đã sẵn sàng nhận traffic để restart hoặc route traffic.
   - **Cách `production/` sửa:** `production/app.py` (dòng 135–161) bổ sung `GET /health` (liveness probe) và `GET /ready` (readiness probe, trả `503` khi chưa sẵn sàng).
5. **Không xử lý graceful shutdown (dòng 47–54):**
   - `develop/app.py` tắt đột ngột khi nhận tín hiệu dừng, làm đứt ngang các request đang xử lý.
   - **Cách `production/` sửa:** `production/app.py` (dòng 39–68, 180–189) dùng `lifespan` của FastAPI và `signal.signal(signal.SIGTERM, handle_sigterm)` để chuyển `is_ready = False` và chờ request hiện tại hoàn tất trước khi tắt.

### Exercise 1.2: Kết quả chạy bản develop
> Chạy trong `01-localhost-vs-production/develop/` (lưu ý bản develop nhận `question` qua query string):
> ```bash
> pip install -r requirements.txt
> python app.py
> # Terminal khác:
> curl -i -X POST "http://localhost:8000/ask?question=Hello"
> ```

```text
$ curl -X POST "http://localhost:8000/ask?question=Hello"
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log server:
```text
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [9744] using WatchFiles
INFO:     Started server process [14224]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
INFO:     127.0.0.1:51099 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```

### Exercise 1.3: Kết quả chạy bản production & Comparison table

Kết quả kiểm tra bản `01-localhost-vs-production/production/`:
```text
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":311.3,"version":"1.0.0","environment":"development","timestamp":"2026-11-26T08:39:58.579885+00:00"}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d "{\"question\": \"Hello\"}"
HTTP/1.1 200 OK
{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic.","model":"gpt-4o-mini"}
```

| Feature | Develop (Basic) | Production (Advanced) | Why Important? |
|---|---|---|---|
| **Config & Secrets** | Hardcode trực tiếp trong code (`OPENAI_API_KEY`, `host="localhost"`, `port=8000`) | Đọc từ environment variables qua `config.py` (`os.getenv(...)`), `host="0.0.0.0"`, `port` từ `PORT` | Tránh lộ secret lên Git; cùng một code chạy linh hoạt trên mọi môi trường (dev/staging/cloud) theo nguyên tắc 12-Factor. |
| **Health check** | Không có | Có `GET /health` (liveness) và `GET /ready` (readiness, trả 503 khi chưa sẵn sàng) | Giúp cloud platform/load balancer tự phát hiện app bị treo để restart và không đẩy traffic vào instance đang khởi động hoặc đang tắt. |
| **Logging** | `print(...)`, có dòng in cả `OPENAI_API_KEY` | Structured JSON logging (`logging` + `json.dumps`), không log secret | Log JSON dễ parse và tìm kiếm trên các hệ thống như Datadog, Loki; không làm rò rỉ thông tin nhạy cảm. |
| **Shutdown** | Tắt đột ngột khi dừng process | Graceful shutdown bằng FastAPI `lifespan` + handler `SIGTERM` | Đảm bảo các request đang xử lý được hoàn thành trọn vẹn trước khi container dừng, tránh lỗi 502/504 cho người dùng. |
| **Debug / Reload** | Bật cứng `DEBUG = True`, `reload=True` | `reload=settings.debug` (mặc định `false`) | Tránh file watcher tốn CPU/RAM và tránh lộ thông tin debug trên production. |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions
1. **Base image:** `python:3.11` (bản full Python distribution, dung lượng lớn vì chứa sẵn nhiều compiler/system packages).
2. **Working directory:** `/app` (`WORKDIR /app`).
3. **Tại sao `COPY requirements.txt` trước `COPY . .`:** Tận dụng Docker layer cache. Khi chỉ sửa source code (`app.py`) mà không thay đổi `requirements.txt`, Docker dùng lại cache của layer `RUN pip install --no-cache-dir -r requirements.txt` nên rebuild nhanh hơn nhiều.
4. **`CMD` vs `ENTRYPOINT` khác nhau thế nào:** `ENTRYPOINT` cố định chương trình/executable chính khi container chạy (khó bị ghi đè), còn `CMD` chỉ định lệnh mặc định hoặc tham số mặc định truyền vào `ENTRYPOINT` (dễ dàng bị ghi đè khi truyền thêm đối số ở cuối `docker run <image> ...`). Trong `02-docker/develop/Dockerfile` dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Kết quả chạy container develop
```text
$ docker run --rm -d --name cp2-dev -p 8000:8000 my-agent:develop
37465a2bf7bd441559f2e548a6c3484bcc2b39fd6290b5fced4efd4f08db2117

$ curl -i -X POST "http://localhost:8000/ask?question=What+is+Docker"
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 09:20:02 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

### Exercise 2.3: Image size comparison
Kết quả đo bằng `docker images | grep my-agent`:
```text
my-agent:advanced              c10ee91a1e2a        240MB         57.4MB
my-agent:develop               85d9d5d2f06e       1.67GB          426MB
```
- Develop (`my-agent:develop`): `1.67 GB` (`1670 MB`, content size `426 MB`)
- Production (`my-agent:advanced`): `240 MB` (content size `57.4 MB`)
- Difference: giảm **~85.6%** (`(1670 - 240) / 1670 ≈ 85.63%`)
- **Tại sao image nhỏ hơn:** `02-docker/production/Dockerfile` dùng **multi-stage build** (`builder` + `runtime`) trên base `python:3.11-slim`. Stage 1 (`builder`) cài `gcc`, `libpq-dev` và compile packages vào `/root/.local`; Stage 2 (`runtime`) chỉ copy `/root/.local` và source code sang `python:3.11-slim` sạch, loại bỏ hoàn toàn build tools và cache, đồng thời chạy dưới non-root user `appuser`.

### Exercise 2.4: Docker Compose stack
- **Sơ đồ kiến trúc các service (`02-docker/production/docker-compose.yml`):**
  ```text
  Client ──(HTTP :80 / HTTPS :443)──▶ Nginx (reverse proxy / load balancer)
                                          │
                                          ▼ (network: internal)
                                      Agent (FastAPI :8000, target: runtime)
                                       ├──▶ Redis (:6379 — session cache & rate limiting)
                                       └──▶ Qdrant (:6333 — vector database)
  ```
  - Chỉ `nginx` mở port `80` và `443` ra ngoài; `agent`, `redis`, `qdrant` giao tiếp nội bộ qua Docker network `internal` bằng tên service (`redis://redis:6379/0`, `http://qdrant:6333`).
  - `agent` dùng `depends_on` với `condition: service_healthy` để chỉ khởi động khi `redis` và `qdrant` đã healthy.
- **Kết quả test qua Nginx:**
  ```text
  $ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question": "Explain microservices"}'
  HTTP/1.1 200 OK
  Server: nginx
  Date: Thu, 26 Nov 2026 09:25:21 GMT
  Content-Type: application/json
  Content-Length: 126
  Connection: keep-alive
  X-Frame-Options: DENY
  X-Content-Type-Options: nosniff
  X-XSS-Protection: 1; mode=block

  {"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
  ```

---

## Part 3: Cloud Deployment

### Exercise 3.1 / 3.2: Cloud deployment (Agent Part 6)
- URL: 
- So sánh `railway.toml` với `render.yaml`: 

### Exercise 3.3: Cloud Run CI/CD (`cloudbuild.yaml` & `service.yaml`)
- Mô tả pipeline (3–5 dòng): 

---

## Part 4: API Security

### Exercise 4.1–4.3: Test results (401 / 200 / 429)

**Exercise 4.1 (`04-api-gateway/develop` — API Key `X-API-Key`):**
```text
# Không có key -> 401 Unauthorized
$ curl -i -X POST "http://localhost:8000/ask" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 401 Unauthorized
date: Thu, 26 Nov 2026 09:46:21 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# Có key hợp lệ -> 200 OK
$ curl -i -X POST "http://localhost:8000/ask" -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 200 OK
date: Thu, 26 Nov 2026 09:45:32 GMT
server: uvicorn
content-length: 145
content-type: application/json

{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

**Exercise 4.2 & 4.3 (`04-api-gateway/production` — JWT + Rate Limit 429):**
Đăng nhập lấy JWT token qua `POST /auth/token` với tài khoản `student` / `demo123` (giới hạn 10 req/phút, thuật toán Sliding Window Counter trong `rate_limiter.py`), sau đó gọi lặp 12 lần với `Authorization: Bearer <TOKEN_REDACTED>`:
```text
=== Request 1 ===
HTTP/1.1 200 OK
{"usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}, ...}
...
=== Request 10 ===
HTTP/1.1 200 OK
{"usage":{"requests_remaining":0,"budget_remaining_usd":0.000185}, ...}

=== Request 11 ===
HTTP/1.1 429 Too Many Requests
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}

=== Request 12 ===
HTTP/1.1 429 Too Many Requests
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost guard implementation
- **Cách hoạt động (`04-api-gateway/production/cost_guard.py`):**
  - `check_budget(user_id)` kiểm tra **trước khi gọi LLM**:
    - Nếu tổng chi phí toàn hệ thống trong ngày (`_global_cost`) đạt ngưỡng `global_daily_budget_usd` (`$10/ngày`) → trả **`503 Service Unavailable`**.
    - Nếu chi phí trong ngày của user đạt `daily_budget_usd` (`$1/ngày`) → trả **`402 Payment Required`**.
    - Khi đạt `80%` (`warn_at_pct = 0.8`) → ghi `logger.warning`.
  - `record_usage(user_id, input_tokens, output_tokens)` chạy **sau khi gọi LLM xong**, tính chi phí theo giá token (`PRICE_PER_1K_INPUT_TOKENS = 0.00015`, `PRICE_PER_1K_OUTPUT_TOKENS = 0.0006`) và cộng dồn vào usage của user và global.
  - **Trong production (Part 6):** Thay lưu trữ in-memory bằng **Redis** (`budget:{user_id}:{YYYY-MM}` với `INCRBYFLOAT` và `EXPIRE` ~32 ngày) để các instance dùng chung state và không mất dữ liệu khi restart.
  - **Vì sao cần cả Rate Limit và Cost Guard:** Rate limit bảo vệ **tốc độ** (số request/phút, chống spam/DDoS), còn Cost Guard bảo vệ **ngân sách tiền** (vì một câu hỏi dài có thể tốn nhiều token hơn hẳn câu ngắn dù nằm trong rate limit).

---

## Part 5: Scaling & Reliability

### Exercise 5.1–5.5: Implementation notes & test_stateless.py
- **Khác nhau giữa `/health` và `/ready`:**
  - `GET /health` (**Liveness probe**): kiểm tra process của agent còn sống hay không. Luôn trả `200 OK` miễn app còn chạy (kể cả khi Redis tạm mất kết nối, để platform không restart nhầm container gây vòng lặp crash).
  - `GET /ready` (**Readiness probe**): kiểm tra agent đã sẵn sàng nhận traffic chưa (ví dụ kết nối Redis thành công, chưa bước vào trạng thái shutdown). Nếu Redis chết hoặc đang tắt → trả `503 Service Unavailable` để Load Balancer/Nginx ngừng đẩy request mới vào instance đó.
- **Tại sao state trong RAM hỏng khi chạy nhiều instance:**
  - Khi scale lên 3 instance (`--scale agent=3`), Load Balancer (Nginx) phân phối request xoay vòng qua nhiều container khác nhau. Nếu session/conversation history, rate limit hoặc cost budget lưu trong RAM của từng process, request 1 vào `instance A` sẽ không thấy dữ liệu khi request 2 rơi vào `instance B` → mất lịch sử hội thoại, sai bộ đếm rate limit/budget.
  - **Giải pháp:** Lưu toàn bộ state dùng chung (session history, rate limit, budget) vào **Redis** tập trung để mọi instance đều đọc/ghi nhất quán.
- **Kết quả chạy `python3 test_stateless.py` (với `--scale agent=3`):**
  ```text
  Session ID: 974ab900-eafc-4767-b108-bc0c50361c46
  Request 1: [instance-178a6a] -> Request 2: [instance-1ba7ba] -> Request 3: [instance-4bb922]
  Request 4: [instance-178a6a] -> Request 5: [instance-1ba7ba]

  Total requests: 5
  Instances used: {'instance-1ba7ba', 'instance-178a6a', 'instance-4bb922'}
  ✅ All requests served despite different instances!
  Total messages: 10
  ✅ Session history preserved across all instances via Redis!
  ```
  - **Nhận xét:** 5 request đi qua cả 3 instance khác nhau nhưng lịch sử 10 messages (5 user + 5 assistant) vẫn được giữ nguyên vẹn nhờ lưu trong Redis.

---

## Part 6: Checklist Deliverable (`check_production_ready.py`)
```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

---

## AI Log
| Thời điểm / Phần | Đã hỏi AI gì | AI trả lời / gợi ý gì | Tự sửa & tự kiểm tra thế nào |
|---|---|---|---|
| CP1 · Part 1 | Hướng dẫn thực hiện và tổng hợp anti-pattern, bảng so sánh `develop` vs `production` trong `01-localhost-vs-production/` | Chỉ ra 5 anti-pattern kèm số dòng đối chiếu sang `production/app.py`, `production/config.py` và tạo khung `MISSION_ANSWERS.md` | Tự chạy `develop/app.py` và `production/app.py` trong WSL2, kiểm tra `curl` và dán output thực tế |
| CP2 · Part 2 | Giải đáp 4 câu hỏi Dockerfile, so sánh dung lượng multi-stage build | Giải thích `python:3.11`, layer cache, `CMD` vs `ENTRYPOINT` và multi-stage `builder`/`runtime` | Tự build `my-agent:develop` và `my-agent:advanced` bằng Docker, đo `1.67GB` vs `240MB` |
| CP3 · Part 4 | Hướng dẫn test JWT + Rate limit và giải thích Cost Guard (`cost_guard.py`) | Giải thích `check_budget` (402/503), `record_usage`, lưu Redis theo tháng và sự khác nhau giữa Rate limit vs Cost guard | Tự chạy API Key (`401`/`200`), lấy JWT `student`/`demo123` và chạy loop 12 lần thấy `429` |
| CP4 · Part 5 | Giải thích `/health` vs `/ready` và stateless scaling với Redis | Tóm tắt liveness vs readiness probe và lý do state trong RAM hỏng khi chạy nhiều instance | Tự bật 3 replica bằng `docker compose -p k5-day14-scaling up -d --build --scale agent=3` và chạy `test_stateless.py` đạt 10/10 messages qua 3 instance |
| CP5 · Part 6 | Triển khai toàn bộ `TODO` trong `06-lab-complete/` | Viết `config.py`, `redis_client.py`, `auth.py`, `rate_limiter.py`, `cost_guard.py`, `main.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml` | Tự cài Python 3.11 bằng `uv` trong WSL2 và chạy `../.venv/bin/python check_production_ready.py` đạt `PASS 12/12` (41/41 checks, image 238 MB) |

