import os
import sys
import unittest
from unittest.mock import patch

import responses
from responses.matchers import query_string_matcher, urlencoded_params_matcher

from amazonorders.exception import AmazonOrdersAuthError
from amazonorders.session import AmazonSession, BASE_URL, SIGN_IN_URL
from tests.unittestcase import UnitTestCase

__author__ = "Alex Laird"
__copyright__ = "Copyright 2024, Alex Laird"
__version__ = "1.0.6"


class TestSession(UnitTestCase):
    def setUp(self):
        super().setUp()

        self.amazon_session = AmazonSession("some-username",
                                            "some-password")

    @responses.activate
    def test_login(self):
        # GIVEN
        self.given_login_responses_success()

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assert_login_responses_success()

    @responses.activate
    def test_login_invalid_username(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-invalid-email.html"), "r", encoding="utf-8") as f:
            resp2 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        with self.assertRaises(AmazonOrdersAuthError):
            self.amazon_session.login()

        # THEN
        self.assertFalse(self.amazon_session.is_authenticated)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)

    @responses.activate
    def test_login_invalid_password(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-invalid-password.html"), "r", encoding="utf-8") as f:
            resp2 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        with self.assertRaises(AmazonOrdersAuthError):
            self.amazon_session.login()

        # THEN
        self.assertFalse(self.amazon_session.is_authenticated)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)

    @responses.activate
    @patch('builtins.input')
    def test_mfa(self, input_mock):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-mfa.html"), "r", encoding="utf-8") as f:
            resp2 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "order-history-2018-0.html"), "r", encoding="utf-8") as f:
            resp3 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assertEqual(1, input_mock.call_count)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)
        self.assertEqual(1, resp3.call_count)

    @responses.activate
    @patch('builtins.input')
    def test_new_otp(self, input_mock):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-new-otp.html"), "r", encoding="utf-8") as f:
            resp2 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-mfa.html"), "r", encoding="utf-8") as f:
            resp3 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "order-history-2018-0.html"), "r", encoding="utf-8") as f:
            resp4 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assertEqual(2, input_mock.call_count)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)
        self.assertEqual(1, resp3.call_count)
        self.assertEqual(1, resp4.call_count)

    @responses.activate
    def test_captcha_1(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        resp2 = responses.add(
            responses.POST,
            SIGN_IN_URL,
            status=302,
            headers={"Location": "{}/ap/cvf/request".format(BASE_URL)}
        )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-captcha-1.html"), "r", encoding="utf-8") as f:
            resp3 = responses.add(
                responses.GET,
                "{}/ap/cvf/request".format(BASE_URL),
                body=f.read(),
                status=200
            )
        with open(os.path.join(self.RESOURCES_DIR, "captcha_easy.jpg"), "rb") as f:
            resp4 = responses.add(
                responses.GET,
                "https://opfcaptcha-prod.s3.amazonaws.com/d32ff4fa043d4f969a1693adfb5d663a.jpg",
                body=f.read(),
                headers={"Content-Type": "image/jpeg"},
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "order-history-2018-0.html"), "r", encoding="utf-8") as f:
            request_data = {
                "clientContext": "132-7968344-2156059",
                "cvf_captcha_captcha_action": "verifyCaptcha",
                "cvf_captcha_captcha_token": "sEusNpCt1AQ2rRr2f39/fwAAAAAAAAABPjglplbzE96xUsCT0ZswRq/pkFbblKXbv1cN6hKjq04HzZIYdTBAsdTA9fOZZZsAXG/6qLx8k6IQ8N5gpuIxjtQRhgYiPGzs/b0x0UO9BpFhRTd5JGaUlxx3NdvsaBvaaCDpiGc3E6pzcmhqzqGOuMYMNCP0hLh1u1c+y+6xpzgSr9UYDWHZ9da61HQ8B/ay90YCc5vbiH556wwYffTosLN9LJzCydLp+zzJ2gU1NjWfGyDYvIWYt2h6dCxxJe1jIztakaLnkkJhYQEzHZMC9az8M0S+Yr87/IMh0m9/QMERYs+/cDlUT4jVsqii1qEt/m7pfJMz3G4f",
                "cvf_captcha_captcha_type": "imageCaptcha",
                "cvf_captcha_input": "FBJRAC",
                "cvf_captcha_js_enabled_metric": "0",
                "openid.assoc_handle": "usflex",
                "openid.mode": "checkid_setup",
                "openid.ns": "http://specs.openid.net/auth/2.0",
                "openid.pape.max_auth_age": "900",
                "openid.return_to": "https://www.amazon.com?",
                "pageId": "usflex",
                "verifyToken": "s|71202aba-23dd-378a-9cb3-75f90b00933e"
            }
            resp5 = responses.add(
                responses.POST,
                "{}/ap/cvf/verify".format(BASE_URL),
                body=f.read(),
                status=200,
                match=[urlencoded_params_matcher(request_data)],
            )

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)
        self.assertEqual(1, resp3.call_count)
        self.assertEqual(1, resp4.call_count)
        self.assertEqual(1, resp5.call_count)

    @responses.activate
    def test_captcha_2(self):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-captcha-2.html"), "r", encoding="utf-8") as f:
            resp2 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "captcha_easy.jpg"), "rb") as f:
            resp3 = responses.add(
                responses.GET,
                "https://images-na.ssl-images-amazon.com/captcha/ddwwidnf/Captcha_gmwackhtzu.jpg",
                body=f.read(),
                headers={"Content-Type": "image/jpeg"},
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "order-history-2018-0.html"), "r", encoding="utf-8") as f:
            resp4 = responses.add(
                responses.GET,
                "{}/errors/validateCaptcha".format(BASE_URL),
                body=f.read(),
                status=200,
                match=[query_string_matcher(
                    "amzn=Ozn2ONrAzGQc1ZETILqvvA%3D%3D&amzn-r=%2Fap%2Fsignin%3Fopenid.pape.max_auth_age%3D900%26openid.return_to%3Dhttps%253A%252F%252Fwww.amazon.com%253F%26openid.assoc_handle%3Dusflex%26openid.mode%3Dcheckid_setup%26openid.ns%3Dhttp%253A%252F%252Fspecs.openid.net%252Fauth%252F2.0&amzn-pt=AuthenticationPortal&field-keywords=FBJRAC")],
            )

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)
        self.assertEqual(1, resp3.call_count)
        self.assertEqual(1, resp4.call_count)

    @unittest.skipIf(sys.platform == "win32", reason="Windows does not respect PIL's show() method in tests")
    @responses.activate
    @patch('builtins.input')
    def test_captcha_1_hard(self, input_mock):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        resp2 = responses.add(
            responses.POST,
            SIGN_IN_URL,
            status=302,
            headers={"Location": "{}/ap/cvf/request".format(BASE_URL)}
        )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-captcha-1.html"), "r", encoding="utf-8") as f:
            resp3 = responses.add(
                responses.GET,
                "{}/ap/cvf/request".format(BASE_URL),
                body=f.read(),
                status=200
            )
        with open(os.path.join(self.RESOURCES_DIR, "captcha_hard.jpg"), "rb") as f:
            resp4 = responses.add(
                responses.GET,
                "https://opfcaptcha-prod.s3.amazonaws.com/d32ff4fa043d4f969a1693adfb5d663a.jpg",
                body=f.read(),
                headers={"Content-Type": "image/jpeg"},
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "order-history-2018-0.html"), "r", encoding="utf-8") as f:
            resp5 = responses.add(
                responses.POST,
                "{}/ap/cvf/verify".format(BASE_URL),
                body=f.read(),
                status=200,
            )

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assertEqual(1, input_mock.call_count)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)
        self.assertEqual(1, resp3.call_count)
        self.assertEqual(2, resp4.call_count)
        self.assertEqual(1, resp5.call_count)

    @responses.activate
    @patch('builtins.input')
    def test_captcha_otp(self, input_mock):
        # GIVEN
        with open(os.path.join(self.RESOURCES_DIR, "signin.html"), "r", encoding="utf-8") as f:
            resp1 = responses.add(
                responses.GET,
                "{}/gp/sign-in.html".format(BASE_URL),
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "post-signin-captcha-otp.html"), "r", encoding="utf-8") as f:
            resp2 = responses.add(
                responses.POST,
                SIGN_IN_URL,
                body=f.read(),
                status=200,
            )
        with open(os.path.join(self.RESOURCES_DIR, "order-history-2018-0.html"), "r", encoding="utf-8") as f:
            resp3 = responses.add(
                responses.POST,
                "{}/ap/cvf/approval/verifyOtp".format(BASE_URL),
                body=f.read(),
                status=200,
            )

        # WHEN
        self.amazon_session.login()

        # THEN
        self.assertTrue(self.amazon_session.is_authenticated)
        self.assertEqual(1, input_mock.call_count)
        self.assertEqual(1, resp1.call_count)
        self.assertEqual(1, resp2.call_count)
        self.assertEqual(1, resp3.call_count)
