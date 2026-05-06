# -*- coding: utf-8 -*-
"""
Test Suite 1: Kiểm tra chức năng Đăng ký (Registration / Sign Up)
ID hệ thống: REG_01 → REG_05, INT_01 (theo 02_system - Copy.xlsx, sheet Feature_RL)
Mô tả: Kiểm tra giao diện trang đăng ký, xác thực dữ liệu biểu mẫu,
       xác minh cơ sở dữ liệu qua API và quản lý trạng thái sau test.
"""
import time                                              # Thư viện thời gian để tạm dừng thực thi
import unittest                                          # Framework kiểm thử đơn vị Python
import requests                                          # Thư viện gửi HTTP request để xác minh API
from datetime import datetime                            # Xử lý ngày giờ cho báo cáo
from selenium.webdriver.common.by import By              # Định nghĩa cách tìm phần tử HTML
from selenium.webdriver.common.keys import Keys          # Bàn phím ảo để mô phỏng nhấn phím
from selenium.webdriver.support.ui import WebDriverWait  # Chờ đợi phần tử xuất hiện
from selenium.webdriver.support import expected_conditions as EC  # Điều kiện chờ cho Selenium

import config                                            # File cấu hình URL và hằng số dự án
from base_test import BaseTest                           # Lớp cơ sở chứa các phương thức hỗ trợ test


