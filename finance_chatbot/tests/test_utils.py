"""
test_utils.py
===========================================================================
Test cases TC-UTIL-001  →  TC-UTIL-008

Module đang được test : finance_chatbot/finance_agent/utils.py

CÁC HÀM ĐƯỢC KIỂM TRA
-----------------------
  get_verbosity()      → TC-UTIL-001, TC-UTIL-002, TC-UTIL-003
  get_dependencies()   → TC-UTIL-004, TC-UTIL-005, TC-UTIL-006
  configure_logging()  → TC-UTIL-007, TC-UTIL-008

TẠI SAO KHÔNG CẦN ROLLBACK
-----------------------------
Tất cả ba hàm đều là *pure utility functions* hoặc chỉ cấu hình logging:
  • ``get_verbosity``   – đọc env var, trả về bool. Không có side-effect.
  • ``get_dependencies``– list comprehension thuần túy; không có I/O.
  • ``configure_logging``– áp dụng logging config. Ta kiểm tra level kết quả
    thông qua logging module's inspection API.

Không có database, Redis, hay file-system state nào được tạo ra,
nên không có gì để rollback.

``monkeypatch`` (pytest built-in) tự động hoàn tác mọi thay đổi
``os.environ`` sau khi test kết thúc — đây là "rollback" cho env var.

Tương đương với CheckDB
------------------------
Với pure functions, "check" là assertion trực tiếp trên return value.
Với ``configure_logging``, "check" là kiểm tra effective log level
của logger sau khi gọi hàm.
===========================================================================
"""

import logging
import pytest

# ---------------------------------------------------------------------------
# Setup path để có thể import từ finance_chatbot package
# ---------------------------------------------------------------------------
# Thêm thư mục gốc finance_chatbot vào sys.path để import như app thật,
# tránh phụ thuộc vào cách chạy script (đảm bảo `from finance_agent.utils import ...`
# hoạt động dù chạy từ bất kỳ thư mục nào).
import sys, os
_CHATBOT_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _CHATBOT_ROOT not in sys.path:
    sys.path.insert(0, _CHATBOT_ROOT)

# Import các hàm cần test
from finance_agent.utils import (
    get_verbosity,      # Đọc biến môi trường VERBOSE và trả về bool
    configure_logging,  # Cấu hình log level cho finance_agent loggers
    get_dependencies,   # Lấy danh sách AnsweredSubQuestion mà subquestion hiện tại phụ thuộc vào
)
from finance_agent.models import AnsweredSubQuestion, SubQuestion


# ===========================================================================
# get_verbosity()
# Hàm này đọc biến môi trường VERBOSE và trả về bool:
#   - VERBOSE = 'True'  → True  (case-sensitive: chỉ đúng chữ hoa 'True')
#   - VERBOSE = 'false' → False (khác 'True' → False)
#   - VERBOSE không tồn tại → False
# ===========================================================================

class TestGetVerbosity:
    """Tests cho helper get_verbosity() — đọc VERBOSE env var thành bool."""

    # TC-UTIL-001 ─────────────────────────────────────────────────────────────
    # Kịch bản: VERBOSE='True' (chữ hoa T) → phải trả về True
    def test_TC_UTIL_001_returns_true_when_VERBOSE_is_set_to_True(
        self, monkeypatch
    ):
        """
        TC-UTIL-001: Khi os.environ['VERBOSE'] == 'True', get_verbosity()
        phải trả về exactly ``True`` (so sánh case-sensitive).

        monkeypatch.setenv() tự động hoàn tác thay đổi sau khi test kết thúc,
        đảm bảo test không làm ô nhiễm process environment cho test khác.
        """
        monkeypatch.setenv("VERBOSE", "True")  # monkeypatch tự revert sau test

        result = get_verbosity()

        assert result is True, (
            "get_verbosity() should return True when VERBOSE='True'"
        )

    # TC-UTIL-002 ─────────────────────────────────────────────────────────────
    # Kịch bản: VERBOSE không được set → phải trả về False (default)
    def test_TC_UTIL_002_returns_false_when_VERBOSE_env_var_is_absent(
        self, monkeypatch
    ):
        """
        TC-UTIL-002: Khi env var VERBOSE hoàn toàn không tồn tại,
        get_verbosity() phải trả về ``False`` (giá trị mặc định an toàn).

        Đây là behavior mong muốn trong production: verbose mode phải được
        BẬT chủ động, không phải là mặc định.
        """
        # Xóa hoàn toàn env var (raising=False: không lỗi nếu đã không tồn tại)
        monkeypatch.delenv("VERBOSE", raising=False)

        result = get_verbosity()

        assert result is False, (
            "get_verbosity() should return False when VERBOSE is not set"
        )

    # TC-UTIL-003 ─────────────────────────────────────────────────────────────
    # Kịch bản: VERBOSE='false' (chữ thường) → phải trả về False (case-sensitive)
    def test_TC_UTIL_003_returns_false_when_VERBOSE_is_lowercase_false(
        self, monkeypatch
    ):
        """
        TC-UTIL-003: Khi VERBOSE='false' (lowercase), get_verbosity() phải
        trả về ``False``. So sánh là case-sensitive: chỉ 'True' trả về True.

        Điều này bắt lỗi cấu hình sai phổ biến khi dev set VERBOSE=false
        và mong rằng nó sẽ hoạt động — nhưng không phải vậy.
        """
        monkeypatch.setenv("VERBOSE", "false")  # lowercase: không phải 'True'

        result = get_verbosity()

        assert result is False, (
            "get_verbosity() is case-sensitive: 'false' should return False, not True"
        )


