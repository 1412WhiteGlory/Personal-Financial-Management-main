# -*- coding: utf-8 -*-
"""
Test Suite 4: Kiểm tra chức năng Quản lý Chi tiêu (Expense Management)
ID hệ thống: EXP_IC_03, EXP_IC_05, EXP_IC_06, EXP_IC_07, EXP_01
             (tương đương Feature_IM nhưng cho mô-đun chi tiêu)
Mô tả: Kiểm tra thêm/xóa chi tiêu qua giao diện UI,
       xác minh dữ liệu trong DB qua API, bao gồm rollback sau test.
"""
import time                          # Thư viện thời gian để tạm dừng thực thi
import unittest                      # Framework kiểm thử đơn vị Python
import requests                      # Gửi HTTP request để xác minh API backend
from selenium.webdriver.common.by import By  # Cách tìm phần tử HTML

import config                        # File cấu hình: URL, tài khoản test, endpoint API
from base_test import BaseTest       # Lớp cơ sở với các phương thức hỗ trợ test


class TestExpense(BaseTest):
    """Các test case hệ thống cho chức năng quản lý chi tiêu (CRUD)."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo lớp test: đảm bảo user test tồn tại và lấy token xác thực."""
        super().setUpClass()  # Gọi setup từ lớp cha
        # Đăng ký tài khoản test (bỏ qua nếu đã tồn tại)
        requests.post(config.API_AUTH_REGISTER, json={
            "fullName": config.TEST_USER_FULLNAME,   # Họ tên người dùng test
            "email": config.TEST_USER_EMAIL,          # Email người dùng test
            "password": config.TEST_USER_PASSWORD     # Mật khẩu người dùng test
        })
        # Đăng nhập để lấy token xác thực cho các request API
        resp = requests.post(config.API_AUTH_LOGIN, json={
            "email": config.TEST_USER_EMAIL,
            "password": config.TEST_USER_PASSWORD
        })
        if resp.status_code == 200:  # Nếu đăng nhập thành công
            cls._auth_token = resp.json().get("token")  # Lưu token

    def _login_and_go_to_expense(self):
        """Đăng nhập qua UI và điều hướng đến trang quản lý chi tiêu."""
        self.login_via_ui()             # Đăng nhập bằng giao diện
        time.sleep(1)                  # Chờ quá trình đăng nhập hoàn tất
        self.driver.get(config.EXPENSE_URL)  # Điều hướng đến trang chi tiêu
        time.sleep(2)                  # Chờ trang tải dữ liệu chi tiêu

    def _open_add_expense_modal(self):
        """Nhấp nút 'Thêm chi tiêu' để mở modal thêm chi tiêu."""
        btns = self.driver.find_elements(By.CSS_SELECTOR, "button")  # Tìm tất cả nút
        for btn in btns:
            text = btn.text.strip()  # Lấy văn bản nút
            if "Thêm chi tiêu" in text:  # Tìm nút mở modal chi tiêu
                self.safe_click(btn)   # Nhấp an toàn
                time.sleep(1.5)        # Chờ modal hiện ra
                return True
        return False  # Không tìm thấy nút

    def _fill_expense_form(self, category="", amount="", date=""):
        time.sleep(1)
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input, textarea")

        cat_filled = False
        amount_filled = False
        date_filled = False

        for inp in inputs:
            placeholder = (inp.get_attribute("placeholder") or "").lower()
            inp_type = inp.get_attribute("type") or ""
            inp_name = (inp.get_attribute("name") or "").lower()

            # Date fields first (most specific)
            if not date_filled and inp_type == "date":
                if date:
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                        inp, date
                    )
                date_filled = True
            # Amount: placeholder 'Nhập số tiền' or type number
            elif not amount_filled and (
                "nhập số tiền" in placeholder or "amount" in placeholder
                or inp_type == "number" or "amount" in inp_name
            ):
                if amount:
                    self.clear_and_type(inp, str(amount))
                amount_filled = True
            # Category: any remaining text input
            elif not cat_filled and inp_type == "text":
                if category:
                    self.clear_and_type(inp, category)
                cat_filled = True

        return cat_filled, amount_filled, date_filled

    def _submit_expense_form(self):
        """Click the 'Add Expense' submit button inside the expense modal."""
        btns = self.driver.find_elements(By.CSS_SELECTOR, "button")
        for btn in btns:
            text = btn.text.strip()
            # Exact match for the modal submit button
            if text == "Add Expense" or text == "Lưu" or text == "Save":
                self.scroll_to_element(btn)
                time.sleep(0.3)
                self.safe_click(btn)
                time.sleep(3)
                return True
        return False

    def _get_expense_count_from_api(self):
        resp = requests.get(config.API_EXPENSE_GET,
                            headers={"Authorization": f"Bearer {self._auth_token}"})
        if resp.status_code == 200:
            return len(resp.json())
        return -1

    # ═══════════════════════════════════════════════════════════
    # TEST CASES
    # ═══════════════════════════════════════════════════════════

    def test_TC_EXP_001_add_food_expense(self):
        """TC_EXP_001: Add food expense with valid data."""
        start = time.time()
        tc_id = "TC_EXP_001"
        test_data = self.load_csv("test_expense.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_expense_count_from_api()
            self._login_and_go_to_expense()
            self._open_add_expense_modal()
            self._fill_expense_form(row["category"], row["amount"], row["date"])
            self._submit_expense_form()
            time.sleep(2)

            count_after = self._get_expense_count_from_api()
            db_added = count_after > count_before

            if db_added:
                expenses = requests.get(config.API_EXPENSE_GET,
                                        headers={"Authorization": f"Bearer {self._auth_token}"}).json()
                if expenses:
                    self.register_rollback(
                        lambda eid=expenses[0]["_id"]: requests.delete(
                            f"{config.API_BASE_URL}/api/v1/expense/{eid}",
                            headers={"Authorization": f"Bearer {self._auth_token}"}
                        )
                    )

            duration = time.time() - start
            self.record_result(tc_id, "Add Food Expense", "Expense",
                               row["description"], "PASS" if db_added else "FAIL",
                               f"CountBefore={count_before}, CountAfter={count_after}",
                               duration=duration)
            self.assertTrue(db_added)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Add Food Expense", "Expense",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_EXP_002_add_transport_expense(self):
        """TC_EXP_002: Add transportation expense."""
        start = time.time()
        tc_id = "TC_EXP_002"
        test_data = self.load_csv("test_expense.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_expense_count_from_api()
            self._login_and_go_to_expense()
            self._open_add_expense_modal()
            self._fill_expense_form(row["category"], row["amount"], row["date"])
            self._submit_expense_form()
            time.sleep(2)

            count_after = self._get_expense_count_from_api()
            db_added = count_after > count_before

            if db_added:
                expenses = requests.get(config.API_EXPENSE_GET,
                                        headers={"Authorization": f"Bearer {self._auth_token}"}).json()
                if expenses:
                    self.register_rollback(
                        lambda eid=expenses[0]["_id"]: requests.delete(
                            f"{config.API_BASE_URL}/api/v1/expense/{eid}",
                            headers={"Authorization": f"Bearer {self._auth_token}"}
                        )
                    )

            duration = time.time() - start
            self.record_result(tc_id, "Add Transportation Expense", "Expense",
                               row["description"], "PASS" if db_added else "FAIL",
                               f"CountBefore={count_before}, CountAfter={count_after}",
                               duration=duration)
            self.assertTrue(db_added)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Add Transportation Expense", "Expense",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_EXP_005_missing_category(self):
        """TC_EXP_005: Add expense without category should fail."""
        start = time.time()
        tc_id = "TC_EXP_005"
        test_data = self.load_csv("test_expense.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_expense_count_from_api()
            self._login_and_go_to_expense()
            self._open_add_expense_modal()
            self._fill_expense_form("", row["amount"], row["date"])
            self._submit_expense_form()
            time.sleep(2)

            count_after = self._get_expense_count_from_api()
            not_added = count_after == count_before

            page_text = self.driver.page_source.lower()
            has_error = ("bắt buộc" in page_text or "required" in page_text
                         or "danh mục" in page_text)

            duration = time.time() - start
            passed = not_added or has_error
            self.record_result(tc_id, "Missing Category Expense", "Expense",
                               row["description"], "PASS" if passed else "FAIL",
                               f"NotAdded={not_added}, ErrorShown={has_error}",
                               duration=duration)
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Missing Category Expense", "Expense",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_EXP_008_negative_amount(self):
        """TC_EXP_008: Add expense with negative amount should fail."""
        start = time.time()
        tc_id = "TC_EXP_008"
        test_data = self.load_csv("test_expense.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_expense_count_from_api()
            self._login_and_go_to_expense()
            self._open_add_expense_modal()
            self._fill_expense_form(row["category"], row["amount"], row["date"])
            self._submit_expense_form()
            time.sleep(2)

            count_after = self._get_expense_count_from_api()
            not_added = count_after == count_before

            page_text = self.driver.page_source.lower()
            has_error = ("lớn hơn 0" in page_text or "positive" in page_text
                         or "hợp lệ" in page_text)

            duration = time.time() - start
            passed = not_added or has_error
            self.record_result(tc_id, "Negative Amount Expense", "Expense",
                               row["description"], "PASS" if passed else "FAIL",
                               f"NotAdded={not_added}, ErrorShown={has_error}",
                               duration=duration)
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Negative Amount Expense", "Expense",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_EXP_DELETE_001_delete_expense(self):
        """TC_EXP_DELETE_001: Delete an expense entry."""
        start = time.time()
        tc_id = "TC_EXP_DELETE_001"

        try:
            # Seed via API
            requests.post(config.API_EXPENSE_ADD,
                          headers={"Authorization": f"Bearer {self._auth_token}"},
                          json={"category": "Delete Test", "amount": 50000,
                                "date": "2025-04-20"})
            time.sleep(1)

            count_before = self._get_expense_count_from_api()
            self._login_and_go_to_expense()

            delete_btns = self.driver.find_elements(By.CSS_SELECTOR,
                "button[class*='delete'], [class*='trash'], .fa-trash")
            if not delete_btns:
                delete_icons = self.driver.find_elements(By.CSS_SELECTOR,
                    "svg[class*='trash'], i[class*='trash']")
                delete_btns = [icon.find_element(By.XPATH, "..") for icon in delete_icons if delete_icons]

            if delete_btns:
                self.scroll_to_element(delete_btns[0])
                self.safe_click(delete_btns[0])
                time.sleep(1)

                confirm_btns = self.driver.find_elements(By.CSS_SELECTOR, "button")
                for btn in confirm_btns:
                    text = btn.text.strip().lower()
                    if "xóa" in text or "delete" in text or "confirm" in text:
                        self.safe_click(btn)
                        break
                time.sleep(2)

            count_after = self._get_expense_count_from_api()
            deleted = count_after < count_before

            duration = time.time() - start
            self.record_result(tc_id, "Delete Expense", "Expense",
                               "Delete an expense entry",
                               "PASS" if deleted else "FAIL",
                               f"CountBefore={count_before}, CountAfter={count_after}",
                               duration=duration)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Delete Expense", "Expense",
                               "Delete expense entry", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    # ─── UI Checks ───────────────────────────────────────────

    def test_TC_EXP_UI_001_page_layout(self):
        """Verify expense page layout."""
        start = time.time()
        tc_id = "TC_EXP_UI_001"

        try:
            self._login_and_go_to_expense()

            page_text = self.driver.page_source
            has_overview = "Chi tiêu" in page_text or "Expense" in page_text
            has_add_btn = any("thêm" in btn.text.lower() or "add" in btn.text.lower()
                              for btn in self.driver.find_elements(By.CSS_SELECTOR, "button"))

            duration = time.time() - start
            all_ok = has_overview and has_add_btn
            self.record_result(
                tc_id, "Expense Page Layout", "Expense UI",
                "Verify expense page has overview, add button, list",
                "PASS" if all_ok else "FAIL",
                f"Overview={has_overview}, AddBtn={has_add_btn}",
                duration=duration
            )
            self.assertTrue(all_ok)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Expense Page Layout", "Expense UI",
                               "Expense page layout", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise


if __name__ == "__main__":
    unittest.main()
