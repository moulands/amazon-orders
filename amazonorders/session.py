import json
import logging
import os
from typing import Optional, Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag
from requests import Session, Response
from requests.utils import dict_from_cookiejar

from amazonorders import constants
from amazonorders.conf import DEFAULT_COOKIE_JAR_PATH, DEFAULT_OUTPUT_DIR
from amazonorders.exception import AmazonOrdersAuthError
from amazonorders.forms import SignInForm, MfaDeviceSelectForm, MfaForm, CaptchaForm

__author__ = "Alex Laird"
__copyright__ = "Copyright 2024, Alex Laird"
__version__ = "1.0.8"

logger = logging.getLogger(__name__)

AUTH_FORMS = [SignInForm(),
              MfaDeviceSelectForm(),
              MfaForm(),
              CaptchaForm(),
              CaptchaForm(constants.CAPTCHA_2_FORM_SELECTOR, constants.CAPTCHA_2_ERROR_SELECTOR, "field-keywords"),
              MfaForm(constants.CAPTCHA_OTP_FORM_SELECTOR)]


class IODefault:
    """
    Handles input/output from the application. By default, this uses console commands, but
    this class exists so that it can be overriden when constructing an :class:`AmazonSession`
    if input/output should be handled another way.
    """

    def echo(self,
             msg: str,
             **kwargs: Any):
        """
        Echo a message to the console.

        :param msg: The data to send to output.
        :param kwargs: Unused by the default implementation.
        """
        print(msg)

    def prompt(self,
               msg: str,
               type: str = None,
               **kwargs: Any):
        """
        Prompt to the console for user input.

        :param msg: The data to use as the input prompt.
        :param type: Unused by the default implementation.
        :param kwargs: Unused by the default implementation.
        :return: The user input result.
        """
        return input("{}: ".format(msg))