# ===========================================================================
# get_dependencies()
# Hàm này giải quyết dependency graph cho việc trả lời câu hỏi đa bước:
#   - Một SubQuestion có thể phụ thuộc vào kết quả của SubQuestion khác
#     (thông qua trường depends_on: List[int])
#   - get_dependencies() tìm trong danh sách answered_subquestions
#     và trả về những SubQuestion đã được trả lời mà subquestion hiện tại cần
#
# Ví dụ nghiệp vụ:
#   Q1: "Tổng thu nhập tháng này?"
#   Q2: "Tổng chi phí tháng này?"
#   Q3: "Số dư = ? [depends_on: [1, 2]]" → cần Q1 và Q2 đã được trả lời
# ===========================================================================

class TestGetDependencies:
    """Tests cho get_dependencies() — resolver dependency graph câu hỏi."""

    def _make_answered_subquestion(self, subquestion_id: int) -> AnsweredSubQuestion:
        """
        Factory helper: tạo AnsweredSubQuestion tối giản với id cho trước.
        Tránh lặp code setup trong nhiều test methods.

        Note: SubQuestion.id được typed là ``int`` trong models.py.
        """
        subquestion = SubQuestion(
            id       = subquestion_id,
            question = f"Sample question {subquestion_id}",
        )
        return AnsweredSubQuestion(
            subquestion = subquestion,
            answer      = f"Answer for {subquestion_id}",
        )

    # TC-UTIL-004 ─────────────────────────────────────────────────────────────
    # Kịch bản: phụ thuộc vào id=1, id=1 đã được trả lời → trả về [answered_1]
    def test_TC_UTIL_004_returns_correct_dependency_when_it_exists_in_answered_list(self):
        """
        TC-UTIL-004: Khi subquestion depends_on=[1] và subquestion id=1
        đã có trong answered_subquestions, get_dependencies() phải trả về
        chính xác [answered_1] (chỉ dependency được yêu cầu, không thêm gì khác).
        """
        answered_1 = self._make_answered_subquestion(1)  # id=1 đã trả lời
        answered_2 = self._make_answered_subquestion(2)  # id=2 đã trả lời

        # SubQuestion id=3 phụ thuộc VÀO id=1 (không phụ thuộc id=2)
        target_subquestion = SubQuestion(
            id         = 3,
            question   = "Target question",
            depends_on = [1],  # chỉ cần câu trả lời của id=1
        )

        dependencies = get_dependencies(
            answered_subquestions = [answered_1, answered_2],
            subquestion           = target_subquestion,
        )

        # Chỉ answered_1 (id=1) phải được trả về, không phải answered_2
        assert len(dependencies) == 1
        assert dependencies[0].subquestion.id == 1

    # TC-UTIL-005 ─────────────────────────────────────────────────────────────
    # Kịch bản: depends_on=[] (danh sách rỗng) → không có dependency nào
    def test_TC_UTIL_005_returns_empty_list_when_depends_on_is_empty(self):
        """
        TC-UTIL-005: Khi depends_on=[] (câu hỏi độc lập), get_dependencies()
        phải trả về list rỗng [].

        Ví dụ: Q1: "Tổng thu nhập?" không phụ thuộc câu hỏi nào trước
        → có thể trả lời ngay mà không cần chờ câu khác.
        """
        answered_1 = self._make_answered_subquestion(1)

        subquestion_with_no_deps = SubQuestion(
            id         = 10,
            question   = "Independent question",
            depends_on = [],  # rỗng: không có dependency
        )

        dependencies = get_dependencies(
            answered_subquestions = [answered_1],
            subquestion           = subquestion_with_no_deps,
        )

        assert dependencies == []  # list rỗng

    # TC-UTIL-006 ─────────────────────────────────────────────────────────────
    # Kịch bản: depends_on=None (field bị omit) → phải xử lý None gracefully
    def test_TC_UTIL_006_returns_empty_list_when_depends_on_is_None(self):
        """
        TC-UTIL-006: Khi depends_on=None (field không được cung cấp, bị omit),
        get_dependencies() phải trả về list rỗng.

        Test này xác nhận guard ``depends_on or []`` trong implementation
        xử lý đúng khi field là None (không bị NullPointerError hay crash).

        Trường hợp này xảy ra khi LLM tạo SubQuestion và quên set depends_on.
        """
        answered_1 = self._make_answered_subquestion(1)

        subquestion_with_none_deps = SubQuestion(
            id         = 20,
            question   = "Another independent question",
            depends_on = None,  # None: guard ``or []`` phải xử lý được
        )

        dependencies = get_dependencies(
            answered_subquestions = [answered_1],
            subquestion           = subquestion_with_none_deps,
        )

        assert dependencies == []  # None phải được treat như []


