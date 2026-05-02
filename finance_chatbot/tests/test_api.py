"""
test_api.py
===========================================================================
Test cases TC-API-001  →  TC-API-010

Module đang được test : finance_chatbot/main.py  (FastAPI application)

CÁC ENDPOINT ĐƯỢC KIỂM TRA
---------------------------
  POST   /api/init                     → TC-API-001, TC-API-002
  POST   /api/chat                     → TC-API-003, TC-API-004, TC-API-005
  GET    /api/session/{session_id}     → TC-API-006, TC-API-007
  DELETE /api/session/{session_id}     → TC-API-008, TC-API-009
  GET    /api/health                   → TC-API-010

KIẾN TRÚC TEST (không cần container nào đang chạy)
----------------------------------------------------
• Fixture ``test_client`` (từ conftest.py) clear ``main.sessions``
  TRƯỚC và SAU mỗi test → đảm bảo mỗi test bắt đầu từ slate sạch.
• ``FinancialAgent`` được thay bằng ``MockFinancialAgent`` → không có
  cuộc gọi LLM nào được thực hiện, test chạy nhanh và xác định.
• httpx.AsyncClient + ASGITransport → gửi HTTP request trực tiếp vào
  FastAPI app mà không cần server chạy trên port thật.

ROLLBACK / CHIẾN LƯỢC CÔ LẬP
-------------------------------
Vì app lưu state trong ``main.sessions`` (dict Python in-memory, không phải DB),
"CheckDB" ở đây là kiểm tra trực tiếp dict đó sau mỗi mutation.
Mỗi assertion liên quan đến state được đánh dấu ``# CheckDB:``.

IMPORTANT: Cần pytest-anyio để chạy test async.
  pip install pytest-anyio httpx
  Thêm ``asyncio_mode = "auto"`` vào pytest.ini (đã có), HOẶC
  mark module với @pytest.mark.anyio (đã được set toàn cục bên dưới).
===========================================================================
"""

import re
import pytest
import pytest_anyio          # noqa: F401 – cần thiết cho anyio backend
import main as app_module    # import SAU KHI mock được áp dụng trong conftest


# ---------------------------------------------------------------------------
# Đánh dấu mọi coroutine trong module này là anyio test
# anyio cho phép viết async test và chạy chúng với asyncio
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.anyio


# ===========================================================================
# POST /api/init
# Chức năng: Khởi tạo session chatbot mới cho một user.
# Response: { session_id (UUID v4), message, timestamp }
# ===========================================================================

class TestInitSession:

    # TC-API-001 ─────────────────────────────────────────────────────────────
    # Kịch bản happy path: tạo session mới thành công với user_id hợp lệ
    async def test_TC_API_001_valid_request_creates_session_and_returns_uuid(
        self, test_client
    ):
        """
        TC-API-001: POST /api/init với user_id hợp lệ phải:
          1. Trả về HTTP 200
          2. Response có đủ các trường: session_id, message, timestamp
          3. session_id là UUID v4 hợp lệ (format: 8-4-4-4-12 hex)
          4. Session được lưu vào main.sessions (CheckDB)
        """
        payload = {"user_id": "user123"}

        # Gửi POST request để khởi tạo session
        response = await test_client.post("/api/init", json=payload)

        # Kiểm tra HTTP status
        assert response.status_code == 200

        body = response.json()
        # Kiểm tra response có đủ các trường bắt buộc
        assert "session_id" in body
        assert "message" in body
        assert "timestamp" in body

        # Kiểm tra session_id là UUID v4 hợp lệ
        # UUID v4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        # Ký tự thứ 3 của block 3 phải là '4' (version 4)
        # Ký tự đầu của block 4 phải là 8, 9, a, hoặc b (variant bits)
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(body["session_id"]), (
            f"session_id '{body['session_id']}' is not a valid UUID v4"
        )

        # CheckDB: session phải được lưu vào dict in-memory main.sessions
        assert body["session_id"] in app_module.sessions

    # TC-API-002 ─────────────────────────────────────────────────────────────
    # Kiểm tra tính duy nhất của UUID: 2 lần gọi init phải trả về 2 UUID khác nhau
    async def test_TC_API_002_two_sequential_inits_return_distinct_session_ids(
        self, test_client
    ):
        """
        TC-API-002: Hai lần POST /api/init liên tiếp phải trả về hai
        session_id KHÁC NHAU (đảm bảo UUID được tạo ngẫu nhiên, không bị trùng).
        """
        # Tạo 2 session cho 2 user khác nhau
        response_1 = await test_client.post("/api/init", json={"user_id": "userA"})
        response_2 = await test_client.post("/api/init", json={"user_id": "userB"})

        assert response_1.status_code == 200
        assert response_2.status_code == 200

        session_id_1 = response_1.json()["session_id"]
        session_id_2 = response_2.json()["session_id"]

        # Hai session_id phải khác nhau
        assert session_id_1 != session_id_2, (
            "Two init calls returned the same session_id — UUIDs are not unique!"
        )

        # CheckDB: cả 2 session phải được lưu độc lập trong main.sessions
        assert session_id_1 in app_module.sessions
        assert session_id_2 in app_module.sessions


