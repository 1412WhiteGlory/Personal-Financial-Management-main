# -*- coding: utf-8 -*-
"""
Test Suite 2: Kiểm tra chức năng Đăng nhập (Login)
ID hệ thống: LOG_01 → LOG_05, INT_02 (theo 02_system - Copy.xlsx, sheet Feature_RL)
Mô tả: Kiểm tra giao diện trang đăng nhập, xác thực dữ liệu biểu mẫu,
       đăng nhập thành công/thất bại và xác minh token trong cơ sở dữ liệu.
"""
import time                              # Thư viện thời gian để tạm dừng thực thi
import unittest                          # Framework kiểm thử đơn vị Python
import requests                          # Gửi HTTP request để xác minh API backend
from datetime import datetime            # Xử lý ngày giờ
from selenium.webdriver.common.by import By  # Cách tìm phần tử HTML trong Selenium

import config                            # File cấu hình: URL, tài khoản test, hằng số
from base_test import BaseTest           # Lớp cơ sở với các phương thức hỗ trợ test


class TestLogin(BaseTest):
    """Các test case hệ thống cho chức năng đăng nhập người dùng."""

    @classmethod
    def setUpClass(cls):
        """Khởi tạo lớp test: đảm bảo tài khoản test tồn tại trong DB trước khi chạy."""
        super().setUpClass()  # Gọi setup từ lớp cha
        # Đăng ký tài khoản test - bỏ qua nếu đã tồn tại (HTTP 409)
        requests.post(config.API_AUTH_REGISTER, json={
            "fullName": config.TEST_USER_FULLNAME,   # Họ tên người dùng test
            "email": config.TEST_USER_EMAIL,          # Email người dùng test
            "password": config.TEST_USER_PASSWORD     # Mật khẩu người dùng test
        })

    # ─── Helper: Điều hướng và điền biểu mẫu đăng nhập ──────────────────────

    def _navigate_to_login(self):
        """Điều hướng đến trang đăng nhập và xóa localStorage để đảm bảo đăng xuất."""
        self.driver.get(config.LOGIN_URL)  # Mở trang đăng nhập
        time.sleep(0.5)                    # Chờ trang tải
        try:
            self.driver.execute_script("localStorage.clear();")  # Xóa token cũ trong localStorage
        except Exception:
            pass                           # Bỏ qua lỗi nếu localStorage không khả dụng
        self.driver.get(config.LOGIN_URL)  # Tải lại trang để đảm bảo trạng thái sạch
        time.sleep(1.5)                    # Chờ trang tải hoàn chỉnh

    def _fill_login_form(self, email="", password=""):
        """Tìm và điền các trường email và mật khẩu trong biểu mẫu đăng nhập.
        
        Args:
            email: Địa chỉ email đăng nhập
            password: Mật khẩu đăng nhập
        """
        inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")  # Tìm tất cả trường nhập
        email_input = None      # Biến lưu trường email
        password_input = None   # Biến lưu trường mật khẩu

        for inp in inputs:  # Duyệt từng trường nhập liệu
            inp_type = inp.get_attribute("type") or ""                     # Lấy loại trường
            placeholder = (inp.get_attribute("placeholder") or "").lower() # Lấy gợi ý

            if inp_type == "password" or "mật khẩu" in placeholder:  # Nhận diện trường mật khẩu
                password_input = inp
            elif inp_type in ("text", "email") or "email" in placeholder:  # Nhận diện trường email
                email_input = inp

        if email_input and email:       # Điền email nếu tìm được trường và có giá trị
            self.clear_and_type(email_input, email)
        if password_input and password: # Điền mật khẩu nếu tìm được trường và có giá trị
            self.clear_and_type(password_input, password)

        return email_input, password_input  # Trả về các trường để kiểm tra

    def _click_login_button(self):
        """Tìm và nhấp nút đăng nhập trong biểu mẫu."""
        btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")  # Tìm nút submit
        for btn in btns:
            text = btn.text.strip().upper()  # Lấy văn bản nút, chuyển hoa
            if "ĐĂNG NHẬP" in text or "LOGIN" in text:  # Kiểm tra văn bản nút
                self.safe_click(btn)   # Nhấp an toàn
                return True
        if btns:                       # Nếu không tìm theo văn bản, nhấp nút đầu tiên
            self.safe_click(btns[0])
            return True
        return False                   # Không tìm thấy nút đăng nhập

    # ═══════════════════════════════════════════════════════════════════════════
    # CÁC TEST CASE ĐĂNG NHẬP
    # ═══════════════════════════════════════════════════════════════════════════

    def test_TC_LOGIN_001_valid_login(self):
        """LOG_01: Xác minh đăng nhập thành công với thông tin đăng nhập hợp lệ.
        
        Test ID hệ thống: LOG_01 (Feature_RL, hàng 25)
        Mục tiêu: Người dùng đăng nhập với email và mật khẩu đúng, 
                  hệ thống chuyển hướng đến dashboard và token hợp lệ.
        """
        start = time.time()     # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_001"  # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            self._fill_login_form(config.TEST_USER_EMAIL, config.TEST_USER_PASSWORD)  # Điền thông tin
            self._click_login_button()  # Nhấp nút đăng nhập
            time.sleep(3)              # Chờ server xử lý và chuyển hướng

            current = self.driver.current_url  # Lấy URL sau đăng nhập
            success = "dashboard" in current   # Kiểm tra đã vào dashboard chưa

            # Xác minh token trong DB bằng cách gọi API với token từ localStorage
            db_verified = False
            if success:  # Chỉ xác minh nếu chuyển hướng thành công
                token = self.driver.execute_script("return localStorage.getItem('token');")  # Lấy token
                if token:  # Nếu có token
                    resp = requests.get(config.API_AUTH_GET_USER,
                                        headers={"Authorization": f"Bearer {token}"})  # Gọi API xác minh
                    db_verified = resp.status_code == 200  # 200 = token hợp lệ

            duration = time.time() - start  # Tính thời gian thực thi
            passed = success and db_verified  # Cả hai điều kiện phải đúng
            self.record_result(
                tc_id, "Valid Login", "Login",
                "Đăng nhập với thông tin hợp lệ và xác minh token trong DB",
                "PASS" if passed else "FAIL",
                f"Redirected={success}, DB_Token_Valid={db_verified}",
                duration=duration
            )
            self.assertTrue(passed, "Phải đăng nhập thành công và token hợp lệ")

        except Exception as e:  # Xử lý lỗi không mong đợi
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)  # Chụp màn hình để debug
            self.record_result(tc_id, "Valid Login", "Login",
                               "Đăng nhập với thông tin hợp lệ", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_LOGIN_002_wrong_password(self):
        """LOG_02: Xác minh đăng nhập thất bại khi mật khẩu sai.
        
        Test ID hệ thống: LOG_02 (Feature_RL, hàng 26)
        Mục tiêu: Kiểm tra hệ thống hiển thị lỗi và không cho đăng nhập khi sai mật khẩu.
        """
        start = time.time()     # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_002"  # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            self._fill_login_form(config.TEST_USER_EMAIL, "WrongPassword@999")  # Điền mật khẩu sai
            self._click_login_button()  # Nhấp đăng nhập
            time.sleep(2)              # Chờ phản hồi

            current = self.driver.current_url
            stayed = "login" in current.lower()  # Kiểm tra vẫn ở trang đăng nhập
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi xuất hiện
            has_error = ("invalid" in page_text or "lỗi" in page_text or "sai" in page_text
                         or "incorrect" in page_text or "không hợp lệ" in page_text)

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu ở lại trang hoặc có thông báo lỗi
            self.record_result(
                tc_id, "Wrong Password Login", "Login",
                "Đăng nhập với mật khẩu sai phải hiển thị lỗi",
                "PASS" if passed else "FAIL",
                f"StayedOnLogin={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Wrong Password Login", "Login",
                               "Đăng nhập sai mật khẩu", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_LOGIN_003_empty_email(self):
        """LOG_02: Xác minh đăng nhập thất bại khi bỏ trống email.
        
        Test ID hệ thống: LOG_02 (Feature_RL, hàng 26)
        Mục tiêu: Kiểm tra validation - hệ thống báo lỗi khi email trống.
        """
        start = time.time()     # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_003"  # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            self._fill_login_form("", config.TEST_USER_PASSWORD)  # Bỏ trống email
            self._click_login_button()  # Nhấp đăng nhập
            time.sleep(2)              # Chờ phản hồi

            stayed = "login" in self.driver.current_url.lower()  # Kiểm tra vẫn ở trang đăng nhập
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi email trống
            has_error = "email" in page_text and ("hợp lệ" in page_text or "required" in page_text
                                                   or "vui lòng" in page_text)

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu hệ thống từ chối đăng nhập
            self.record_result(
                tc_id, "Empty Email Login", "Login",
                "Đăng nhập không có email phải hiển thị lỗi validation",
                "PASS" if passed else "FAIL",
                f"StayedOnLogin={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Empty Email Login", "Login",
                               "Đăng nhập email trống", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_LOGIN_004_empty_password(self):
        """LOG_02: Xác minh đăng nhập thất bại khi bỏ trống mật khẩu.
        
        Test ID hệ thống: LOG_02 (Feature_RL, hàng 26)
        Mục tiêu: Kiểm tra validation - hệ thống báo lỗi khi mật khẩu trống.
        """
        start = time.time()     # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_004"  # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            self._fill_login_form(config.TEST_USER_EMAIL, "")  # Bỏ trống mật khẩu
            self._click_login_button()  # Nhấp đăng nhập
            time.sleep(2)              # Chờ phản hồi

            stayed = "login" in self.driver.current_url.lower()  # Kiểm tra vẫn ở trang đăng nhập
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi mật khẩu trống
            has_error = (("mật khẩu" in page_text or "password" in page_text) and
                         ("vui lòng" in page_text or "required" in page_text or "8" in page_text))

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu hệ thống từ chối
            self.record_result(
                tc_id, "Empty Password Login", "Login",
                "Đăng nhập không có mật khẩu phải hiển thị lỗi validation",
                "PASS" if passed else "FAIL",
                f"StayedOnLogin={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Empty Password Login", "Login",
                               "Đăng nhập mật khẩu trống", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_LOGIN_005_nonexistent_account(self):
        """LOG_03: Xác minh đăng nhập thất bại với tài khoản không tồn tại.
        
        Test ID hệ thống: LOG_03 (Feature_RL, hàng 27)
        Mục tiêu: Kiểm tra hệ thống từ chối đăng nhập với email chưa đăng ký.
        """
        start = time.time()     # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_005"  # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            # Điền email không tồn tại trong hệ thống
            self._fill_login_form("nonexistent_user_xyz@nowhere.com", "Test@1234")
            self._click_login_button()  # Nhấp đăng nhập
            time.sleep(2)              # Chờ phản hồi

            stayed = "login" in self.driver.current_url.lower()  # Kiểm tra vẫn ở trang đăng nhập
            page_text = self.driver.page_source.lower()
            # Kiểm tra thông báo lỗi tài khoản không tồn tại
            has_error = "invalid" in page_text or "lỗi" in page_text or "không hợp lệ" in page_text

            duration = time.time() - start
            passed = stayed or has_error  # Pass nếu hệ thống từ chối đăng nhập
            self.record_result(
                tc_id, "Non-existent Account Login", "Login",
                "Đăng nhập tài khoản không tồn tại phải hiển thị lỗi",
                "PASS" if passed else "FAIL",
                f"StayedOnLogin={stayed}, ErrorShown={has_error}",
                duration=duration
            )
            self.assertTrue(passed)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Non-existent Account Login", "Login",
                               "Tài khoản không tồn tại", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    # ─── Kiểm tra Giao diện Trang Đăng nhập ──────────────────────────────────

    def test_TC_LOGIN_UI_001_page_elements(self):
        """INT_02: Kiểm tra giao diện tổng thể trang đăng nhập.
        
        Test ID hệ thống: INT_02 (Feature_RL, hàng 17)
        Mục tiêu: Xác minh trang đăng nhập hiển thị đầy đủ các thành phần giao diện.
        """
        start = time.time()      # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_UI_001"  # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            page_text = self.driver.page_source  # Lấy HTML toàn trang

            # Kiểm tra tiêu đề trang đăng nhập
            has_heading = "Chào mừng" in page_text or "Login" in page_text or "Đăng nhập" in page_text
            
            # Kiểm tra số lượng trường nhập (tối thiểu 2: email và mật khẩu)
            inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
            has_inputs = len(inputs) >= 2
            
            # Kiểm tra nút submit đăng nhập
            btns = self.driver.find_elements(By.CSS_SELECTOR, "button[type='submit']")
            has_submit = len(btns) > 0
            
            # Kiểm tra liên kết đến trang đăng ký
            links = self.driver.find_elements(By.CSS_SELECTOR, "a")
            has_signup_link = any("signup" in (l.get_attribute("href") or "").lower() for l in links)
            # Kiểm tra liên kết quên mật khẩu
            has_forgot_link = any("forgot" in (l.get_attribute("href") or "").lower() for l in links)

            duration = time.time() - start
            all_ok = has_heading and has_inputs and has_submit and has_signup_link  # Tất cả phải đúng
            self.record_result(
                tc_id, "Login Page UI Elements", "Login UI",
                "Xác minh tất cả phần tử giao diện trang đăng nhập",
                "PASS" if all_ok else "FAIL",
                f"Heading={has_heading}, Inputs={len(inputs)}, Submit={has_submit}, "
                f"SignupLink={has_signup_link}, ForgotLink={has_forgot_link}",
                duration=duration
            )
            self.assertTrue(all_ok)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Login Page UI Elements", "Login UI",
                               "Xác minh phần tử trang đăng nhập", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise

    def test_TC_LOGIN_UI_002_forgot_password_link(self):
        """LOG_04: Xác minh chức năng liên kết Quên mật khẩu.
        
        Test ID hệ thống: LOG_04 (Feature_RL, hàng 28)
        Mục tiêu: Nhấp vào liên kết "Quên mật khẩu?" phải điều hướng đến trang tương ứng.
        """
        start = time.time()       # Ghi thời điểm bắt đầu
        tc_id = "TC_LOGIN_UI_002" # Mã test nội bộ

        try:
            self._navigate_to_login()  # Điều hướng trang đăng nhập
            links = self.driver.find_elements(By.CSS_SELECTOR, "a")  # Tìm tất cả liên kết
            forgot_link = None  # Biến lưu liên kết quên mật khẩu

            for link in links:  # Tìm liên kết "Quên mật khẩu"
                href = link.get_attribute("href") or ""
                text = link.text.lower()
                if "forgot" in href.lower() or "quên" in text:  # Tìm theo href hoặc văn bản
                    forgot_link = link
                    break

            if forgot_link:                    # Nếu tìm thấy liên kết
                self.safe_click(forgot_link)   # Nhấp liên kết
                time.sleep(2)                  # Chờ điều hướng
                current = self.driver.current_url
                navigated = "forgot" in current.lower()  # Kiểm tra đã đến trang quên mật khẩu
            else:
                navigated = False  # Không tìm thấy liên kết

            duration = time.time() - start
            self.record_result(
                tc_id, "Forgot Password Link", "Login UI",
                "Liên kết quên mật khẩu phải điều hướng đến trang đặt lại mật khẩu",
                "PASS" if navigated else "FAIL",
                f"ForgotLinkFound={forgot_link is not None}, Navigated={navigated}",
                duration=duration
            )
            self.assertTrue(navigated)

        except Exception as e:
            duration = time.time() - start
            ss = self.take_screenshot(tc_id)
            self.record_result(tc_id, "Forgot Password Link", "Login UI",
                               "Điều hướng liên kết quên mật khẩu", "ERROR", str(e),
                               screenshot_path=ss, duration=duration)
            raise


if __name__ == "__main__":
    unittest.main()  # Chạy test khi file được thực thi trực tiếp