# ===========================================================================
# configure_logging()
# Hàm này cấu hình log level cho finance_agent loggers:
#   - verbose=True  → INFO  (hiển thị log trong quá trình development/debug)
#   - verbose=False → CRITICAL (im lặng gần như hoàn toàn trong production,
#                               chỉ log khi có lỗi nghiêm trọng nhất)
# ===========================================================================

class TestConfigureLogging:
    """Tests cho configure_logging() — cấu hình log level của finance_agent."""

    # TC-UTIL-007 ─────────────────────────────────────────────────────────────
    # Kịch bản: verbose=True → logger phải ở mức INFO (level 20)
    def test_TC_UTIL_007_verbose_true_sets_agent_logger_to_INFO(self):
        """
        TC-UTIL-007: Khi verbose=True, logger 'finance_agent.agent' phải được
        set ở mức INFO (numeric value = 20).

        Mức INFO phù hợp cho development: hiển thị thông tin về:
          - Các subquestion được tạo ra
          - Câu trả lời từng bước
          - Thời gian xử lý
        mà không quá verbose như DEBUG.
        """
        configure_logging(verbose=True)

        # Lấy logger theo tên đầy đủ (hierarchy: finance_agent → agent)
        agent_logger = logging.getLogger("finance_agent.agent")

        # getLevel() trả về level được set trực tiếp trên logger này
        # (khác getEffectiveLevel() — không đi lên parent)
        assert agent_logger.level == logging.INFO, (
            f"Expected INFO ({logging.INFO}) but got {agent_logger.level} "
            f"({logging.getLevelName(agent_logger.level)})"
        )

    # TC-UTIL-008 ─────────────────────────────────────────────────────────────
    # Kịch bản: verbose=False → logger phải ở mức CRITICAL (level 50)
    def test_TC_UTIL_008_verbose_false_sets_agent_logger_to_CRITICAL(self):
        """
        TC-UTIL-008: Khi verbose=False, logger 'finance_agent.agent' phải được
        set ở mức CRITICAL (numeric value = 50).

        Mức CRITICAL trong production: gần như im lặng hoàn toàn, chỉ log
        khi có lỗi nghiêm trọng nhất (ứng dụng sắp crash). Điều này tránh
        làm ngập log của server production với thông tin debug không cần thiết.

        Thứ tự các log level (tăng dần theo severity):
          DEBUG (10) < INFO (20) < WARNING (30) < ERROR (40) < CRITICAL (50)
        """
        configure_logging(verbose=False)

        agent_logger = logging.getLogger("finance_agent.agent")
        assert agent_logger.level == logging.CRITICAL, (
            f"Expected CRITICAL ({logging.CRITICAL}) but got {agent_logger.level} "
            f"({logging.getLevelName(agent_logger.level)})"
        )