# ===========================================================================
# POST /api/chat
# Chức năng: Gửi tin nhắn tới chatbot trong một session đã tồn tại.
# Session phải được tạo trước (qua /api/init) rồi mới chat được.
# ===========================================================================

class TestChat:

    # Helper: tạo session và trả về session_id
    # Được dùng trong nhiều test để tránh lặp code setup
    async def _create_session(self, client):
        """
        Helper nội bộ: tạo session mới và trả về session_id của nó.
        Dùng để chuẩn bị pre-condition cho các test cần session tồn tại.
        """
        response = await client.post("/api/init", json={"user_id": "chat_tester"})
        assert response.status_code == 200
        return response.json()["session_id"]

    # TC-API-003 ─────────────────────────────────────────────────────────────
    # Kịch bản happy path: chat với session hợp lệ và tin nhắn có nội dung
    async def test_TC_API_003_chat_with_valid_session_and_message_returns_200(
        self, test_client
    ):
        """
        TC-API-003: POST /api/chat với session_id hợp lệ và message không rỗng
        phải:
          1. Trả về HTTP 200
          2. Response có trường 'report' (câu trả lời từ AI)
          3. Response có trường 'answered_subquestions'
          4. Response echoes lại session_id
          5. Lịch sử hội thoại được cập nhật trong session (CheckDB)
        """
        # Bước 1: Tạo session trước (pre-condition)
        session_id = await self._create_session(test_client)

        payload = {
            "session_id": session_id,
            "message"   : "What is my current balance?",  # câu hỏi tài chính
        }

        # Bước 2: Gửi tin nhắn tới chatbot
        response = await test_client.post("/api/chat", json=payload)

        assert response.status_code == 200

        body = response.json()
        # Kiểm tra cấu trúc response: phải có đủ các trường
        assert "report" in body                         # câu trả lời AI
        assert "answered_subquestions" in body          # các câu hỏi phụ đã trả lời
        assert body["session_id"] == session_id         # session_id khớp

        # CheckDB: tin nhắn phải được ghi vào lịch sử hội thoại của session
        stored_session = app_module.sessions[session_id]
        assert len(stored_session["history"]) == 1      # có 1 tin nhắn
        assert stored_session["history"][0]["user_message"] == payload["message"]

    # TC-API-004 ─────────────────────────────────────────────────────────────
    # Kịch bản lỗi: chat với session_id không tồn tại → 404 Not Found
    async def test_TC_API_004_chat_with_unknown_session_id_returns_404(
        self, test_client
    ):
        """
        TC-API-004: POST /api/chat với session_id không tồn tại trong
        ``main.sessions`` phải trả về HTTP 404.

        Đây là trường hợp: user gửi request với session đã hết hạn,
        bị xóa, hoặc session_id bị giả mạo.
        """
        payload = {
            "session_id": "00000000-0000-4000-8000-000000000000",  # UUID hợp lệ nhưng chưa tạo
            "message"   : "Hello",
        }

        response = await test_client.post("/api/chat", json=payload)

        assert response.status_code == 404  # Not Found
        assert "session not found" in response.json()["detail"].lower()

    # TC-API-005 ─────────────────────────────────────────────────────────────
    # Kịch bản lỗi: gửi tin nhắn rỗng hoặc chỉ có khoảng trắng → 400 Bad Request
    async def test_TC_API_005_chat_with_empty_message_returns_400(
        self, test_client
    ):
        """
        TC-API-005: POST /api/chat với message rỗng hoặc chỉ có whitespace
        phải trả về HTTP 400 (guard: ``not request.message.strip()``).

        Tại sao cần guard này?
        - Tin nhắn rỗng không có ý nghĩa để gửi cho LLM.
        - Tránh tốn token/credit của LLM API cho request vô nghĩa.
        - Không ghi vào lịch sử session (CheckDB).
        """
        session_id = await self._create_session(test_client)

        # Gửi message rỗng
        response = await test_client.post(
            "/api/chat",
            json={"session_id": session_id, "message": ""},  # chuỗi rỗng
        )

        assert response.status_code == 400  # Bad Request
        assert "empty" in response.json()["detail"].lower()

        # CheckDB: lịch sử session phải VẪN RỖNG (message không được ghi)
        stored_session = app_module.sessions[session_id]
        assert len(stored_session["history"]) == 0


# ===========================================================================
# GET /api/session/{session_id}
# Chức năng: Lấy thông tin metadata của một session cụ thể.
# Trả về: session_id, created_at, history_count, v.v.
# ===========================================================================

