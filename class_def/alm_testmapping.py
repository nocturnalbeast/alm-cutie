#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import yamlloader
from collections import OrderedDict
from json import loads as json_load
from yaml import load as yaml_load

FALLBACK_MAPPING = OrderedDict(
    {
        "Feature code": "user-12",
        "Test case ID": "user-10",
        "Test name": "name",
        "Creation date": "creation-time",
        "Type": "subtype-id",
        "Test mode": "user-09",
        "Test level": "user-06",
        "Test execution time": "user-13",
        "Requirement ID": "user-14",
        "Config interface": "user-01",
        "IP version": "user-05",
        "LAN interface": "user-02",
        "ALM internal ID": "id",
        "WAN connection": "user-04",
        "WAN mode": "user-03",
        "Test title": "user-16",
        "Test type": "user-15",
        "Owner": "owner",
        "Description": "description",
    }
)


class ALMTestMapping:
    def __init__(self, mapping_file=None) -> None:
        # start everything as empty
        self.data = OrderedDict()
        self.logger = logging.getLogger("cutie-mapping")
        # check if we actually have some value
        if mapping_file is None:
            self.logger.warn("No mapping file provided, using fallback values.")
        else:
            # get absolute path for later use
            file_path = os.path.abspath(mapping_file)
            # get extension
            file_path_ext = file_path.rsplit(".", 1)[1]
            # check if file exists
            if os.path.isfile(file_path):
                # handle YAML if that's the case
                if file_path_ext in ["yaml", "yml"]:
                    self.logger.info(
                        "Detected YAML file, getting mapping in YAML mode."
                    )
                    with open(file_path, "r") as pref_file_handle:
                        self.data = yaml_load(
                            pref_file_handle, Loader=yamlloader.ordereddict.CLoader
                        )
                # handle JSON if that's the case
                elif file_path_ext == "json":
                    self.logger.info("Detected JSON file, getting config in JSON mode.")
                    with open(file_path, "r") as pref_file_handle:
                        # python 3.7+ preserves order - so no need to add object_pairs_hook
                        self.data = json_load(pref_file_handle.read())
                # handle unknown filetype
                else:
                    self.logger.error(
                        "Unknown filetype, please provide a YAML or a JSON file!"
                    )
            else:
                self.logger.error("Invalid path provided, using fallback mapping.")
        # by this point, if mapping of the class instance is empty, then that means we've failed somewhere
        # and need to assign the default/fallback mapping
        if len(self.data.items()) == 0:
            self.data = FALLBACK_MAPPING
