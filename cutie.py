#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# created by   : nocturnalbeast
# created date : 17/12/2021
# version      : '1.0-multi'
# ---------------------------------------------------------------------------

"""
This is a script that is used to export all the tests from a QC ALM test plan
using the REST API.

Usage:
  python cutie.py [-o/--output OUTPUT_FILE] [-m/--mapping MAPPING_FILE]
  [-p/--preferences PREFERENCES_FILE] [-h/--help]

Requirements:
  rich
  beautifulsoup4
  requests
  xlsxwriter
  lxml
  yaml
  yamlloader
"""

import argparse
import concurrent.futures
import json
import logging
import os
import sys
import xlsxwriter
from bs4 import BeautifulSoup
from rich import print
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, SpinnerColumn
from rich.prompt import Confirm

from class_def.alm import ALMConnection
from class_def.alm_testmapping import ALMTestMapping
from class_def.preferences import Preferences
from libs.pathops import is_path_exists_or_creatable


# this is an ALM-defined parameter - so it is kept as a global constant
# it can go lower, but not higher the max value set in the server,
# which is usually 100
QUERY_RESULT_MAX_PER_REQUEST = 100

# this is a user-defined param - tells the script how many connections
# to make to the server parallelly
MAX_CONNECTION_THREADS = 5


def map_entity_to_test(unprocessed_test_dict, mapping) -> list:
    test_field_dict = {}
    for field in unprocessed_test_dict.get("Fields"):
        key = field.get("Name")
        all_values = field.get("values")
        if len(all_values) == 1:
            value = all_values[0].get("value")
            if value is None:
                continue
            test_field_dict[key] = value
        else:
            continue
    # create test record from the mapping
    return [
        test_field_dict.get(mapping.data[key])
        if mapping.data[key] != "description"
        else BeautifulSoup(
            test_field_dict.get(mapping.data[key], ""), features="lxml"
        ).text
        for key in mapping.data.keys()
    ]


def fetch_test_from_index(
    authed_session, mapping, baseurl, index, https_strict
) -> list:
    mapped_tests = []
    log = logging.getLogger("cutie-task")
    log.info(
        f"Attempting to get {QUERY_RESULT_MAX_PER_REQUEST} tests from index {index}..."
    )
    res = authed_session.get(
        f"{baseurl}?order-by={{id[ASC]}}&page-size={QUERY_RESULT_MAX_PER_REQUEST}&start-index={index}",
        verify=https_strict,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )

    if res.status_code != 200:
        log.error(
            f"Failed to get some tests from ALM (index: {index}, max_result: {QUERY_RESULT_MAX_PER_REQUEST})."
        )
        return None
    # parse the results into a simpler format by using the mapper function
    entities = json.loads(res.content)
    unmapped_tests = entities.get("entities")
    for test in unmapped_tests:
        mapped_tests.append(map_entity_to_test(test, mapping))
    return mapped_tests


