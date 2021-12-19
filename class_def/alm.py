#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
from urllib3.exceptions import InsecureRequestWarning

QC_URL_IS_AUTHENTICATED = "qcbin/rest/is-authenticated"
QC_URL_AUTHENTICATE = "qcbin/authentication-point/alm-authenticate"
QC_URL_SITE_SESSION = "qcbin/rest/site-session"


class ALMConnection:

    session = None

    def __init__(self, session=None) -> None:
        # check if we have a pre-authed session
        if session is not None:
            self.session = session

    def authenticate(self, preferences):
        # disable insecure request warnings if asked for
        if not preferences.https_strict:
            requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)
        # create a session
        s = requests.session()
        # check if already authenticated
        is_authed = s.get(
            f"{preferences.webdomain}/{QC_URL_IS_AUTHENTICATED}",
            verify=preferences.https_strict,
        )
        # if not then authenticate
        if is_authed.status_code != 200:
            login_user = s.post(
                f"{preferences.webdomain}/{QC_URL_AUTHENTICATE}",
                data=f"<alm-authentication><user>{preferences.username}</user><password>{preferences.password}</password></alm-authentication>",
                headers={
                    "Accept": "application/xml",
                    "Content-Type": "application/xml",
                },
                verify=preferences.https_strict,
            )
            if login_user.status_code not in [200, 201]:
                return
        session_create = s.post(
            f"{preferences.webdomain}/{QC_URL_SITE_SESSION}",
            verify=preferences.https_strict,
        )
        if session_create.status_code not in [200, 201]:
            return
        # set session in class instance var if everything's fine
        self.session = s