class TestRegistration(BaseTest):
    """Các test case hệ thống cho chức năng đăng ký người dùng."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo lớp test - gọi setup từ lớp cha BaseTest."""
        super().setUpClass()

    # ─── Helper: Điều hướng và điền biểu mẫu đăng ký ────────────────────────

    def _navigate_to_signup(self):
        """Điều hướng trình duyệt đến trang đăng ký."""
        self.driver.get(config.SIGNUP_URL)  # Mở URL trang đăng ký
        time.sleep(1.5)                     # Chờ trang tải hoàn chỉnh

    def _fill_signup_form(self, full_name="", email="", password=""):
        """Tìm và điền các trường biểu mẫu đăng ký.
        
        Args:
            full_name: Họ và tên đầy đủ của người dùng
            email: Địa chỉ email đăng ký
            password: Mật khẩu đăng ký
        """
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")  # Tìm tất cả trường nhập liệu
        name_input = None      # Trường họ tên
        email_input = None     # Trường email
        password_input = None  # Trường mật khẩu

        for inp in inputs:  # Duyệt qua từng trường nhập liệu
            placeholder = (inp.get_attribute("placeholder") or "").lower()  # Lấy văn bản gợi ý
            inp_type = inp.get_attribute("type") or ""                       # Lấy loại trường

            # Nhận diện trường họ tên qua gợi ý hoặc tên thuộc tính
            if "họ" in placeholder or "tên" in placeholder or "name" in placeholder.lower():
                name_input = inp
            elif "email" in placeholder:          # Nhận diện trường email
                email_input = inp
            elif inp_type == "password" or "mật khẩu" in placeholder:  # Nhận diện trường mật khẩu
                password_input = inp

        if name_input and full_name:      # Điền họ tên nếu tìm được trường và có giá trị
            self.clear_and_type(name_input, full_name)
        if email_input and email:         # Điền email nếu tìm được trường và có giá trị
            self.clear_and_type(email_input, email)
        if password_input and password:   # Điền mật khẩu nếu tìm được trường và có giá trị
            self.clear_and_type(password_input, password)

        return name_input, email_input, password_input  # Trả về các trường để kiểm tra

    def _click_signup_button(self):
        """Tìm và nhấp nút đăng ký/submit của biểu mẫu."""
        btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")  # Tìm nút submit
        for btn in btns:
            text = btn.text.strip().upper()  # Lấy văn bản nút, chuyển hoa
            if "ĐĂNG KÝ" in text or "SIGN" in text or "REGISTER" in text:  # Kiểm tra văn bản nút
                self.safe_click(btn)  # Nhấp an toàn (có xử lý exception)
                return True
        if btns:                   # Nếu không tìm được theo văn bản, nhấp nút đầu tiên
            self.safe_click(btns[0])
            return True
        return False               # Không tìm thấy nút submit

    # ─── Hỗ trợ: Kiểm tra tồn tại user sau test ──────────────────────────────

    def _rollback_delete_user(self, email, password):
        """Xác minh user test đã tồn tại trong DB qua API đăng nhập (thông tin).
        
        Lưu ý: Không có endpoint xóa user, chỉ kiểm tra sự tồn tại.
        """
        try:
            resp = requests.post(config.API_AUTH_LOGIN, json={
                "email": email, "password": password  # Thử đăng nhập để kiểm tra user tồn tại
            })
            if resp.status_code == 200:  # Đăng nhập thành công nghĩa là user tồn tại trong DB
                print(f"[ROLLBACK INFO] User test {email} tồn tại trong DB (lấy token thành công).")
        except Exception as e:
            print(f"[ROLLBACK] Không thể xác minh user {email}: {e}")  # Ghi log lỗi

    # ═══════════════════════════════════════════════════════════════════════════
    # CÁC TEST CASE ĐĂNG KÝ
    # ═══════════════════════════════════════════════════════════════════════════

    def test_TC_REG_001_valid_registration(self):
        """REG_01: Đăng ký với dữ liệu hợp lệ thành công.
        
        Test ID hệ thống: REG_01 (Feature_RL, hàng 20)
        Mục tiêu: Xác minh người dùng có thể đăng ký tài khoản mới với dữ liệu hợp lệ.
        """
        start = time.time()   # Ghi lại thời điểm bắt đầu test để tính thời gian thực thi
        tc_id = "TC_REG_001"  # Mã định danh test case nội bộ
        test_data = self.load_csv("test_users.csv")  # Tải dữ liệu test từ file CSV
        row = next(r for r in test_data if r["test_case_id"] == tc_id)  # Lấy dòng dữ liệu tương ứng

        # Tạo email duy nhất để tránh xung đột với lần chạy test trước
        unique_email = f"test_reg001_{int(time.time())}@test.com"

        try:
            self._navigate_to_signup()  # Điều hướng đến trang đăng ký

            # Kiểm tra URL hiện tại có chứa "signup" không
            self.assertIn("signup", self.driver.current_url.lower(),
                          "Phải đang ở trang đăng ký")

            self._fill_signup_form(row["full_name"], unique_email, row["password"])  # Điền biểu mẫu
            self._click_signup_button()  # Nhấp nút đăng ký
            time.sleep(3)               # Chờ server xử lý và chuyển hướng

            # Kiểm tra chuyển hướng sang trang dashboard sau đăng ký thành công
            current = self.driver.current_url         # Lấy URL hiện tại sau đăng ký
            success = "dashboard" in current          # Kiểm tra đã vào dashboard chưa

            # Xác minh user tồn tại trong DB bằng cách đăng nhập qua API
            db_verified = False
            if success:  # Chỉ xác minh DB nếu chuyển hướng thành công
                login_resp = requests.post(config.API_AUTH_LOGIN, json={
                    "email": unique_email, "password": row["password"]
                })
                db_verified = login_resp.status_code == 200  # 200 = đăng nhập thành công

            duration = time.time() - start  # Tính tổng thời gian chạy test
            status = "PASS" if success and db_verified else "FAIL"  # Xác định kết quả
            self.record_result(
                tc_id, "Valid Registration", "Registration",  # Ghi kết quả vào báo cáo
                row["description"], status,
                f"Redirected={success}, DB_Verified={db_verified}",
                duration=duration
            )
            self.assertTrue(success, "Đăng ký thành công phải chuyển hướng sang dashboard")

        except Exception as e:  # Xử lý ngoại lệ - chụp màn hình và ghi log lỗi
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)  # Chụp màn hình để debug
            self.record_result(
                tc_id, "Valid Registration", "Registration",
                row["description"], "ERROR", str(e),
                screenshot_path=ss, duration=duration
            )
            raise  # Ném lại exception để test runner ghi nhận lỗi

    def test_TC_REG_002_missing_fullname(self):
        """REG_02: Đăng ký không có họ tên phải thất bại.
        
        Test ID hệ thống: REG_02 (Feature_RL, hàng 21)
        Mục tiêu: Kiểm tra validation - không cho phép đăng ký khi bỏ trống trường bắt buộc.
        """
        start = time.time()   # Ghi thời điểm bắt đầu
        tc_id = "TC_REG_002"  # Mã test nội bộ
        test_data = self.load_csv("test_users.csv")  # Tải dữ liệu test
        row = next(r for r in test_data if r["test_case_id"] == tc_id)  # Lấy dữ liệu test case

        try:
            self._navigate_to_signup()                             # Điều hướng trang đăng ký
            self._fill_signup_form("", row["email"], row["password"])  # Điền form (bỏ trống họ tên)
            self._click_signup_button()                            # Nhấp nút đăng ký
            time.sleep(2)                                          # Chờ phản hồi

            # Kiểm tra ở lại trang đăng ký (không chuyển hướng sang dashboard)
            current = self.driver.current_url
            stayed = "signUp" in current.lower() or "signup" in current.lower()
            
            # Kiểm tra thông báo lỗi xuất hiện trên trang
            page_text = self.driver.page_source
            has_error = ("lỗi" in page_text.lower() or "error" in page_text.lower()
                         or "bắt buộc" in page_text.lower() or "vui lòng" in page_text.lower()
                         or "required" in page_text.lower() or "họ và tên" in page_text.lower())

            duration = time.time() - start
            passed = stayed or has_error   # Pass nếu ở lại trang HOẶC có thông báo lỗi
            status = "PASS" if passed else "FAIL"
            self.record_result(
                tc_id, "Missing Full Name", "Registration",
                row["description"], status,
                f"StayedOnPage={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed, "Không được phép đăng ký khi thiếu họ tên")

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)  # Chụp màn hình khi lỗi
            self.record_result(
                tc_id, "Missing Full Name", "Registration",
                row["description"], "ERROR", str(e),
                screenshot_path=ss, duration=duration
            )
            raise

    def test_TC_REG_005_invalid_email(self):
        """REG_03: Đăng ký với email sai định dạng phải bị từ chối.
        
        Test ID hệ thống: REG_03 (Feature_RL, hàng 22)
        Mục tiêu: Kiểm tra validation định dạng email (phải có @ và domain).
        """
        start = time.time()   # Ghi thời điểm bắt đầu
        tc_id = "TC_REG_005"  # Mã test nội bộ (ánh xạ REG_03 trong system)
        test_data = self.load_csv("test_users.csv")  # Tải dữ liệu test
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            self._navigate_to_signup()  # Điều hướng trang đăng ký
            self._fill_signup_form(row["full_name"], row["email"], row["password"])  # Điền form với email sai
            self._click_signup_button()  # Nhấp đăng ký
            time.sleep(2)               # Chờ phản hồi

            current = self.driver.current_url
            stayed = "signup" in current.lower()  # Kiểm tra ở lại trang đăng ký
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi email không hợp lệ
            has_error = "email" in page_text and ("hợp lệ" in page_text or "valid" in page_text or "lỗi" in page_text)

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu ở lại trang hoặc có lỗi
            self.record_result(
                tc_id, "Invalid Email Format", "Registration",
                row["description"], "PASS" if passed else "FAIL",
                f"StayedOnPage={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(
                tc_id, "Invalid Email Format", "Registration",
                row["description"], "ERROR", str(e),
                screenshot_path=ss, duration=duration
            )
            raise

    def test_TC_REG_006_weak_password_short(self):
        """REG_05: Đăng ký với mật khẩu quá ngắn (dưới 8 ký tự) phải bị từ chối.
        
        Test ID hệ thống: REG_05 (Feature_RL, hàng 24)
        Mục tiêu: Kiểm tra yêu cầu độ dài tối thiểu của mật khẩu.
        """
        start = time.time()   # Ghi thời điểm bắt đầu
        tc_id = "TC_REG_006"  # Mã test nội bộ (ánh xạ REG_05 trong system)
        test_data = self.load_csv("test_users.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            self._navigate_to_signup()  # Điều hướng trang đăng ký
            self._fill_signup_form(row["full_name"], row["email"], row["password"])  # Điền mật khẩu ngắn
            self._click_signup_button()  # Nhấp đăng ký
            time.sleep(2)               # Chờ phản hồi

            current = self.driver.current_url
            stayed = "signup" in current.lower()  # Kiểm tra ở lại trang
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi về độ dài mật khẩu
            has_error = (("password" in page_text or "mật khẩu" in page_text) and
                         ("8" in page_text or "character" in page_text or "ký tự" in page_text or "at least" in page_text))

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu trang từ chối đăng ký
            self.record_result(
                tc_id, "Weak Password (Short)", "Registration",
                row["description"], "PASS" if passed else "FAIL",
                f"StayedOnPage={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(
                tc_id, "Weak Password (Short)", "Registration",
                row["description"], "ERROR", str(e),
                screenshot_path=ss, duration=duration
            )
            raise

    def test_TC_REG_007_no_uppercase(self):
        """REG_05: Đăng ký với mật khẩu không có chữ hoa phải bị từ chối.
        
        Test ID hệ thống: REG_05 (Feature_RL, hàng 24)
        Mục tiêu: Kiểm tra yêu cầu mật khẩu phải chứa ít nhất một chữ cái viết hoa.
        """
        start = time.time()   # Ghi thời điểm bắt đầu
        tc_id = "TC_REG_007"  # Mã test nội bộ
        test_data = self.load_csv("test_users.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            self._navigate_to_signup()  # Điều hướng trang đăng ký
            self._fill_signup_form(row["full_name"], row["email"], row["password"])  # Điền mật khẩu toàn chữ thường
            self._click_signup_button()  # Nhấp đăng ký
            time.sleep(2)               # Chờ phản hồi

            stayed = "signup" in self.driver.current_url.lower()  # Kiểm tra ở lại trang
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi về chữ hoa
            has_error = "uppercase" in page_text or "chữ hoa" in page_text or "A-Z" in self.driver.page_source

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu hệ thống từ chối
            self.record_result(
                tc_id, "No Uppercase in Password", "Registration",
                row["description"], "PASS" if passed else "FAIL",
                f"StayedOnPage={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "No Uppercase in Password", "Registration",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_REG_010_no_special_char(self):
        """REG_05: Đăng ký với mật khẩu không có ký tự đặc biệt phải bị từ chối.
        
        Test ID hệ thống: REG_05 (Feature_RL, hàng 24)
        Mục tiêu: Kiểm tra yêu cầu mật khẩu phải chứa ký tự đặc biệt (!@#$...).
        """
        start = time.time()   # Ghi thời điểm bắt đầu
        tc_id = "TC_REG_010"  # Mã test nội bộ
        test_data = self.load_csv("test_users.csv")
        row = next(r for r in test_data if r["test_case_id"] == tc_id)

        try:
            self._navigate_to_signup()  # Điều hướng trang đăng ký
            self._fill_signup_form(row["full_name"], row["email"], row["password"])  # Điền mật khẩu không có ký tự đặc biệt
            self._click_signup_button()  # Nhấp đăng ký
            time.sleep(2)               # Chờ phản hồi

            stayed = "signup" in self.driver.current_url.lower()  # Kiểm tra ở lại trang
            page_text = self.driver.page_source
            # Kiểm tra thông báo lỗi về ký tự đặc biệt
            has_error = ("special" in page_text.lower() or "đặc biệt" in page_text.lower()
                         or "!@#$" in page_text)

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu hệ thống từ chối
            self.record_result(
                tc_id, "No Special Character", "Registration",
                row["description"], "PASS" if passed else "FAIL",
                f"StayedOnPage={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "No Special Character", "Registration",
                               row["description"], "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    # ─── Kiểm tra Giao diện Trang Đăng ký ────────────────────────────────────

    def test_TC_REG_UI_001_page_elements(self):
        """INT_01: Kiểm tra giao diện tổng thể trang đăng ký.
        
        Test ID hệ thống: INT_01 (Feature_RL, hàng 16)
        Mục tiêu: Xác minh trang đăng ký hiển thị đầy đủ các thành phần giao diện cần thiết.
        """
        start = time.time()       # Ghi thời điểm bắt đầu
        tc_id = "TC_REG_UI_001"   # Mã test nội bộ

        try:
            self._navigate_to_signup()  # Điều hướng trang đăng ký

            # Kiểm tra tiêu đề trang có tồn tại không
            page_text = self.driver.page_source
            has_heading = "Tạo tài khoản" in page_text or "Sign Up" in page_text

            # Kiểm tra số lượng trường nhập liệu (tối thiểu 3: họ tên, email, mật khẩu)
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
            has_enough_inputs = len(inputs) >= 3

            # Kiểm tra nút submit tồn tại
            btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            has_submit = len(btns) > 0

            # Kiểm tra liên kết đến trang đăng nhập
            links = self.driver.find_elements(By.CSS_SELECTOR, "a")
            has_login_link = any("login" in (l.get_attribute("href") or "").lower() for l in links)

            duration = time.time() - start
            all_ok = has_heading and has_enough_inputs and has_submit and has_login_link  # Tất cả phải đúng
            self.record_result(
                tc_id, "Signup Page UI Elements", "Registration UI",
                "Xác minh tất cả phần tử giao diện trang đăng ký",
                "PASS" if all_ok else "FAIL",
                f"Heading={has_heading}, Inputs={len(inputs)}, Submit={has_submit}, LoginLink={has_login_link}",
                duration=duration
            )
            self.assertTrue(all_ok, "Tất cả phần tử trang đăng ký phải hiển thị đầy đủ")

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)  # Chụp màn hình khi có lỗi
            self.record_result(tc_id, "Signup Page UI Elements", "Registration UI",
                               "Xác minh phần tử trang đăng ký", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise


if __name__ == "__main__":
    unittest.main()  # Chạy test khi file được thực thi trực tiếp