def main():
    # build option parser
    parser = argparse.ArgumentParser(
        prog=os.path.basename(__file__),
        description="CUTIE: Python tool to export all the tests from QC ALM.",
        add_help=False,
    )
    exec_args = parser.add_argument_group("Run-specific arguments")
    other_args = parser.add_argument_group("Other arguments")
    exec_args.add_argument(
        "-o",
        "--output",
        action="store",
        type=str,
        required=True,
        metavar="OUTPUT_FILE",
        help="The Excel file to output to.",
    )
    exec_args.add_argument(
        "-m",
        "--mapping",
        action="store",
        type=str,
        metavar="MAPPING_FILE",
        help="The user-defined mapping file that specifies the fields and the relevant column headers (can be YAML/JSON).",
    )
    exec_args.add_argument(
        "-p",
        "--preferences",
        action="store",
        type=str,
        metavar="PREFERENCES_FILE",
        help="The preferences file that contains the ALM server info (can be YAML/JSON).",
    )
    other_args.add_argument("-h", "--help", action="help", help="Show this cruft.")
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()

    # setup logging
    logging.basicConfig(
        level="NOTSET",
        format="| %(message)s",
        datefmt="[%x %X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True, show_path=False, omit_repeated_times=False
            )
        ],
    )
    log = logging.getLogger("cutie-main")
    log.info("Started CUTIE!")

    # handle output file shennanigans before proceeding
    output_file_path = os.path.abspath(args.output)
    if is_path_exists_or_creatable(output_file_path):
        if os.path.exists(output_file_path):
            if os.path.isfile(output_file_path):
                if Confirm.ask(
                    "Existing file found at the path mentioned. Shall I delete it?"
                ):
                    os.unlink(output_file_path)
                else:
                    log.error(
                        "You have cancelled deletion of the file at the path mentioned. Please re-run the script with another path/filename.",
                    )
                    exit(2)
            elif os.path.isdir(output_file_path):
                output_file_path = output_file_path + os.path.sep + "cutie_output.xlsx"
            else:
                log.error("Unknown error in path specified!")
                exit(3)
    else:
        log.error("Invalid path and/or insufficient permissions to the path.")
        exit(4)

    # check preferences file existence, else use fallback/interactive preferences
    if args.preferences is not None:
        preferences_file_path = os.path.abspath(args.preferences)
        if is_path_exists_or_creatable(preferences_file_path) and os.path.isfile(
            preferences_file_path
        ):
            log.info("Preferences file found, attempting to retrieve preferences.")
            pref = Preferences(preferences_file_path)
        else:
            log.warning("Error in path specified!")
            pref = Preferences()
    else:
        log.warning("No preferences file specified!")
        pref = Preferences()

    # check mapping file existence, else use fallback mapping
    if args.mapping is not None:
        mapping_file_path = os.path.abspath(args.mapping)
        if is_path_exists_or_creatable(mapping_file_path) and os.path.isfile(
            mapping_file_path
        ):
            log.info("Mapping file found, attempting to retrieve mapping.")
            mapping = ALMTestMapping(mapping_file_path)
        else:
            log.warning("Error in path specified!")
            mapping = ALMTestMapping()
    else:
        log.warning("No mapping file specified!")
        mapping = ALMTestMapping()

    # create an authenticated connection using the preferences obtained
    alm_conn = ALMConnection()
    alm_conn.authenticate(pref)

    # setting up some common stuff
    tests_baseurl = f"{pref.webdomain}/qcbin/rest/domains/{pref.domain}/projects/{pref.project}/tests"
    req_headers_for_json = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # dummy test retrieval to get the number of tests
    res = alm_conn.session.get(
        tests_baseurl, verify=pref.https_strict, headers=req_headers_for_json
    )
    test_count = json.loads(res.content).get("TotalResults")
    if not isinstance(test_count, int):
        log.error("Failed to get test case count! Exiting now.")
        exit(5)
    else:
        log.info(f"Found {test_count} testcases!")

    # initialize header for result list
    all_tests = [mapping.data.keys()]

    # start progress bar
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(bar_width=80),
        "[progress.percentage]{task.percentage:>3.0f}%",
        SpinnerColumn(),
    ) as progress:
        fetch_test_task = progress.add_task(
            "[cyan]Fetching tests from ALM:", total=test_count
        )

        # initialize pool of threads
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_CONNECTION_THREADS
        ) as executor:
            # start fetch tasks
            futures = [
                executor.submit(
                    fetch_test_from_index,
                    alm_conn.session,
                    mapping,
                    tests_baseurl,
                    index,
                    pref.https_strict,
                )
                for index in range(1, test_count, QUERY_RESULT_MAX_PER_REQUEST)
            ]
            for future in futures:
                if future.cancelled():
                    continue
                try:
                    task_result = future.result()
                    if task_result is not None:
                        all_tests += task_result
                except Exception as e:
                    log.error("Error trying to get task result!")
                finally:
                    # advance by max query answers even in case of partial/error response
                    progress.update(
                        fetch_test_task, advance=QUERY_RESULT_MAX_PER_REQUEST
                    )

    # finally write to output file
    with xlsxwriter.Workbook(output_file_path) as workbook:
        worksheet = workbook.add_worksheet()
        for idx, data in enumerate(all_tests):
            worksheet.write_row(idx, 0, data)


if __name__ == "__main__":
    main()
