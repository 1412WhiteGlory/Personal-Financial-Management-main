"""
conftest.py
===========================================================================
Shared pytest fixtures (cấu hình dùng chung) cho toàn bộ test suite
của finance_chatbot.

CHIẾN LƯỢC ROLLBACK / CÔ LẬP TEST
--------------------------------------
FastAPI app lưu session trong một dict Python thuần túy trong bộ nhớ
(``sessions: Dict[str, dict]`` trong main.py), KHÔNG có database thật.
Vì vậy không cần rollback database. Thay vào đó, ta đảm bảo cô lập bằng:

  1. Tạo một **ASGI test client mới** cho mỗi test function thông qua
     fixture ``test_client`` (scope="function"). Mỗi client bắt đầu với
     dict ``sessions`` rỗng, test trước không thể ảnh hưởng test sau.

  2. ``FinancialAgent`` được mock thông qua ``mock_agent_class`` để không
     có cuộc gọi LLM API thật nào được thực hiện trong khi test.
     → Không tốn token, test chạy nhanh, không phụ thuộc internet.

Tương đương với CheckDB
-----------------------
Vì app dùng dict in-memory thay vì DB, "CheckDB" ở đây có nghĩa là
kiểm tra trực tiếp vào ``main.sessions`` sau khi nhận HTTP response.
===========================================================================
"""

import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Stub thay thế FinancialAgent (LLM thật) trong khi test
# ---------------------------------------------------------------------------

class MockFinancialAgent:
    """
    Stub không làm gì (no-op) thay thế FinancialAgent thật.

    TẠI SAO CẦN MOCK?
    - FinancialAgent thật gọi Google Gemini API → tốn tiền, chậm, cần internet.
    - Test chỉ kiểm tra logic HTTP/routing của FastAPI, không phải chất lượng LLM.
    - Stub này trả về response xác định (deterministic) để assertion rõ ràng.

    Mọi attribute access đều trả về MagicMock, phương thức ``answer``
    trả về response "canned" (đóng hộp sẵn) để test không bao giờ
    chạm tới LLM thật.
    """

    def __init__(self, *args, **kwargs):
        # Mock Gemini model object (test có thể kiểm tra thuộc tính này nếu cần)
        self.gemini = MagicMock()
        self.gemini.model = "mock-model"
        self.tool_callback = None

    def answer(self, message: str, token=None):
        """
        Trả về response giả xác định (deterministic) cho bất kỳ tin nhắn nào.

        Format trả về giống hệt FinancialAgent thật để test có thể
        kiểm tra cấu trúc response mà không cần LLM thật.
        """
        return {
            "report": f"Mock answer for: {message}",  # luôn có trường 'report'
            "answered_subquestions": [
                {"question": message, "answer": "mock answer"}
            ],
        }

    def get_conversation_summary(self):
        """Trả về summary giả — không có lịch sử hội thoại trong test."""
        return {"total_exchanges": 0, "last_exchange_time": None}

    def get_conversation_history(self):
        """Trả về lịch sử rỗng — test bắt đầu từ slate sạch."""
        return []

    def clear_conversation_history(self):
        """No-op — không có gì để xóa trong test."""
        pass


# ---------------------------------------------------------------------------
# Shared fixtures (dùng chung cho tất cả test file trong suite)
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_agent_class():
    """
    Patch (thay thế) ``FinancialAgent`` bằng ``MockFinancialAgent``
    trong suốt thời gian của MỘT test function.

    TẠI SAO PATCH CẢ HAI IMPORT SITE?
    - ``finance_agent.agent.FinancialAgent``: nơi class được định nghĩa
    - ``main.FinancialAgent``: nơi main.py import và dùng class
    Cần patch cả hai để đảm bảo object được tạo trong main.py cũng là mock.

    scope mặc định (function) → patch tự động được gỡ sau mỗi test.
    """
    with patch("finance_agent.agent.FinancialAgent", MockFinancialAgent), \
         patch("main.FinancialAgent", MockFinancialAgent):
        yield MockFinancialAgent


@pytest.fixture
async def test_client(mock_agent_class):
    """
    Cung cấp một AsyncClient mới kết nối với FastAPI ASGI app.

    CÁCH HOẠT ĐỘNG:
    - httpx.AsyncClient với ASGITransport gửi HTTP request trực tiếp vào
      FastAPI app mà KHÔNG cần server thật đang lắng nghe trên bất kỳ port nào.
    - Điều này giống như supertest trong Node.js: test nhanh và cô lập.

    ROLLBACK:
    - ``main.sessions`` được clear() TRƯỚC và SAU mỗi test.
    - "Trước": đảm bảo test bắt đầu từ slate sạch (không có session cũ).
    - "Sau": cleanup session được tạo trong test (phòng ngừa memory leak).

    Nhờ fixture này, mỗi test function có một sessions dict hoàn toàn rỗng
    bất kể thứ tự chạy các test.
    """
    # Import main SAU KHI mock đã được áp dụng (mock_agent_class fixture đã active)
    # Đảm bảo khi main.py được import, FinancialAgent đã là MockFinancialAgent
    import main as app_module

    # ── Pre-test rollback: xóa sạch session còn sót từ lần chạy trước ──────
    app_module.sessions.clear()

    # Tạo transport kết nối client với FastAPI ASGI app (không dùng TCP/IP thật)
    transport = ASGITransport(app=app_module.app)

    # AsyncClient: gửi request bất đồng bộ (async) vào app trong test
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client  # test function nhận được client này

    # ── Post-test rollback: xóa session được tạo trong test này ─────────────
    app_module.sessions.clear()
