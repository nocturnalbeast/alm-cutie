#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import logging
from getpass import getuser
from yaml import safe_load as yaml_load
from json import loads as json_load
from rich.prompt import Confirm, Prompt

FALLBACK_PREFS = {
    "domain": "EXAMPLE",
    "webdomain": "http://localhost:8080",
    "project": "QA",
    "tests_folder": "Subject\\TestFolder",
    "https_strict": True,
}


class Preferences:
    def __init__(self, pref_file=None) -> None:
        # start everything as empty
        self.domain = None
        self.webdomain = None
        self.project = None
        self.tests_folder = None
        self.username = None
        self.password = None
        self.https_strict = None
        self.logger = logging.getLogger("cutie-preferences")
        # check if we actually have some value
        if pref_file is None:
            self.logger.warn("No config file provided, using fallback values.")
        else:
            # get absolute path for later use
            file_path = os.path.abspath(pref_file)
            # get extension
            file_path_ext = file_path.rsplit(".", 1)[1]
            # check if file exists
            if os.path.isfile(file_path):
                # handle YAML if that's the case
                if file_path_ext in ["yaml", "yml"]:
                    self.logger.info("Detected YAML file, getting config in YAML mode.")
                    with open(file_path, "r") as pref_file_handle:
                        pref_data = yaml_load(pref_file_handle)
                # handle JSON if that's the case
                elif file_path_ext == "json":
                    self.logger.info("Detected JSON file, getting config in JSON mode.")
                    with open(file_path, "r") as pref_file_handle:
                        pref_data = json_load(pref_file_handle.read())
                # handle unknown filetype
                else:
                    self.logger.error(
                        "Unknown filetype, please provide a YAML or a JSON file!"
                    )
                    pref_data = {}
                # iterate through data obtained from the file and assign to respective class instance vars
                for key in pref_data.keys():
                    if hasattr(self, key):
                        setattr(self, key, pref_data[key])
                    else:
                        self.logger.error(f"Unkown key {key}!")
            else:
                self.logger.error(
                    "Invalid path provided, please provide the valid path!"
                )
                return
        # handle values that aren't accessed via the above methods in fallback values/interactive mode
        for key in self.__dict__.keys():
            if getattr(self, key) is None:
                if key in FALLBACK_PREFS.keys():
                    self.logger.info(
                        f"Value for field {key} empty! Searching in fallback values."
                    )
                    setattr(self, key, FALLBACK_PREFS[key])
                else:
                    self.logger.info(
                        f"Value for field {key} empty and not found in fallback preferences, moving to interactive mode."
                    )
                    if key == "password":
                        self.password = Prompt.ask("Password", password=True)
                    elif key == "username":
                        username = getuser()
                        self.logger.info(
                            f"Autodetected username as {username} from system."
                        )
                        username_correct = Confirm.ask("Is this username correct?")
                        if username_correct:
                            self.username = username
                        else:
                            self.username = Prompt.ask("Username")
                    else:
                        setattr(self, key, Prompt.ask(f"{key.title()}"))
