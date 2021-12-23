#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ---------------------------------------------------------------------------
# author  : nocturnalbeast
# version : '1.1-multi'
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
from datetime import datetime
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, SpinnerColumn
from rich.prompt import Confirm

from class_def.alm import ALMConnection, ALMTestMapping
from class_def.configuration import ConfigStore, write_default_config
from libs.email import prepare_email, send_email
from libs.pathops import is_path_exists_or_creatable


# this is an ALM-defined parameter - so it is kept as a global constant
# it can go lower, but not higher the max value set in the server,
# which is usually 100
QUERY_RESULT_MAX_PER_REQUEST = 100

# this is a user-defined param - tells the script how many connections
# to make to the server in parallel
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
        test_field_dict.get(mapping[key])
        if mapping[key] != "description"
        else BeautifulSoup(test_field_dict.get(mapping[key], ""), features="lxml").text
        for key in mapping.keys()
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
        metavar="OUTPUT_FILE",
        help="The Excel file to output to.",
    )
    exec_args.add_argument(
        "-p",
        "--preferences",
        action="store",
        type=str,
        metavar="PREFERENCES_FILE",
        help="Path to the preferences file (YAML).",
    )
    exec_args.add_argument(
        "-e",
        "--email",
        action="store_true",
        help="Enables sending an email containing the export once script finishes.",
    )
    other_args.add_argument(
        "-g",
        "--generate_preferences",
        action="store_true",
        help="Generate a default preferences.yaml file to be customized.",
    )
    other_args.add_argument("-h", "--help", action="help", help="Show this cruft.")
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        exit(0)
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

    # check if the generate_preferences flag is set, if yes then call the configuration method to do the same, and exit
    if args.generate_preferences:
        write_default_config(os.getcwd() + os.path.sep + "preferences.yaml")
        exit(0)

    # handle output file shennanigans before proceeding
    if args.output is not None:
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
                    output_file_path = (
                        output_file_path + os.path.sep + "cutie_output.xlsx"
                    )
                else:
                    log.error("Unknown error in path specified!")
                    exit(3)
        else:
            log.error("Invalid path and/or insufficient permissions to the path.")
            exit(4)
    else:
        timestamp = datetime.strftime(datetime.now(), "%Y_%m_%d_%H_%M")
        output_file_path = os.path.abspath(
            f"{os.getcwd()}{os.path.sep}export_{timestamp}.xlsx"
        )

    # check preferences file existence, else use fallback/interactive preferences
    if args.preferences is not None:
        preferences_file_path = os.path.abspath(args.preferences)
        if is_path_exists_or_creatable(preferences_file_path) and os.path.isfile(
            preferences_file_path
        ):
            log.info("Preferences file found, attempting to retrieve preferences.")
            pref = ConfigStore(preferences_file_path)
        else:
            log.error("Error in path specified!")
            exit(5)
    else:
        log.error(
            f'No preferences file specified! Use the command "{os.path.basename(__file__)}" -g to generate a default configuration file!'
        )
        exit(6)

    # create an authenticated connection using the preferences obtained
    alm_conn = ALMConnection()
    alm_conn.authenticate(
        pref.alm.webdomain, pref.alm.username, pref.alm.password, pref.alm.https_strict
    )

    # use the raw data from the preferences to generate the mapping instance
    test_mapping = ALMTestMapping(
        pref.raw_data["mapping"].keys(), pref.raw_data["mapping"]
    )

    # setting up some common stuff
    tests_baseurl = f"{pref.alm.webdomain}/qcbin/rest/domains/{pref.alm.domain}/projects/{pref.alm.project}/tests"
    req_headers_for_json = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    # dummy test retrieval to get the number of tests
    res = alm_conn.session.get(
        tests_baseurl, verify=pref.alm.https_strict, headers=req_headers_for_json
    )
    test_count = json.loads(res.content).get("TotalResults")
    if not isinstance(test_count, int):
        log.error("Failed to get test case count! Exiting now.")
        exit(5)
    else:
        log.info(f"Found {test_count} testcases!")

    # initialize header for result list
    all_tests = [test_mapping.mapping_order]

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
                    test_mapping.mapping,
                    tests_baseurl,
                    index,
                    pref.alm.https_strict,
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
                except Exception:
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

    # handle email
    if args.email:
        from_address, subject, content = prepare_email(pref.email.sender_domain)
        log.info(
            f"Sending email has been enabled - sending from address {from_address}..."
        )
        status = send_email(
            from_address,
            pref.email.to_list,
            pref.email.cc_list,
            pref.email.smtp_host,
            pref.email.smtp_port,
            subject,
            content,
            output_file_path,
        )
        if status:
            log.info("Email sent successfully.")
        else:
            log.error("Error encountered in sending email!")


if __name__ == "__main__":
    main()