class AmazonSession:
    """
    An interface for interacting with Amazon and authenticating an underlying :class:`requests.Session`. Utilizing
    this class means session data is maintained between requests. Session data is also persisted after each request,
    meaning it will also be maintained between separate instantiations of the class or application.

    To get started, call the :func:`login` function.
    """

    def __init__(self,
                 username: str,
                 password: str,
                 debug: bool = False,
                 max_auth_attempts: int = 10,
                 cookie_jar_path: str = None,
                 io: IODefault = IODefault(),
                 output_dir: str = None) -> None:
        if not cookie_jar_path:
            cookie_jar_path = DEFAULT_COOKIE_JAR_PATH
        if not output_dir:
            output_dir = DEFAULT_OUTPUT_DIR

        #: An Amazon username.
        self.username: str = username
        #: An Amazon password.
        self.password: str = password

        #: Set logger ``DEBUG``, send output to ``stderr``, and write an HTML file for each request made on the session.
        self.debug: bool = debug
        if self.debug:
            logger.setLevel(logging.DEBUG)
        #: Will continue in :func:`login`'s auth flow this many times (successes and failures).
        self.max_auth_attempts: int = max_auth_attempts
        #: The path to persist session cookies, defaults to ``conf.DEFAULT_COOKIE_JAR_PATH``.
        self.cookie_jar_path: str = cookie_jar_path
        #: The I/O handler for echoes and prompts.
        self.io: IODefault = io
        #: The directory where any output files will be produced, defaults to ``conf.DEFAULT_OUTPUT_DIR``.
        self.output_dir = output_dir

        #: The shared session to be used across all requests.
        self.session: Session = Session()
        #: The last response executed on the Session.
        self.last_response: Optional[Response] = None
        #: A parsed representation of the last response executed on the Session.
        self.last_response_parsed: Optional[Tag] = None
        #: If :func:`login` has been executed and successfully logged in the session.
        self.is_authenticated: bool = False

        cookie_dir = os.path.dirname(self.cookie_jar_path)
        if not os.path.exists(cookie_dir):
            os.makedirs(cookie_dir)
        if os.path.exists(self.cookie_jar_path):
            with open(self.cookie_jar_path, "r", encoding="utf-8") as f:
                data = json.loads(f.read())
                cookies = requests.utils.cookiejar_from_dict(data)
                self.session.cookies.update(cookies)

    def request(self,
                method: str,
                url: str,
                **kwargs: Any) -> Response:
        """
        Execute the request against Amazon with base headers, parsing and storing the response
        and persisting response cookies.

        :param method: The request method to execute.
        :param url: The URL to execute ``method`` on.
        :param kwargs: Remaining ``kwargs`` will be passed to :func:`requests.request`.
        :return: The Response from the executed request.
        """
        if "headers" not in kwargs:
            kwargs["headers"] = {}
        kwargs["headers"].update(constants.BASE_HEADERS)

        logger.debug("{} request to {}".format(method, url))

        self.last_response = self.session.request(method, url, **kwargs)
        self.last_response_parsed = BeautifulSoup(self.last_response.text,
                                                  "html.parser")

        cookies = dict_from_cookiejar(self.session.cookies)
        if os.path.exists(self.cookie_jar_path):
            os.remove(self.cookie_jar_path)
        with open(self.cookie_jar_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(cookies))

        logger.debug("Response: {} - {}".format(self.last_response.url,
                                                self.last_response.status_code))

        if self.debug:
            page_name = self._get_page_from_url(self.last_response.url)
            with open(os.path.join(self.output_dir, page_name), "w",
                      encoding="utf-8") as html_file:
                logger.debug(
                    "Response written to file: {}".format(html_file.name))
                html_file.write(self.last_response.text)

        return self.last_response

    def get(self,
            url: str,
            **kwargs: Any):
        """
        Perform a GET request.

        :param url: The URL to GET on.
        :param kwargs: Remaining ``kwargs`` will be passed to :func:`AmazonSession.request`.
        :return: The Response from the executed GET request.
        """
        return self.request("GET", url, **kwargs)

    def post(self,
             url,
             **kwargs: Any) -> Response:
        """
        Perform a POST request.

        :param url: The URL to POST on.
        :param kwargs: Remaining ``kwargs`` will be passed to :func:`AmazonSession.request`.
        :return: The Response from the executed POST request.
        """
        return self.request("POST", url, **kwargs)

    def auth_cookies_stored(self):
        cookies = dict_from_cookiejar(self.session.cookies)
        return cookies.get("session-token") and cookies.get("x-main")

    def login(self) -> None:
        """
        Execute an Amazon login process. This will include the sign-in page, and may also include Captcha challenges
        and OTP pages (of 2FA authentication is enabled on your account).

        If successful, ``is_authenticated`` will be set to ``True``.

        Session cookies are persisted, and if existing session data is found during this auth flow, it will be
        skipped entirely and flagged as authenticated.
        """
        self.get(constants.SIGN_IN_URL)

        # If our local session data is stale, Amazon will redirect us to the signin page
        if self.auth_cookies_stored() and self.last_response.url.split("?")[0] == constants.SIGN_IN_REDIRECT_URL:
            self.logout()
            self.get(constants.SIGN_IN_URL)

        attempts = 0
        while not self.is_authenticated and attempts < self.max_auth_attempts:
            # TODO: BeautifulSoup doesn't let us query for #nav-item-signout, maybe because it's dynamic on the page, but we should find a better way to do this
            if self.auth_cookies_stored() or \
                    ("Hello, sign in" not in self.last_response.text and
                     "nav-item-signout" in self.last_response.text):
                self.is_authenticated = True
                break

            form_found = False
            for form in AUTH_FORMS:
                if form.select_form(self, self.last_response_parsed):
                    form_found = True

                    form.fill_form()
                    form.submit()

                    break

            if not form_found:
                debug_str = " To capture the page to a file, set the `debug` flag." if not self.debug else ""
                if self.last_response.ok:
                    raise AmazonOrdersAuthError(
                        "An error occurred, this is an unknown page, or its parsed contents don't match a known auth flow: {}.{}".format(
                            self.last_response.url, debug_str))
                elif 400 <= self.last_response.status_code < 500:
                    raise AmazonOrdersAuthError(
                        "An error occurred, the page {} returned {}.{}".format(self.last_response.url, debug_str))
                elif 500 <= self.last_response.status_code < 600:
                    raise AmazonOrdersAuthError(
                        "An error occurred, the page {} returned {}, which Amazon had an error (or may be temporarily blocking your requests). Wait a bit before trying again.{}".format(
                            self.last_response.url, debug_str))

            attempts += 1

        if attempts == self.max_auth_attempts:
            raise AmazonOrdersAuthError(
                "Max authentication flow attempts reached.")

    def logout(self) -> None:
        """
        Logout and close the existing Amazon session and clear cookies.
        """
        self.get(constants.SIGN_OUT_URL)

        if os.path.exists(self.cookie_jar_path):
            os.remove(self.cookie_jar_path)

        self.session.close()
        self.session = Session()

        self.is_authenticated = False

    def _get_page_from_url(self,
                           url: str) -> str:
        page_name = os.path.basename(urlparse(url).path).strip(".html")
        i = 0
        while os.path.isfile("{}_{}.html".format(page_name, i)):
            i += 1
        return "{}_{}.html".format(page_name, i)
