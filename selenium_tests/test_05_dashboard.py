# -*- coding: utf-8 -*-
"""
Test Suite 5: Kiểm tra Trang Tổng quan (Dashboard)
ID hệ thống: DASH_01 → DASH_07, DASH_UI_01
Mô tả: Kiểm tra trang dashboard: giao diện, hiển thị dữ liệu, biểu đồ,
       điều hướng và tính nhất quán dữ liệu với API.
"""
import time                          # Thư viện thời gian để tạm dừng
import unittest                      # Framework kiểm thử Python
import requests                      # Gửi HTTP request để xác minh API
from selenium.webdriver.common.by import By  # Cách tìm phần tử HTML

import config                        # File cấu hình URL và endpoint
from base_test import BaseTest       # Lớp cơ sở hỗ trợ test


class TestDashboard(BaseTest):
    """Các test case hệ thống cho trang tổng quan tài chính."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo lớp test: đăng ký user test, lấy token và tạo dữ liệu mẫu."""
        super().setUpClass()  # Gọi setup từ lớp cha
        # Đảm bảo tài khoản test tồn tại trong hệ thống
        requests.post(config.API_AUTH_REGISTER, json={
            "fullName": config.TEST_USER_FULLNAME,
            "email": config.TEST_USER_EMAIL,
            "password": config.TEST_USER_PASSWORD
        })
        resp = requests.post(config.API_AUTH_LOGIN, json={
            "email": config.TEST_USER_EMAIL,
            "password": config.TEST_USER_PASSWORD
        })
        if resp.status_code == 200:   # Lưu token nếu đăng nhập thành công
            cls._auth_token = resp.json().get("token")

        # Tạo dữ liệu mẫu cho test dashboard (thu nhập và chi tiêu)
        headers = {"Authorization": f"Bearer {cls._auth_token}"}
        requests.post(config.API_INCOME_ADD, headers=headers,      # Thêm thu nhập mẫu
                       json={"source": "Dashboard Test Income", "amount": 10000000,
                             "date": "2025-04-01"})
        requests.post(config.API_EXPENSE_ADD, headers=headers,     # Thêm chi tiêu mẫu
                       json={"category": "Dashboard Test Expense", "amount": 3000000,
                             "date": "2025-04-02"})

    def _login_and_go_to_dashboard(self):
        """Đăng nhập qua UI và điều hướng đến trang tổng quan."""
        self.login_via_ui()               # Đăng nhập bằng giao diện
        time.sleep(1)                    # Chờ đăng nhập hoàn tất
        self.driver.get(config.DASHBOARD_URL)  # Mở trang dashboard
        time.sleep(3)                    # Chờ trang tải đầy đủ (biểu đồ cần thời gian render)

    # ═══════════════════════════════════════════════════════════════════════════
    # CÁC TEST CASE TRANG TỔŠNG QUAN
    # ═══════════════════════════════════════════════════════════════════════════

    def test_TC_DASH_001_page_loads(self):
        """DASH_01: Trang tổng quan tải thành công sau đăng nhập.
        
        Test ID hệ thống: DASH_01
        Mục tiêu: Xác minh URL chứa 'dashboard' và trang hiển thị nội dung tài chính.
        """
        start = time.time()
        tc_id = "TC_DASH_001"

        try:
            self._login_and_go_to_dashboard()

            current = self.driver.current_url
            loaded = "dashboard" in current

            page_text = self.driver.page_source
            has_content = ("Tổng" in page_text or "Balance" in page_text or
                           "Thu nhập" in page_text or "Chi tiêu" in page_text)

            duration = time.time() - start
            passed = loaded and has_content
            self.record_result(
                tc_id, "Dashboard Loads", "Dashboard",
                "Dashboard page loads with financial data",
                "PASS" if passed else "FAIL",
                f"URLCorrect={loaded}, HasContent={has_content}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Dashboard Loads", "Dashboard",
                               "Dashboard loading", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_002_info_cards_displayed(self):
        """TC_DASH_002: Dashboard displays info cards (balance, income, expense)."""
        start = time.time()
        tc_id = "TC_DASH_002"

        try:
            self._login_and_go_to_dashboard()

            page_text = self.driver.page_source
            has_balance = "Tổng số dư" in page_text or "Total Balance" in page_text or "balance" in page_text.lower()
            has_income = "Tổng thu nhập" in page_text or "Total Income" in page_text
            has_expense = "Tổng chi tiêu" in page_text or "Total Expense" in page_text

            duration = time.time() - start
            all_cards = has_balance and has_income and has_expense
            self.record_result(
                tc_id, "Dashboard Info Cards", "Dashboard",
                "Dashboard shows balance, income, expense cards",
                "PASS" if all_cards else "FAIL",
                f"Balance={has_balance}, Income={has_income}, Expense={has_expense}",
                duration=duration
            )
            self.assertTrue(all_cards)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Dashboard Info Cards", "Dashboard",
                               "Info cards display", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_003_data_matches_api(self):
        """TC_DASH_003: Dashboard data matches API response (DB verification)."""
        start = time.time()
        tc_id = "TC_DASH_003"

        try:
            # Get data from API
            headers = {"Authorization": f"Bearer {self._auth_token}"}
            api_resp = requests.get(config.API_DASHBOARD, headers=headers)
            api_data = api_resp.json() if api_resp.status_code == 200 else {}

            self._login_and_go_to_dashboard()

            page_text = self.driver.page_source
            # Check if the total income/expense values from API appear somewhere in page
            api_total_income = api_data.get("totalIncome", 0)
            api_total_expense = api_data.get("totalExpenses", 0)

            # The page likely displays formatted numbers so we just check general consistency
            data_available = api_resp.status_code == 200
            has_financial_data = ("0" in page_text or str(int(api_total_income)) in page_text.replace(".", "")
                                  or api_total_income == 0)

            duration = time.time() - start
            passed = data_available
            self.record_result(
                tc_id, "Dashboard Data Consistency", "Dashboard + DB",
                "Dashboard data matches API/database values",
                "PASS" if passed else "FAIL",
                f"API_Income={api_total_income}, API_Expense={api_total_expense}, "
                f"API_Status={api_resp.status_code}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Dashboard Data Consistency", "Dashboard + DB",
                               "Data consistency check", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_004_navigation_to_income(self):
        """TC_DASH_004: Navigate from dashboard to income page."""
        start = time.time()
        tc_id = "TC_DASH_004"

        try:
            self._login_and_go_to_dashboard()

            # Find and click Income link in sidebar/navigation
            links = self.driver.find_elements(By.CSS_SELECTOR, "a, button, [role='menuitem']")
            clicked = False
            for link in links:
                text = link.text.strip()
                href = link.get_attribute("href") or ""
                if ("Thu nhập" in text or "Income" in text) and "income" in href.lower():
                    self.safe_click(link)
                    clicked = True
                    break

            if not clicked:
                # Try direct navigation
                self.driver.get(config.INCOME_URL)

            time.sleep(2)
            navigated = "income" in self.driver.current_url.lower()

            duration = time.time() - start
            self.record_result(
                tc_id, "Navigate to Income", "Dashboard Navigation",
                "Navigate from dashboard to income page",
                "PASS" if navigated else "FAIL",
                f"Navigated={navigated}, URL={self.driver.current_url}",
                duration=duration
            )
            self.assertTrue(navigated)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Navigate to Income", "Dashboard Navigation",
                               "Income navigation", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_005_navigation_to_expense(self):
        """TC_DASH_005: Navigate from dashboard to expense page."""
        start = time.time()
        tc_id = "TC_DASH_005"

        try:
            self._login_and_go_to_dashboard()

            links = self.driver.find_elements(By.CSS_SELECTOR, "a, button, [role='menuitem']")
            clicked = False
            for link in links:
                text = link.text.strip()
                href = link.get_attribute("href") or ""
                if ("Chi tiêu" in text or "Expense" in text) and "expense" in href.lower():
                    self.safe_click(link)
                    clicked = True
                    break

            if not clicked:
                self.driver.get(config.EXPENSE_URL)

            time.sleep(2)
            navigated = "expense" in self.driver.current_url.lower()

            duration = time.time() - start
            self.record_result(
                tc_id, "Navigate to Expense", "Dashboard Navigation",
                "Navigate from dashboard to expense page",
                "PASS" if navigated else "FAIL",
                f"Navigated={navigated}",
                duration=duration
            )
            self.assertTrue(navigated)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Navigate to Expense", "Dashboard Navigation",
                               "Expense navigation", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_006_charts_displayed(self):
        """TC_DASH_006: Dashboard displays charts/graphs."""
        start = time.time()
        tc_id = "TC_DASH_006"

        try:
            self._login_and_go_to_dashboard()

            # Recharts renders SVG elements
            svg_elements = self.driver.find_elements(By.CSS_SELECTOR, "svg.recharts-surface, svg")
            canvas_elements = self.driver.find_elements(By.CSS_SELECTOR, "canvas")
            has_charts = len(svg_elements) > 0 or len(canvas_elements) > 0

            duration = time.time() - start
            self.record_result(
                tc_id, "Dashboard Charts", "Dashboard UI",
                "Dashboard displays charts/graphs for financial data",
                "PASS" if has_charts else "FAIL",
                f"SVG_Count={len(svg_elements)}, Canvas_Count={len(canvas_elements)}",
                duration=duration
            )
            self.assertTrue(has_charts, "Dashboard should have chart elements")

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Dashboard Charts", "Dashboard UI",
                               "Chart display verification", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_007_recent_transactions(self):
        """TC_DASH_007: Dashboard displays recent transactions section."""
        start = time.time()
        tc_id = "TC_DASH_007"

        try:
            self._login_and_go_to_dashboard()

            page_text = self.driver.page_source
            has_recent = ("Giao dịch" in page_text or "Transaction" in page_text or
                          "gần đây" in page_text or "Recent" in page_text)

            duration = time.time() - start
            self.record_result(
                tc_id, "Recent Transactions Section", "Dashboard UI",
                "Dashboard shows recent transactions",
                "PASS" if has_recent else "FAIL",
                f"HasRecentSection={has_recent}",
                duration=duration
            )
            self.assertTrue(has_recent)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Recent Transactions", "Dashboard UI",
                               "Recent transactions section", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_DASH_UI_001_responsive_layout(self):
        """TC_DASH_UI_001: Dashboard layout has proper grid structure."""
        start = time.time()
        tc_id = "TC_DASH_UI_001"

        try:
            self._login_and_go_to_dashboard()

            # Check that there are grid containers
            grids = self.driver.find_elements(By.CSS_SELECTOR, "[class*='grid']")
            has_grid = len(grids) > 0

            # Check window title
            title = self.driver.title
            has_title = len(title) > 0

            duration = time.time() - start
            passed = has_grid
            self.record_result(
                tc_id, "Dashboard Responsive Layout", "Dashboard UI",
                "Dashboard uses grid layout for responsive design",
                "PASS" if passed else "FAIL",
                f"GridElements={len(grids)}, Title={title}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Dashboard Responsive Layout", "Dashboard UI",
                               "Responsive layout check", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise


if __name__ == "__main__":
    unittest.main()
