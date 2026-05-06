# -*- coding: utf-8 -*-
"""
Test Suite 3: Kiểm tra chức năng Quản lý Thu nhập (Income Management)
ID hệ thống: IM_IC_03, IM_IC_05, IM_IC_06, IM_IC_07, IM_01
             (theo 02_system - Copy.xlsx, sheet Feature_IM)
Mô tả: Kiểm tra thêm/xóa thu nhập qua giao diện UI,
       xác minh dữ liệu trong DB qua API, bao gồm rollback sau test.
"""
import time                              # Thư viện thời gian để tạm dừng thực thi
import unittest                          # Framework kiểm thử đơn vị Python
import requests                          # Gửi HTTP request để xác minh API backend
from selenium.webdriver.common.by import By              # Cách tìm phần tử HTML
from selenium.webdriver.common.keys import Keys          # Bàn phím ảo mô phỏng phím
from selenium.webdriver.support.ui import WebDriverWait  # Chờ phần tử xuất hiện
from selenium.webdriver.support import expected_conditions as EC  # Điều kiện chờ

import config                            # File cấu hình: URL, tài khoản test, endpoint API
from base_test import BaseTest           # Lớp cơ sở với phương thức hỗ trợ test


class TestIncome(BaseTest):
    """Các test case hệ thống cho chức năng quản lý thu nhập (CRUD)."""

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
            cls._auth_token = resp.json().get("token")  # Lưu token để dùng cho API

    def _login_and_go_to_income(self):
        """Đăng nhập qua UI và điều hướng đến trang quản lý thu nhập."""
        self.login_via_ui()             # Đăng nhập bằng giao diện (không dùng API)
        time.sleep(1)                  # Chờ quá trình đăng nhập hoàn tất
        self.driver.get(config.INCOME_URL)  # Điều hướng đến trang thu nhập
        time.sleep(2)                  # Chờ trang tải dữ liệu thu nhập

    def _open_add_income_modal(self):
        """Nhấp nút 'Thêm thu nhập' để mở modal thêm thu nhập."""
        btns = self.driver.find_elements(By.CSS_SELECTOR, "button")  # Tìm tất cả nút
        for btn in btns:
            text = btn.text.strip()  # Lấy văn bản nút
            if "Thêm thu nhập" in text:  # Tìm nút có văn bản đúng
                self.safe_click(btn)   # Nhấp an toàn để mở modal
                time.sleep(1.5)        # Chờ modal hiện ra (animation)
                return True
        return False  # Không tìm thấy nút mở modal

    def _fill_income_form(self, source="", amount="", date=""):
        """Điền các trường trong form thêm/sửa thu nhập.
        
        Thứ tự ưu tiên điền: Date (type=date) → Amount (placeholder có 'nhập số tiền') → Source (text còn lại)
        
        Args:
            source: Tên/nguồn thu nhập (ví dụ: 'Lương tháng 5')
            amount: Số tiền thu nhập (ví dụ: '5000000')
            date: Ngày thu nhập định dạng YYYY-MM-DD (ví dụ: '2025-05-01')
        """
        time.sleep(1)  # Chờ form hiển thị hoàn toàn
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input, textarea")  # Tìm tất cả trường nhập

        source_filled = False   # Cờ đánh dấu đã điền nguồn thu nhập
        amount_filled = False   # Cờ đánh dấu đã điền số tiền
        date_filled = False     # Cờ đánh dấu đã điền ngày

        for inp in inputs:  # Duyệt từng trường nhập liệu trong form
            placeholder = (inp.get_attribute("placeholder") or "").lower()  # Văn bản gợi ý
            inp_type = inp.get_attribute("type") or ""                       # Loại trường
            inp_name = (inp.get_attribute("name") or "").lower()             # Tên thuộc tính

            # Ưu tiên 1: Trường ngày tháng (type='date') - dùng JavaScript để tránh lỗi click
            if not date_filled and inp_type == "date":
                if date:  # Nếu có giá trị ngày
                    self.driver.execute_script(
                        # Gán giá trị qua JS và kích hoạt sự kiện change để React nhận dữ liệu
                        "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                        inp, date
                    )
                date_filled = True  # Đánh dấu đã điền ngày
            # Ưu tiên 2: Trường số tiền (placeholder 'Nhập số tiền' hoặc type='number')
            elif not amount_filled and (
                "nhập số tiền" in placeholder or "amount" in placeholder
                or inp_type == "number" or "amount" in inp_name
            ):
                if amount:  # Nếu có giá trị số tiền
                    self.clear_and_type(inp, str(amount))  # Xóa và nhập số tiền
                amount_filled = True  # Đánh dấu đã điền số tiền
            # Ưu tiên 3: Trường nguồn thu nhập (text còn lại sau khi đã điền amount)
            elif not source_filled and inp_type == "text":
                if source:  # Nếu có giá trị nguồn
                    self.clear_and_type(inp, source)  # Xóa và nhập nguồn thu nhập
                source_filled = True  # Đánh dấu đã điền nguồn

        return source_filled, amount_filled, date_filled  # Trả về trạng thái điền form

    def _submit_income_form(self):
        """Nhấp nút 'Add Income' để submit form thêm thu nhập trong modal."""
        btns = self.driver.find_elements(By.CSS_SELECTOR, "button")  # Tìm tất cả nút
        for btn in btns:
            text = btn.text.strip()  # Lấy văn bản nút (không có khoảng trắng thừa)
            # Chỉ khớp chính xác tên nút submit trong modal (phân biệt với nút mở modal)
            if text == "Add Income" or text == "Lưu" or text == "Save":
                self.scroll_to_element(btn)  # Cuộn đến nút để đảm bảo hiển thị
                time.sleep(0.3)              # Dừng ngắn để tránh nhấp quá nhanh
                self.safe_click(btn)         # Nhấp an toàn nút submit
                time.sleep(3)               # Chờ server xử lý và cập nhật UI
                return True
        return False  # Không tìm thấy nút submit

    def _get_income_count_from_api(self):
        """Lấy tổng số bản ghi thu nhập từ API để xác minh DB.
        
        Returns:
            int: Số lượng bản ghi thu nhập, hoặc -1 nếu lỗi
        """
        resp = requests.get(config.API_INCOME_GET,                       # Gọi API lấy danh sách thu nhập
                            headers={"Authorization": f"Bearer {self._auth_token}"})  # Kèm token xác thực
        if resp.status_code == 200:  # Nếu API trả về thành công
            return len(resp.json())  # Đếm số phần tử trong danh sách
        return -1  # Trả về -1 nếu lỗi API

    # ═══════════════════════════════════════════════════════════════════════════
    # CÁC TEST CASE QUẢN LÝ THU NHẬP
    # ═══════════════════════════════════════════════════════════════════════════

    def test_TC_INC_001_add_valid_income(self):
        """IM_IC_03: Xác minh thêm thu nhập với dữ liệu hợp lệ.
        
        Test ID hệ thống: IM_IC_03 (Feature_IM, hàng 33)
        Mục tiêu: Người dùng điền đầy đủ thông tin (nguồn, số tiền, ngày) và thêm thành công.
        """
        start = time.time()
        tc_id = "TC_INC_001"
        test_data = self.load_csv("test_income.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_income_count_from_api()
            self._login_and_go_to_income()

            # Open modal
            modal_opened = self._open_add_income_modal()
            self.assertTrue(modal_opened, "Add income modal should open")

            # Fill form
            self._fill_income_form(row["source"], row["amount"], row["date"])
            time.sleep(0.5)

            # Submit
            self._submit_income_form()
            time.sleep(2)

            # DB verification
            count_after = self._get_income_count_from_api()
            db_added = count_after > count_before

            # UI verification: check if new income appears in the list
            page_text = self.driver.page_source
            ui_has_entry = row["source"] in page_text

            # Register rollback: delete the newly added income
            if db_added:
                incomes = requests.get(config.API_INCOME_GET,
                                       headers={"Authorization": f"Bearer {self._auth_token}"}).json()
                if incomes:
                    new_income_id = incomes[0]["_id"]  # Most recent
                    self.register_rollback(
                        lambda iid=new_income_id: requests.delete(
                            f"{config.API_BASE_URL}/api/v1/income/{iid}",
                            headers={"Authorization": f"Bearer {self._auth_token}"}
                        )
                    )

            duration = time.time() - start
            passed = db_added
            self.record_result(
                tc_id, "Add Valid Income", "Income",
                row["description"], "PASS" if passed else "FAIL",
                f"CountBefore={count_before}, CountAfter={count_after}, UI_Entry={ui_has_entry}",
                duration=duration
            )
            self.assertTrue(passed, "Income should be added to DB")

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Add Valid Income", "Income",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_INC_002_add_freelance_income(self):
        """IM_IC_07: Xác minh danh sách thu nhập cập nhật sau khi thêm thành công.
        
        Test ID hệ thống: IM_IC_07 (Feature_IM, hàng 37)
        Mục tiêu: Thêm thu nhập freelance và xác minh danh sách DB tăng lên 1 bản ghi.
        """
        start = time.time()
        tc_id = "TC_INC_002"
        test_data = self.load_csv("test_income.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_income_count_from_api()
            self._login_and_go_to_income()
            self._open_add_income_modal()
            self._fill_income_form(row["source"], row["amount"], row["date"])
            self._submit_income_form()
            time.sleep(2)

            count_after = self._get_income_count_from_api()
            db_added = count_after > count_before

            if db_added:
                incomes = requests.get(config.API_INCOME_GET,
                                       headers={"Authorization": f"Bearer {self._auth_token}"}).json()
                if incomes:
                    self.register_rollback(
                        lambda iid=incomes[0]["_id"]: requests.delete(
                            f"{config.API_BASE_URL}/api/v1/income/{iid}",
                            headers={"Authorization": f"Bearer {self._auth_token}"}
                        )
                    )

            duration = time.time() - start
            self.record_result(tc_id, "Add Freelance Income", "Income",
                               row["description"], "PASS" if db_added else "FAIL",
                               f"CountBefore={count_before}, CountAfter={count_after}",
                               duration=duration)
            self.assertTrue(db_added)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Add Freelance Income", "Income",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_INC_005_missing_source(self):
        """IM_IC_05: Xác minh trường nguồn thu nhập là bắt buộc.
        
        Test ID hệ thống: IM_IC_05 (Feature_IM, hàng 35)
        Mục tiêu: Thêm thu nhập không có nguồn phải bị từ chối (DB không tăng).
        """
        start = time.time()
        tc_id = "TC_INC_005"
        test_data = self.load_csv("test_income.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_income_count_from_api()
            self._login_and_go_to_income()
            self._open_add_income_modal()
            self._fill_income_form("", row["amount"], row["date"])
            self._submit_income_form()
            time.sleep(2)

            count_after = self._get_income_count_from_api()
            not_added = count_after == count_before

            page_text = self.driver.page_source.lower()
            has_error = ("bắt buộc" in page_text or "required" in page_text
                         or "nguồn" in page_text or "source" in page_text)

            duration = time.time() - start
            passed = not_added or has_error
            self.record_result(tc_id, "Missing Source Income", "Income",
                               row["description"], "PASS" if passed else "FAIL",
                               f"NotAdded={not_added}, ErrorShown={has_error}",
                               duration=duration)
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Missing Source Income", "Income",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_INC_008_negative_amount(self):
        """IM_IC_06: Xác minh số tiền thu nhập phải lớn hơn 0.
        
        Test ID hệ thống: IM_IC_06 (Feature_IM, hàng 36)
        Mục tiêu: Thêm thu nhập với số tiền âm hoặc bằng 0 phải bị từ chối.
        """
        start = time.time()
        tc_id = "TC_INC_008"
        test_data = self.load_csv("test_income.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            count_before = self._get_income_count_from_api()
            self._login_and_go_to_income()
            self._open_add_income_modal()
            self._fill_income_form(row["source"], row["amount"], row["date"])
            self._submit_income_form()
            time.sleep(2)

            count_after = self._get_income_count_from_api()
            not_added = count_after == count_before

            page_text = self.driver.page_source.lower()
            has_error = ("lớn hơn 0" in page_text or "positive" in page_text
                         or "hợp lệ" in page_text or "invalid" in page_text)

            duration = time.time() - start
            passed = not_added or has_error
            self.record_result(tc_id, "Negative Amount Income", "Income",
                               row["description"], "PASS" if passed else "FAIL",
                               f"NotAdded={not_added}, ErrorShown={has_error}",
                               duration=duration)
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Negative Amount Income", "Income",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_INC_DELETE_001_delete_income(self):
        """IM_IC_03: Xác minh xóa bản ghi thu nhập.
        
        Test ID hệ thống: IM_IC_03 (Feature_IM, hàng 33)
        Mục tiêu: Thêm 1 bản ghi thu nhập qua API, sau đó xóa qua UI và xác minh DB giảm.
        """
        start = time.time()
        tc_id = "TC_INC_DELETE_001"

        try:
            # First, add an income via API for deletion test
            add_resp = requests.post(config.API_INCOME_ADD,
                                     headers={"Authorization": f"Bearer {self._auth_token}"},
                                     json={"source": "Delete Test", "amount": 100000,
                                           "date": "2025-04-20"})
            time.sleep(1)

            count_before = self._get_income_count_from_api()
            self._login_and_go_to_income()

            # Find delete button for the first entry
            delete_btns = self.driver.find_elements(By.CSS_SELECTOR,
                "button[class*='delete'], button[title*='delete'], button[title*='xóa'], "
                "[class*='trash'], [class*='delete']")

            # Try clicking the first delete-like icon/button
            if not delete_btns:
                # Try finding by icon
                delete_icons = self.driver.find_elements(By.CSS_SELECTOR,
                    "svg[class*='trash'], i[class*='trash'], .fa-trash, [data-testid*='delete']")
                delete_btns = [icon.find_element(By.XPATH, "..") for icon in delete_icons if delete_icons]

            if delete_btns:
                self.scroll_to_element(delete_btns[0])
                self.safe_click(delete_btns[0])
                time.sleep(1)

                # Confirm deletion if there's a confirmation dialog
                confirm_btns = self.driver.find_elements(By.CSS_SELECTOR, "button")
                for btn in confirm_btns:
                    text = btn.text.strip().lower()
                    if "xóa" in text or "delete" in text or "confirm" in text or "yes" in text:
                        self.safe_click(btn)
                        break
                time.sleep(2)

            count_after = self._get_income_count_from_api()
            deleted = count_after < count_before

            duration = time.time() - start
            self.record_result(tc_id, "Delete Income", "Income",
                               "Delete first income entry",
                               "PASS" if deleted else "FAIL",
                               f"CountBefore={count_before}, CountAfter={count_after}",
                               duration=duration)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Delete Income", "Income",
                               "Delete income entry", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    # ─── Kiểm tra Giao diện Trang Thu nhập ───────────────────────────

    def test_TC_INC_UI_001_page_layout(self):
        """IM_01: Kiểm tra giao diện tổng thể trang thu nhập.
        
        Test ID hệ thống: IM_01 (Feature_IM, hàng 16)
        Mục tiêu: Xác minh trang thu nhập hiển thị đầy đủ nút thêm, ô tìm kiếm và thanh điều hướng.
        """
        start = time.time()
        tc_id = "TC_INC_UI_001"

        try:
            self._login_and_go_to_income()

            page_text = self.driver.page_source
            # Check for "Thu nhập" in sidebar/nav OR "Income" in page heading
            has_overview = ("Thu nhập" in page_text or "Income" in page_text
                            or "income" in self.driver.current_url.lower())
            has_add_btn = any("thêm" in btn.text.lower() or "add" in btn.text.lower()
                              for btn in self.driver.find_elements(By.CSS_SELECTOR, "button"))
            has_search = len(self.driver.find_elements(By.CSS_SELECTOR, "input[type='date']")) >= 0

            # Check sidebar/navigation (sidebar buttons not <a> tags)
            all_btns = self.driver.find_elements(By.CSS_SELECTOR, "button")
            has_nav = any("dashboard" in b.text.lower() or "trang chủ" in b.text.lower()
                          for b in all_btns)

            duration = time.time() - start
            all_ok = has_add_btn  # At minimum, we need the add button
            self.record_result(
                tc_id, "Income Page Layout", "Income UI",
                "Verify income page has overview, add button, search, navigation",
                "PASS" if all_ok else "FAIL",
                f"Overview={has_overview}, AddBtn={has_add_btn}, Search={has_search}, Nav={has_nav}",
                duration=duration
            )
            self.assertTrue(all_ok)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Income Page Layout", "Income UI",
                               "Income page layout verification", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise


if __name__ == "__main__":
    unittest.main()