class TestGetSession:

    # TC-API-006 ─────────────────────────────────────────────────────────────
    # Kịch bản happy path: lấy thông tin session đang tồn tại
    async def test_TC_API_006_get_existing_session_returns_200_with_metadata(
        self, test_client
    ):
        """
        TC-API-006: GET /api/session/{session_id} với session đang tồn tại
        phải trả về HTTP 200 cùng metadata của session:
          - session_id (khớp với request)
          - created_at (timestamp tạo session)
          - history_count (số lượng tin nhắn; 0 nếu chưa chat)
        """
        # Tạo session trước
        init_response = await test_client.post("/api/init", json={"user_id": "u1"})
        session_id = init_response.json()["session_id"]

        # Lấy thông tin session
        response = await test_client.get(f"/api/session/{session_id}")

        assert response.status_code == 200
        body = response.json()
        assert body["session_id"] == session_id  # phải khớp
        assert "created_at" in body              # phải có timestamp tạo
        assert "history_count" in body           # phải có số lượng tin nhắn
        assert body["history_count"] == 0        # chưa chat → 0 tin nhắn

    # TC-API-007 ─────────────────────────────────────────────────────────────
    # Kịch bản lỗi: lấy thông tin session không tồn tại → 404
    async def test_TC_API_007_get_non_existent_session_returns_404(
        self, test_client
    ):
        """
        TC-API-007: GET /api/session/{session_id} với session_id không tồn tại
        phải trả về HTTP 404.
        """
        # Dùng ID rõ ràng không hợp lệ để test
        response = await test_client.get("/api/session/invalid-uuid-that-does-not-exist")

        assert response.status_code == 404  # Not Found
        assert "session not found" in response.json()["detail"].lower()


# ===========================================================================
# DELETE /api/session/{session_id}
# Chức năng: Xóa session và giải phóng bộ nhớ.
# Quan trọng: session chứa lịch sử hội thoại và FinancialAgent instance,
# cần xóa để tránh memory leak khi user kết thúc phiên làm việc.
# ===========================================================================

class TestDeleteSession:

    # TC-API-008 ─────────────────────────────────────────────────────────────
    # Kịch bản happy path: xóa session đang tồn tại thành công
    async def test_TC_API_008_delete_existing_session_returns_200(
        self, test_client
    ):
        """
        TC-API-008: DELETE /api/session/{session_id} với session đang tồn tại
        phải:
          1. Trả về HTTP 200 với message xác nhận đã xóa
          2. Xóa session khỏi ``main.sessions`` (CheckDB)
        """
        # Tạo session trước (cần có session để xóa)
        init_response = await test_client.post("/api/init", json={"user_id": "del_user"})
        session_id = init_response.json()["session_id"]

        # Xác nhận pre-condition: session phải tồn tại trước khi xóa
        assert session_id in app_module.sessions

        # Xóa session
        response = await test_client.delete(f"/api/session/{session_id}")

        assert response.status_code == 200
        assert "deleted" in response.json()["message"].lower()

        # CheckDB: session phải không còn trong dict sessions nữa
        assert session_id not in app_module.sessions

    # TC-API-009 ─────────────────────────────────────────────────────────────
    # Kịch bản lỗi: xóa session không tồn tại → 404
    async def test_TC_API_009_delete_non_existent_session_returns_404(
        self, test_client
    ):
        """
        TC-API-009: DELETE /api/session/{session_id} với session_id không tồn tại
        phải trả về HTTP 404.

        Trường hợp này xảy ra khi: session đã bị xóa trước đó, hoặc
        client cố xóa session không thuộc về mình.
        """
        # ID hoàn toàn không tồn tại
        response = await test_client.delete("/api/session/totally-unknown-id")

        assert response.status_code == 404  # Not Found
        assert "session not found" in response.json()["detail"].lower()


# ===========================================================================
# GET /api/health
# Chức năng: Health check endpoint — kiểm tra chatbot service còn hoạt động không.
# Được dùng bởi load balancer, monitoring tools, hoặc Docker health check
# để xác định pod/container có khỏe mạnh không.
# ===========================================================================

class TestHealthCheck:

    # TC-API-010 ─────────────────────────────────────────────────────────────
    # Kiểm tra: health endpoint trả về status "healthy" đúng format
    async def test_TC_API_010_health_check_returns_healthy_status(
        self, test_client
    ):
        """
        TC-API-010: GET /api/health phải trả về HTTP 200 với JSON body:
          - status = "healthy"    : service đang hoạt động bình thường
          - active_sessions       : số session đang có trong bộ nhớ (integer)
          - timestamp             : thời điểm kiểm tra (ISO 8601 format)

        Endpoint này KHÔNG yêu cầu authentication và phải luôn trả về
        nhanh (không phụ thuộc LLM hay DB).
        """
        response = await test_client.get("/api/health")

        assert response.status_code == 200

        body = response.json()
        # Kiểm tra status phải là "healthy" (không phải "degraded" hay "down")
        assert body["status"] == "healthy"
        # active_sessions phải là số nguyên (không phải string hay null)
        assert isinstance(body["active_sessions"], int)
        # timestamp phải tồn tại trong response
        assert "timestamp" in body

        # Xác nhận timestamp là chuỗi ISO 8601 hợp lệ (có thể parse được)
        # Nếu không parse được → pytest.fail() với message rõ ràng
        from datetime import datetime
        try:
            datetime.fromisoformat(body["timestamp"])
        except ValueError:
            pytest.fail(f"timestamp '{body['timestamp']}' is not a valid ISO 8601 string")
