"""Module holding engine utility functions"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import psycopg2
import re
import time
import ssl
import errno
import http
from uuid import uuid4
from typing import List, Optional, Dict, Any
import subprocess
# from uhm.hosts.linux import linux_host
from shared.log import get_logger
import vaultInteraction.vaultInteraction as vi
from datetime import datetime
import pytz
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from . import config as conf
import shared.database as db
from shared import ldap
import uuid
import traceback
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from email.mime.application import MIMEApplication

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

logger = get_logger(__name__)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

BASE_URL = 'http://ibid.usd.lab.emc.com/api/'
PRODUCT_FAMILY = 'Cyclone'

BASE_XPOOL_CMD = '/home/public/scripts/xpool_trident/prd/xpool'
XPOOL_LIST_CND = '/home/public/scripts/xpool_trident/prd/xpool list -x -a'

VICTORY_PLUS = "Victory-Plus V4.1.0"
BAZELET = "IRC-1 V4.2.0 Bazelet"


def rest_decorator(f, num_of_retry=5, sleep_duration=3):
    """Decorator function to handle vCenter exceptions

    :param f: function to be decorated
    :type f: function
    :param num_of_retry: number of retries in case the system is busy
    :type num_of_retry: int
    :param sleep_duration: time to wait between retries in seconds
    :type sleep_duration: int
    """

    def inner(self, *args, **kwargs):
        """
        Wrapper function that retries the decorated function
        in case of exceptions.
        """
        out = None
        for attempt in range(num_of_retry):
            try:
                out = f(self, *args, **kwargs)
                return out
            except (http.client.BadStatusLine, ssl.SSLError) as e:
                logger.warning(
                    f"REST connection failed with error: {type(e).__name__}. "
                    f"Retrying in {sleep_duration} seconds... (Attempt {attempt + 1}/{num_of_retry})"
                )
                time.sleep(sleep_duration)
            except IOError as e:
                if e.errno == errno.EPIPE:
                    logger.warning(
                        f"Connection failed with error: Broken pipe. "
                        f"Retrying in {sleep_duration} seconds... (Attempt {attempt + 1}/{num_of_retry})"
                    )
                    time.sleep(sleep_duration)
                else:
                    # If it's an IOError other than EPIPE, re-raise it
                    raise e
            except Exception as e:
                if "401" in str(e) or '500' in str(e) and hasattr(self, 'password'):
                    logger.debug(f'Got error {str(e)}, going to get and use new password')
                    self.password = get_jenkins_password(self.url)
                else:
                    logger.debug(f'Got error {str(e)}')
                    raise e

        # If all retries fail, log a final error message
        logger.error(f"All {num_of_retry} retries failed for function '{f.__name__}'")
        return out

    return inner


def get_main_parameters(testinit_stamp):
    """
    Retrieves main parameters from rundata.txt by fetching the artifacts_link
    from the run_data JSON column in the testinit_stamp table.

    :param testinit_stamp: The unique stamp to query the testinit_stamp table.
    :type testinit_stamp: str
    :return: A dictionary of key-value pairs (HBA_SETUP/(INSTALLATION/NDU)/PREFILL).
    :rtype: dict or str
    """
    post_db = db.PostgresDB(**conf.PERF_PARAMS)

    try:
        post_db.connect()

        query_result = post_db.select(
            table=conf.TESTINIT_STAMP,
            columns=["run_data"],
            where={"stamp": testinit_stamp},
            to_dict=True
        )

        if not query_result:
            logger.warning(f"No record found for testinit_stamp: {testinit_stamp}")
            return {"error": "No data found"}

        run_data = query_result[0].get("run_data", {})
        run_data = json.loads(run_data) if not isinstance(run_data, dict) else run_data

        # Step 2: Extract artifacts_link
        artifacts_link = run_data.get("artifacts_link")
        if not artifacts_link:
            logger.warning(f"No artifacts_link found in run_data for stamp: {testinit_stamp}")
            return {"error": "artifacts_link not found"}

        # Step 3: Fetch rundata.txt
        response = requests.get(f"{artifacts_link}/rundata.txt")
        response.raise_for_status()

        # Step 4: Parse rundata.txt
        hba_setup, installation_ndu, prefill = None, None, None
        for line in response.text.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                if key == 'HBA_SETUP':
                    hba_setup = value
                elif key == 'Installation_result':
                    installation_ndu = 'installation'
                elif key == 'NDU_result':
                    installation_ndu = 'ndu'
                elif key == 'POST_PREFILL_CAPACITY':
                    prefill = value
        parameters = {}
        if hba_setup:
            parameters['HBA_SETUP'] = hba_setup
        if installation_ndu:
            parameters['INSTALLATION_NDU'] = installation_ndu
        if prefill:
            parameters['PREFILL'] = prefill
        return parameters

    except Exception as e:
        logger.error(f"Error in get_main_parameters for stamp {testinit_stamp}: {e}")
        return {"error": str(e)}

    finally:
        post_db.disconnect()


def get_test_cases_by_ibid(ibid):
    """
    Retrieve test case names associated with a specific ibid.

    :param ibid: The ibid value to filter test cases.
    :type ibid: int
    :return: A list of test case names.
    :rtype: list
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        query_result = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            columns=["test_case_name", "test_case_status"],
            where={"ibid": ibid},
            to_dict=True
        )

        test_cases = [
            record.get("test_case_name")
            for record in query_result
            if record.get("test_case_status")
        ]

        logger.info(f"Retrieved {len(test_cases)} test case(s) for ibid {ibid}.")
        return test_cases

    except Exception as e:
        logger.error(f"Error retrieving test cases for ibid {ibid}: {e}")
        return []
    finally:
        post_db.disconnect()


def extract_release_name(release):
    """
    Extract the exact release name from the release string.

    The release name is identified as the last sequence of words or hyphenated words
    without numbers in the string.
    Example: 'IRC-1 V4.2.0 Bazelet' -> 'Bazelet'
             'Victory-Plus V4.1.0' -> 'Victory-Plus'

    :param release: The release string to parse.
    :type release: str
    :return: The extracted release name.
    :rtype: str
    """
    match = re.findall(r'\b[A-Za-z]+(?:-[A-Za-z]+)*\b', release)

    if match:
        return match[-1]

    return "Unknown"


def _find_release(filter_text):
    """
    Helper function to determine the release from the provided filter text.

    :param filter_text: The filter text provided with the query.
    :type filter_text: str
    :return: The exact release string if found, otherwise an empty string.
    :rtype: str
    """
    patterns = [
        (r"victory[\s\-]?plus", "Victory-Plus V4.1.0"),
        (r"irc[\s\-]?1", "IRC-1 V4.2.0 Bazelet"),
        (r"bazelet", "IRC-1 V4.2.0 Bazelet")
    ]

    filter_text_lower = filter_text.lower()

    for pattern, release in patterns:
        if re.search(pattern, filter_text_lower):
            return release

    # Default return if no match is found
    return ""


def _update_job_status(test_set_name, test_case_name, build_number, job_name, new_status):
    """
    Update the status of a specific job within a test case in the 'test_case_execution' table.

    :param test_set_name: The test set execution name (Primary Key).
    :type test_set_name: str
    :param test_case_name: The name of the test case to update (e.g., "TC-123").
    :type test_case_name: str
    :param build_number: The build number of the job.
    :type build_number: int
    :param job_name: The name of the job.
    :type job_name: str
    :param new_status: The new status to be set for the job (e.g., "SUCCESS", "FAILURE").
    :type new_status: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Retrieve the current job status
        records = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            columns=["job_status"],
            where={
                "test_set_name": test_set_name,
                "test_case_name": test_case_name,
                "build_number": build_number,
                "job_name": job_name
            },
            to_dict=True
        )

        if not records:
            logger.warning(f"No matching job found for test case '{test_case_name}', build {build_number}, "
                           f"job '{job_name}'.")
            return

        current_status = records[0]["job_status"]
        if current_status and current_status.lower() == new_status.lower():
            logger.debug(f"Job status for test case '{test_case_name}', build {build_number}, job '{job_name}' "
                         f"is already '{new_status}', skipping update.")
            return

        # Update the job status
        post_db.update(
            table=conf.TEST_SET_EXECUTION,
            data={"job_status": new_status},
            where={
                "test_set_name": test_set_name,
                "test_case_name": test_case_name,
                "build_number": build_number,
                "job_name": job_name
            }
        )

        logger.info(f"Updated job status for test case '{test_case_name}', build {build_number}, "
                    f"job '{job_name}' to '{new_status}'.")

    except Exception as e:
        logger.error(f"Error updating job status for test case '{test_case_name}', build {build_number}, "
                     f"job '{job_name}': {e}")

    finally:
        post_db.disconnect()


def get_test_cases_status_dict(test_set_name):
    """
    Retrieve a dictionary of dictionaries from the test_case_execution table,
    where the key of the outer dictionary is the test case ID (e.g., "TC-123"),
    and the inner dictionary contains information about whether the test case
    is 'in progress' or not, filtered by a specific test_set_name.

    :param test_set_name: The name of the test set to filter the results.
    :type test_set_name: str
    :return: A dictionary where keys are test case IDs and values are dictionaries
             indicating whether the test case is 'in progress' or not.
    :rtype: dict
    """
    result_dict = {}
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Query the database
        records = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            columns=["test_case_name", "job_status", "test_case_status"],
            where={"test_set_name": test_set_name},
            to_dict=True
        )

        for record in records:
            test_case_name = record["test_case_name"]
            job_status = record.get('job_status', '')
            test_case_status = record.get('test_case_status')
            in_progress = job_status.lower() == "in progress" if job_status and not test_case_status else False

            # Add the test case to the result dictionary
            if test_case_name:
                if test_case_name not in result_dict:
                    result_dict[test_case_name] = {'in_progress': False}

                # If any job for the test case is in progress, mark it as such
                if in_progress:
                    result_dict[test_case_name]['in_progress'] = True

                if test_case_status:
                    result_dict[test_case_name]['status'] = test_case_status

    except Exception as e:
        logger.error(f"Error retrieving test case statuses: {e}")
    finally:
        post_db.disconnect()

    return result_dict


def _update_test_run_latest_status(run_id, test_case_status):
    """
    Updates the latest run status and the status in the properties JSON field for a given test run.

    :param run_id: The unique ID of the test run to update.
    :type run_id: int
    :param test_case_status: The new test case status (e.g., "Passed", "Failed").
    :type test_case_status: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Fetch the current properties JSON for the specified run_id
        records = post_db.select(
            table="test_runs",
            columns=["properties"],
            where={"run_id": run_id},
            to_dict=True
        )

        if not records:
            logger.warning(f"No test run found with run_id {run_id}.")
            return

        # Extract the properties JSON
        properties = records[0].get("properties", {})
        if isinstance(properties, str):
            properties = json.loads(properties)

        # Update the 'Status' in the properties JSON
        properties["Status"] = test_case_status

        # Update the database with the modified properties
        post_db.update(
            table="test_runs",
            data={"properties": json.dumps(properties)},
            where={"run_id": run_id}
        )

        logger.debug(f"Updated test run {run_id} with latest status '{test_case_status}' in properties.")
    except Exception as e:
        logger.error(f"Error updating test run {run_id}: {e}")
    finally:
        post_db.disconnect()


def get_in_progress_jobs(test_set_name):
    """
    Retrieve all jobs with a status of 'IN PROGRESS' from the test_case_execution table.

    :param test_set_name: The name of the test set to filter the jobs.
    :type test_set_name: str
    :return: A list of in-progress job details.
    :rtype: list of dict
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Query the database for in-progress jobs
        records = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            where={"test_set_name": test_set_name, "job_status": "IN PROGRESS"},
            to_dict=True
        )

        return records

    except Exception as e:
        logger.error(f"Error retrieving in-progress jobs: {e}")
        return []
    finally:
        post_db.disconnect()


def delete_test_case_execution(execution_stamp):
    """
    Delete a test case execution record from the database based on its execution stamp.

    :param execution_stamp: The unique execution stamp of the record to delete.
    :type execution_stamp: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()
        post_db.delete(
            table=conf.TEST_SET_EXECUTION,
            where={"execution_stamp": execution_stamp}
        )
        logger.info(f"Deleted test case execution record with stamp: {execution_stamp}")
    except Exception as e:
        logger.error(f"Failed to delete test case execution with stamp {execution_stamp}: {e}")
    finally:
        post_db.disconnect()


def fetch_job_extend(execution_stamp):
    """
    Fetch the latest job_extend for a given execution_stamp from the database.

    :param execution_stamp: The unique execution stamp of the record to fetch.
    :type execution_stamp: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()
        result = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            columns=["extend"],
            where={"execution_stamp": execution_stamp},
            to_dict=True
        )

        if result:
            return result[0].get("extend")
        else:
            logger.warning(f"No extend param found for execution stamp {execution_stamp}.")
            return False
    except Exception as e:
        logger.error(f"Failed to fetch extend for execution stamp {execution_stamp}: {e}")
        return False
    finally:
        post_db.disconnect()


def fetch_test_case_status(execution_stamp):
    """
    Fetch the latest test_case_status for a given execution_stamp from the database.

    :param execution_stamp: The unique execution stamp of the record to fetch.
    :type execution_stamp: str
    :return: The latest test_case_status or None if not found.
    :rtype: str or None
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()
        result = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            columns=["test_case_status"],
            where={"execution_stamp": execution_stamp},
            to_dict=True
        )

        if result:
            return result[0].get("test_case_status")
        else:
            logger.warning(f"No test case status found for execution stamp {execution_stamp}.")
            return None

    except Exception as e:
        logger.error(f"Failed to fetch test case status for execution stamp {execution_stamp}: {e}")
        return None
    finally:
        post_db.disconnect()

def get_test_case_info(test_case):
    """
    Get the test case info relevant to report from the DB.

    :param test_case: TC PID
    :type test_case: str
    :return: The test_case info prepared to report or None if not found.
    :rtype: dict or None
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()
        cases_config = post_db.select(
            table=conf.TEST_CASE_CONFIG,
            where={"tc_pid": test_case},
            to_dict=True
        )
        if not cases_config:
            logger.warning(f"No test case config found for test case {test_case}.")
            return None
        cases_config = cases_config[0]

        cases = post_db.select(
            table=conf.TEST_CASES,
            columns=["properties"],
            where={"pid": test_case},
            to_dict=True
        )
        if not cases:
            logger.warning(f"No test case properties found for test case {test_case}.")
            return None
        cases_props = cases[0].get('properties')
        cases_props = json.loads(cases_props) if cases_props and not isinstance(cases_props, dict) else cases_props

        return {'Test name': cases_config['tc_name'], 'User': cases_config['username'],
                'Team': cases_props.get('Responsible Team')}

    except Exception as e:
        logger.error(f"Failed to get test case config/props with {test_case}: {e}")
        return None

    finally:
        post_db.disconnect()


def monitor_jobs(test_set, stop_event, cluster_to_exclude, cluster_in_use, url=None):
    """
    Monitor all in-progress jobs for a specific test set in the database.

    :param test_set: The test set data.
    :type test_set: dict
    :param stop_event: An event object used to stop the monitoring process.
    :type stop_event: multiprocessing.Event
    """
    jenkins_client = create_jenkins_object(url=test_set.get('jenkins_server'))
    test_set_name = test_set['name']
    tests = test_set['tests']
    is_dev = test_set.get('is_dev')
    released_jobs = []

    while not stop_event.is_set():
        try:
            # Get all jobs that are currently "IN PROGRESS"
            curr_cases = []
            in_progress_jobs = get_in_progress_jobs(test_set_name)
            for job in in_progress_jobs:
                test_case_name = job["test_case_name"]
                job_name = job["job_name"]
                build_number = job["build_number"]
                status = None
                execution_stamp = job["execution_stamp"]

                # Synchronize the latest test_case_status from the database
                test_case_status = fetch_test_case_status(execution_stamp)

                # Check if the job is still in progress
                if jenkins_client.is_in_progress(job_name, build_number):
                    logger.info(f"Job '{job_name}', build number {build_number} is still building...")
                    _update_job_status(
                        test_set_name,
                        test_case_name,
                        build_number,
                        job_name,
                        "IN PROGRESS"
                    )
                else:
                    # Get the final status of the job
                    build_info = jenkins_client.get_build_info(job_name, build_number)
                    status = build_info['result']

                    logger.info(f"Job '{job_name}', build number {build_number} status: {status}")

                    _update_job_status(
                        test_set_name,
                        test_case_name,
                        build_number,
                        job_name,
                        status
                    )

                    # Handle successful job completion
                    if status == 'SUCCESS':
                        logger.info(f"Build number {build_number} completed successfully!")
                    elif status == 'FAILURE':
                        logger.info(f"Build number {build_number} failed.")
                    elif status == 'ABORTED':
                        logger.info(f"Build number {build_number} was aborted.")
                    #TODO handle cluster_in_use lock in the release cluster monitor
                    # try:
                    #     res = jenkins_client.get_build_console_output(job_name, build_number)
                    #     if res:
                    #         cluster_name = next(i['value'] for i in build_info['actions'][0]['parameters'] if i['name'] == 'CLUSTER_NAME')
                    #         if 'InstallFailureHandler' in res:
                    #             cluster_name = next(i['value'] for i in build_info['actions'][0]['parameters'] if
                    #                                 i['name'] == 'CLUSTER_NAME')
                    #             ibid = next(i['value'] for i in build_info['actions'][0]['parameters'] if
                    #                                 i['name'] == 'IBID')
                    #             logger.error(f'InstallFailureHandler found in build {build_info["url"]} for cluster {cluster_name}')
                    #             #TODO add some logic here
                    #             #send_mail(to_addr='gilad.rahamim@dell.com', subject=f'Install Failure found in build {build_info["url"]} for cluster {cluster_name}', message=res)
                    #             cluster_to_exclude[cluster_name] = ibid
                    #         else:
                    #             cluster_to_exclude.pop(cluster_name, None)

                    # except Exception as e:
                    #     logger.critical(f'Failed to get console output for build {build_number} due to {e}')
                    # # Release cluster resources if not already released
                    # try:
                    #     if build_number not in released_jobs:
                    #         cluster_name = next(i['value'] for i in build_info['actions'][0]['parameters'] if i['name'] == 'CLUSTER_NAME')
                    #         with cluster_in_use.get_lock():
                    #             cluster_in_use.value -= 1
                    #         if is_dev or (not cluster_to_exclude.get(cluster_name) and not fetch_job_extend(execution_stamp)):
                    #             username = next(i['value'] for i in build_info['actions'][0]['parameters'] if i['name'] == 'USERNAME')
                    #             logger.info(f'Going to release {cluster_name}')
                    #             xpool_by_labels_and_group(action='release', user=username, cluster=cluster_name)
                    #             released_jobs.append(build_number)
                    # except Exception as e:
                    #     logger.error(f'Failed to release the cluster for build {build_number} due to {e}')

                # Update test_case_status in the database or delete the row if appropriate
                if test_case_status:
                    tc_pid = job['test_case_name']
                    run_id = [test['run_id'] for test in tests if test['TC'] == tc_pid]
                    if run_id:
                        run_id = run_id[0]
                        logger.info(f"Updating test run {run_id} with latest status {test_case_status}")
                        _update_test_run_latest_status(run_id, test_case_status)
                elif status and status.lower() in ['success', 'failure', 'aborted']:
                    logger.info(f"Deleting execution record with stamp {execution_stamp}")
                    delete_test_case_execution(execution_stamp)
            # Sleep for 5 minutes before checking again
            time.sleep(300)

        except Exception as e:
            logger.error(f"Error monitoring jobs: {traceback.print_exc()}")


def get_test_runs():
    """
    Retrieves all test runs from the database.

    :return: A list of dictionaries representing each test run.
    :rtype: list
    """
    # Initialize the database connection
    post_db = db.PostgresDB(
        host=conf.POSTGRES_IP,
        dbname=conf.QTEST_DB_NAME,
        user=conf.USER,
        password=conf.POSTGRES_PASS
    )

    # Connect to the database
    post_db.connect()

    try:
        # Fetch all records from the test_runs table
        rows = post_db.select(conf.TEST_RUNS, to_dict=True)
        return rows
    except Exception as e:
        logger.error(f"Error retrieving test runs from PostgreSQL: {e}")
        return []  # Return an empty list if there's an error
    finally:
        # Disconnect from the database
        post_db.disconnect()


def get_test_cases_mdts(cases=None):
    """
    Retrieves the MDTs (Multi-Dimensional Tests) for the given test cases.

    :param cases: (list, optional) A list of test case IDs.
                    If provided, only the MDTs for the specified test cases will be returned.
    :type cases: list
    :return: A dictionary containing the test case IDs as keys and the corresponding MDTs as values.
    :rtype: dict
    """
    runs = get_test_runs()
    cases_mdts = {}
    for run in runs:
        if cases and run.get("testcase_pid") not in cases:
            continue
        mdts = []
        properties = run.get("properties", {})
        properties = json.loads(properties) if not isinstance(properties, dict) else properties
        for key, val in properties.items():
            if "bugs" in key.lower():
                if val:
                    mdts.extend(val.split(','))
        if mdts:
            cases_mdts.setdefault(run.get("testcase_pid"), []).extend(mdts)
    return cases_mdts


def get_test_cases_for_ibid(ibid=None, cases=None, program=None, sysqa=False):
    """
    Retrieves the test cases that are solved in a given ibid (Integrated Build ID) or the latest ibid.

    :param ibid: (optional) The ibid to check for solved bugs. If not provided, the latest ibid will be used.
    :type ibid: dict or None
    :param cases: (optional) The list of test case IDs to filter the results.
    :type cases: list or None
    :param program: (optional) The program name to filter the ibid.
    :type program: str or None
    :param sysqa: (optional) Whether to include system quality assurance.
    :type sysqa: bool
    :return: A list of test case IDs that are solved in the given ibid.
    :rtype: list
    """
    ret_tcs = []
    cases_mdts = get_test_cases_mdts(cases)
    if not ibid:
        ibid = get_the_latest_ibid(program, sysqa)
    solved_bugs = ibid.get("content")
    for tc, mdts in cases_mdts.items():
        if any([mdt in solved_bugs for mdt in mdts]):
            ret_tcs.append(tc)
    return ret_tcs


def get_the_latest_ibid(version, sysqa=True):
    """
    Retrieves the latest ibid (Integrated Build ID) for a given version.

    :param version: The version of the program.
    :type version: str
    :param sysqa: Whether to include system quality assurance.
    :type sysqa: bool
    :return: The latest ibid as a dictionary, or None if no ibid is found.
    :rtype: dict
    """
    url = f"{BASE_URL}search?" \
          f"product_family='{PRODUCT_FAMILY}' AND " \
          f"program_name='{version}' AND build_flavor='retail' AND build_state='PROMOTED'"

    # if sysqa:
    #     url += f" AND build_state='PROMOTED'"

    data = _get_request(url)
    if data['result_count'] == 0:
        logger.warning(msg="According to your search, no ibid found for {0}".format(version))
        return None

    data = _get_request(data.get('results')[0])
    try:
        product_family = _get_request(list(data['product_family'].values())[0][0])
        target_flavor_url = list(product_family['target_flavor'].values())[0]
        build_revision = _get_request(target_flavor_url).get('build_revision')
    except Exception as e:
        logger.error(f'Failed to get build_revision for ibid {data["ibid_id"]} sye to {e}')
        logger.debug(traceback.format_exc())

    data.update({'build_revision': build_revision})

    return data


@rest_decorator
def _get_request(url):
    """
    Sends a GET request to the specified URL and returns the response data as a JSON object.

    :param url: The URL to send the GET request to.
    :type url: str
    :return: The response data as a JSON object.
    :rtype: dict
    :raises urllib.error.URLError: If an error occurs while sending the request.
    """
    encoded_url = urllib.parse.quote(url, safe=':/?=&')
    response = urllib.request.urlopen(encoded_url)
    data = json.loads(response.read())
    return data

def find_clusters_by_prefix(text: str, federation_mode: bool = False) -> List[str]:
    """
    Finds and returns a list of clusters in the given text that match the specified mode.

    The function searches for words that start with one of the following prefixes when federation_mode is False:
    'RT-', 'WX-', 'WK-', 'OO-', 'OD-'.
    When federation_mode is True, it searches for federation tag that ends with '-federation-TAG'.

    Args:
        text (str): The input text in which to search for clusters.
        federation_mode (bool): Whether to search for federation tag '-federation-TAG'.

    Returns:
        List[str]: A list of found clusters that match the prefixes or '-federation-TAG', based on the mode.

    Example:
        >>> find_clusters_by_prefix("This is a test RT-123 WX-456 no match")
        ['RT-123', 'WX-456']

        >>> find_clusters_by_prefix("This is a test RT-G0076-RT-G0072-federation-TAG", federation_mode=True)
        ['RT-G0076-RT-G0072-federation-TAG']
    """

    if federation_mode:
        pattern = r'\b\S+-federation-TAG\b'
    else:
        pattern = r'\b(?:RT-|WX-|WK-|OO-|OD-)\w+'

    matches = re.findall(pattern, text)
    return list(set(matches))

def xpool_by_labels_and_group(
    action: Optional[str],
    xpool_group: Optional[str] = None,
    xpool_labels: Optional[str] = None,
    cluster: Optional[str] = None,
    free: bool = True,
    num_of_appliances: int = 0,
    user: Optional[str] = None
) -> List[str]:
    """
        Finds clusters by xpool group and xpool label.
    """
    user = user or 'svc_prdsysqafw'
    cmd = BASE_XPOOL_CMD.split()
    cmd.extend([action])
    if action == 'lease':
        cmd.extend(['2d', '-u', user, '-m', 'test_runner'])
    if action == 'release' and cluster and user:
        cmd.extend([cluster] if 'tag' not in cluster.lower() else ['--tag', cluster])
        cmd.extend(['-u', user])
    elif action == 'list':
        cmd.extend(['-a'])
    if xpool_group:
        cmd.extend(['-g', xpool_group])
        # cmd += f' -g {xpool_group}'
    if bool(num_of_appliances):
        cmd.extend(['--federation', str(num_of_appliances)])
    if xpool_labels:
        cmd.extend(['-l', xpool_labels])
    if cluster and action != 'release':
        cmd.extend(['-c', cluster] if 'tag' not in cluster.lower() else ['--tag', cluster])
    if free and action == 'list':
        cmd.extend(['-x'])
    try:
      p = subprocess.run(cmd, capture_output=True, timeout=120)
    except Exception as e:
      return []
    res = find_clusters_by_prefix(p.stdout.decode(), federation_mode=bool(num_of_appliances))
    logger.debug(f'got {res} for cmd {cmd}')
    # TODO analyze xpool output
    return res

def sort_tests_by_priority(tests: List[Dict], ibid_info: dict = None) -> List[Dict]:
    """
    Sorts a list of tests by their priority value in descending order.

    Args:
        tests (List[Dict]): A list of dictionaries, each representing a test case.

    Returns:
        List[Dict]: The sorted list of test case dictionaries, ordered by priority in descending order.
    """
    exexuted = get_exexuted_tests()
    for test in tests:
        if test['TC'].split('_')[0] not in exexuted:
            test.update({'priority': test['priority'] + 5})
    if ibid_info and ibid_info.get("ibid_id"):
        executed_tests = get_test_cases_by_ibid(ibid_info.get("ibid_id"))
        solved_mdts = get_test_cases_for_ibid(cases=[i['TC'] for i in tests if i['current_status'] != 'Passed' and i['TC'] not in executed_tests], ibid=ibid_info)
        for test in tests:
            if test['TC'] in solved_mdts:
                test.update({'priority': test['priority'] + 1})
    return sorted(tests, key=lambda x: x['priority'], reverse=True)


def create_jenkins_object(url=None):
    """
    create jenkins object

    :parameters: none
    :return: jenkins object
    :rtype: jenkinsapi.jenkins.Jenkins
    """
    from shared.jenkins_module import MyJenkins
    return MyJenkins(url=url)
    # from jenkinsapi.utils.crumb_requester import CrumbRequester
    # crumb = CrumbRequester(username=JENKINS_USER, password=JENKINS_PASS, baseurl=JENKINS_URL, ssl_verify=False)
    # return jenkins.Jenkins(baseurl=JENKINS_URL, username=JENKINS_USER, password=JENKINS_PASS,
    #                         requester=crumb, lazy=True, ssl_verify=False)

def get_jenkins_password(jenkins_server: str = None):
    """
    get jenkins password

    :return: jenkins password
    :rtype: str
    """
    if jenkins_server and 'tst' in jenkins_server:
        return '11cb4653c36d9df0066b6c274519dfe38a'
    return '1123556d5bb99740665b27e650b53f947e'


def trigger_job(jenkins_obj, job_name: str, build_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Triggers a Jenkins job with the specified parameters and waits for the build to start.
    
    Args:
        jenkins_obj (jenkins_module.MyJenkins): An instance of the internal Jenkins server connection.
        job_name (str): The name of the Jenkins job to trigger.
        build_params (Dict[str, Any]): A dictionary of build parameters to pass to the job.

    Returns:
        Dict[str, Any]: A dictionary containing the build number and the build URL.
        
    Example:
        >>> jenkins_inst = jenkins_module.MyJenkins('http://jenkins-server:8080', 'user', 'token')
        >>> params = {'PARAM1': 'value1', 'PARAM2': 'value2'}
        >>> result = trigger_job(jenkins_inst, 'test-job', params)
        >>> print(result)
        {'build_number': 123, 'url': 'http://jenkins-server:8080/job/test-job/123/', 'timestamp': '2023-10-20T12:34:56.789012'}
    """
    res = {}
    logger.debug(f'Going to run {job_name} with params {build_params}')
    build_info = jenkins_obj.trigger_job(job_name, build_params)
    res['build_number'] = build_info['number']
    res['job_url'] = build_info['url']
    res['timestamp'] = datetime.now().isoformat()
    res['job_name'] = job_name
    logger.debug(f'exexuted job: {res}')
    return res


def generate_unique_stamp(test_set_name: str, test_id: str, timestamp: str = None) -> str:
    """
    Generate a unique stamp for each record using the test set name, test ID, and a UUID.

    :param test_set_name: The name of the test set instance
    :type test_set_name: str
    :param test_id: The unique identifier for the test
    :type test_id: str
    :param timestamp: Optional timestamp to include in the stamp
    :type timestamp: str, optional
    :return: A unique execution stamp
    :rtype: str
    """
    if not timestamp:
        timestamp = datetime.now().isoformat()
    unique_id = str(uuid4())
    return f"{test_set_name}-{test_id}-{timestamp}-{unique_id}"


def update_test_execution_table(test_set_name: str, test_id: str, test_data: dict, stamp: str = None):
    """
    Updates the test execution results in the PostgreSQL database.

    :param test_set_name: The name of the test set for which execution is being updated
    :type test_set_name: str
    :param test_id: The unique identifier for the test
    :type test_id: str
    :param test_data: The new test data to add or update in the table
    :type test_data: dict
    :param stamp: Test execution stamp
    :type stamp: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Build Where parameters
        where = {
            "test_set_name": test_set_name,
            "test_case_name": test_id
        } if not stamp else {
            "execution_stamp": stamp
        }

        # Check if the test already exists in the database
        existing_records = post_db.select(
            conf.TEST_SET_EXECUTION,
            columns=["execution_stamp", "test_set_name", "test_case_name", "job_name", "build_number"],
            where=where,
            to_dict=True
        )

        if existing_records:
            for record in existing_records:
                if not record["build_number"] and not record["job_name"]:
                    # Update the existing record
                    post_db.update(
                        table=conf.TEST_SET_EXECUTION,
                        data=test_data,
                        where={"execution_stamp": record["execution_stamp"]}
                    )
                    logger.info(f"Updated existing test case '{test_id}' for execution '{test_set_name}'.")
                    return

        # Insert a new record
        insert_to_test_set_execution(test_set_name, test_id, test_data=test_data, stamp=stamp)

    except Exception as e:
        logger.error(f"Error updating test execution table: {e}")
    finally:
        post_db.disconnect()


def insert_to_test_set_execution(test_set_name, test_case_name, stamp=None, test_data=None):
    """
    Insert a new record into the test_case_execution table if it doesn't exist.

    :param test_set_name: The name of the test set.
    :type test_set_name: str
    :param test_case_name: The name of the test case.
    :type test_case_name: str
    :param stamp: The unique execution stamp. If not provided, it will be generated.
    :type stamp: str, optional
    :param test_data: Additional test data to include in the record.
    :type test_data: dict, optional
    """
    test_data = test_data or {}
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Generate timestamp and execution stamp if not provided
        timestamp = test_data.get("timestamp", datetime.now().isoformat())
        execution_stamp = stamp or generate_unique_stamp(test_set_name, test_case_name, timestamp)

        # Create the record
        new_record = {
            "execution_stamp": execution_stamp,
            "test_set_name": test_set_name,
            "test_case_name": test_case_name,
            **test_data
        }

        # Insert the record into the database
        post_db.insert(conf.TEST_SET_EXECUTION, new_record)
        logger.info(f"Inserted new test case '{test_case_name}' for execution '{test_set_name}'.")
    except Exception as e:
        logger.error(f"Failed to insert new test case '{test_case_name}' into test set '{test_set_name}': {e}")
    finally:
        post_db.disconnect()


def insert_to_test_run_config(id_to_insert: int, config: dict):
    """
    Insert test ID and config to the 'test_run_config' table.

    :param id_to_insert: The test ID to insert
    :type id_to_insert: int
    :param config: The configuration data to insert
    :type config: dict

    Example:
        insert_to_test_run_config(101, {"config_key": "config_value"})
    """
    # Initialize the database connection
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    # Connect to the database
    post_db.connect()

    try:
        # Insert data into the test_run_config table
        data_to_insert = {
            'id': id_to_insert,
            'config': json.dumps(config)
        }

        post_db.insert(conf.TEST_RUN_CONFIG, data_to_insert)
        logger.debug(f"Successfully inserted row with ID {id_to_insert} and config '{config}' into test_run_config.")
    except Exception as e:
        logger.error(f"Error inserting into test_run_config: {e}")
    finally:
        # Disconnect from the database
        post_db.disconnect()


def build_test_params(test_set_name: str, test_config: dict, key_param: str = None, ibid: str = None) -> str:
    """
    create jenkins object

    :parameters: none
    :return: jenkins object
    :rtype: jenkinsapi.jenkins.Jenkins
    """
    logger.debug(f'inside build_test_params, test_config: {test_config}, key_param: {key_param}')
    build_params = ''
    if key_param:
        tc_pid = test_config.get('tc_pid')
        timestamp = test_config.get('timestamp', datetime.now().isoformat())
        stamp = generate_unique_stamp(test_set_name, tc_pid, timestamp)
        # insert_to_test_set_execution(test_set_name, tc_pid, stamp=stamp, test_data={'timestamp': timestamp})

        build_params = f'{test_config.get("tc_name", "")}'
        build_params += '' if not test_config.get('tester') else f',{test_config.get("tester")}'
        build_params += f",{stamp}"
        build_params += '' if not test_config.get('cycles')  else f',-c={test_config.get("cycles")}'
    # params_keys = ['test_init_params', 'test_case_params']
    # for param_key in params_keys:
    conf_to_check = test_config if not key_param else test_config.get(key_param)
    for key, val in conf_to_check.items():
        if key == '--ibid' and ibid:
            build_params += f',{key}={ibid}'
            continue
        if not val:
            build_params += f',{key}'
        else:
            build_params += f',{key}={val}'
    if not key_param and '-L' not in build_params:
        build_params += ',-L=btest'
    return build_params[1 if build_params.startswith(',') else 0:]

def build_test_init_params(test_set_name: str, tests: list) -> str:
    """
    create jenkins object

    :parameters: none
    :return: jenkins object
    :rtype: jenkinsapi.jenkins.Jenkins
    """
    logger.debug(f'inside build_test_init_params, tests: {tests}')
    build_params_dict = {}
    for test in tests:
        build_params_dict.update(test['config']['test_init_params'])
    return build_test_params(test_set_name, build_params_dict)


def build_test_case_params(test_set_name: str, tests: list, ibid: str = None):
    """
    create jenkins object

    :parameters: none
    """
    res = {}
    tc_stamps = {}
    for ind, test in enumerate(tests):
        params = build_test_params(test_set_name, test['config'], 'test_case_params', ibid)
        res.update({ind + 1: params})
        tc_pid = test['config'].get('tc_pid')
        stamp = params.split(',')[2]
        tc_stamps.update({tc_pid: stamp})
    logger.debug(f'test_case_params: {res}')
    test_id = uuid.uuid4().int
    insert_to_test_run_config(test_id, res)
    return test_id, tc_stamps


def compare_test_params(main_params, tests, param_key):
    """
    Find the largest set of tests that can be executed together.

    :param main_params: Main test parameters
    :type main_params: dict

    :param tests: A list of tests information and configuration.
    :type tests: list

    :param param_key: The key inside ``test['config']`` that holds the parameter value
    :type param_key: str

    :return: The test cases IDs that belong to the largest compatible group.
    :rtype: list
    """
    posssible_groups = []

    for test in tests:
        test_params = test['config'][param_key].copy()

        if any(
                test_params.get(key) and test_params.get(key).lower() != val.lower() for key, val in main_params.items()
        ):
            continue

        test_params.update(main_params)
        groups_to_add = [{param_key: test_params, 'tests': [test['TC']]}]

        for group_dict in posssible_groups:
            curr_params = group_dict.get(param_key).copy()
            curr_tests = group_dict.get('tests')[:]

            if any(
                    test_params.get(key) and test_params.get(key).lower() != val.lower() for key, val in
                    curr_params.items()
            ) or test['TC'] in curr_tests:
                continue

            curr_params.update(test_params)
            curr_tests.append(test['TC'])
            groups_to_add.append({param_key: curr_params, 'tests': curr_tests})

        posssible_groups.extend(groups_to_add)

    if not posssible_groups:
        return []

    max_group = max(posssible_groups, key=lambda group: len(group['tests']))
    return max_group['tests']


def get_possible_tests_to_run_with(main_test:dict, tests: list, cluster_to_use: str) -> list:
    """
    create jenkins object

    :parameters: none
    :return: jenkins object
    :rtype: jenkinsapi.jenkins.Jenkins
    """
    labels_per_tc = {}
    opt_tc_to_run = set(compare_test_params(main_test.get('config', {}).get('test_init_params'), tests, 'test_init_params')).intersection(compare_test_params(main_test.get('config', {}).get('os_environ'), tests, 'os_environ'))
    if opt_tc_to_run:
        opt_tests_to_run = [i for i in tests if i['TC'] in opt_tc_to_run]
        labels_per_tc = {test['TC']: get_xpool_labels(test) for test in opt_tests_to_run}
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_input = {key: executor.submit(xpool_by_labels_and_group, action='list', xpool_labels=val, cluster=cluster_to_use, free=False) for key, val in labels_per_tc.items() if val}
            for TC, future in future_to_input.items():
                for f in as_completed([future]):
                    if not f.result():
                        labels_per_tc.pop(TC)
    return [test for test in tests if test['TC'] in labels_per_tc and test['TC'] in opt_tc_to_run]

def create_lease_params(tests: list, url: str = None) -> list:
    """
    create jenkins object

    :parameters: none
    :return: jenkins object
    :rtype: jenkinsapi.jenkins.Jenkins
    """
    max_workers = min(20, len(tests))
    jenkins_obj = create_jenkins_object(url)
    job_name = 'Trident/set_lease_params'
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for test in tests:
            logger.info(f'Going to create lease param for {test["TC"]}')
            params = test['config']['os_environ']
            params.update({'QAENV': '/home/opachm/TEST_RUNNER', 'TC_PID': test['TC']})
            if test['config']['xpool_labels']:
                params.update({'JOBLABEL': test['config']['xpool_labels']})
            future = executor.submit(trigger_job, jenkins_obj=jenkins_obj, job_name=job_name, build_params=params)
            futures.append(future)
            time.sleep(0.2)

    for future in as_completed(futures):
        try:
            res = future.result()
        except Exception as e:
            logger.error('Job failed with exception: %s', e)
    time.sleep(30)

def get_xpool_labels(test: Dict) -> str:
    """
    Sorts a list of tests by their priority value in descending order.

    Args:
        tests (List[Dict]): A list of dictionaries, each representing a test case.

    Returns:
        List[Dict]: The sorted list of test case dictionaries, ordered by priority in descending order.
"""
    labels = set(i for i in test.get('config', {}).get('xpool_labels').split(',')).union([i for i in  (test.get('config', {}).get('lease_params') or '').split(',') if i != 'None'])
    res = ','.join([i for i in labels if i])
    logger.debug(f'{test["TC"]} xpool labels: {res}')
    return res


def send_mail(from_addr: str = 'test.runner@dell.com', to_addr: str = None, cc_addr: str = None, message: str = None,
              subject: str = None, markup: str = 'plain', file_path: str = None):
    """
    Send email with optional Cc.

    :param from_addr: Sender's email address
    :type from_addr: str
    :param to_addr: Recipient's email address
    :type to_addr: str
    :param cc_addr: CC email address (optional)
    :type cc_addr: str
    :param message: The email body
    :type message: str
    :param subject: The email subject
    :type subject: str
    :param markup: Format of the email body, either 'plain' or 'html'
    :type markup: str
    :param file_path: Path to the attachment file (optional)
    :type file_path: str
    :return: None
    :rtype: None
    """
    logger.debug('Preparing to send email')
    msg = MIMEMultipart('alternative')
    msg['From'] = from_addr
    msg['To'] = to_addr
    if cc_addr:
        msg['Cc'] = cc_addr
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    body = MIMEText(message, markup)
    msg.attach(body)
    if file_path:
        try:
            with open(file_path, 'rb') as myFile:
                attachment = MIMEApplication(myFile.read(), Name=os.path.basename(file_path))
                attachment['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
                msg.attach(attachment)
            logger.debug(f'Attached file {file_path}')
        except Exception as e:
            logger.error(f'Error attaching file: {e}')

    recipients = msg['To'].split(',')
    if cc_addr:
        recipients += msg.get_all('Cc', [])

    try:
        smtpObj = smtplib.SMTP('mailserver.xiolab.lab.emc.com')
        smtpObj.sendmail(msg['From'], recipients, msg.as_string())
        smtpObj.quit()
        logger.info(f'Email sent to {to_addr} with cc to {cc_addr}')
    except Exception as e:
        logger.error(f'Error sending email: {e}')


def generate_html_table(test_results):
    """
    Generate an HTML table from a list of dictionaries with specified column order.

    :param test_results: List of test result dictionaries
    :type test_results: list
    :return: HTML table as a string
    :rtype: str
    """
    logger.debug('Generating HTML table for test results')
    columns = ['Test name', 'TC ID', 'User', 'IBID', 'Results']

    html = '<html><body><h2>Test Results</h2><table border="1">'
    html += '<tr>' + ''.join(f'<th>{col}</th>' for col in columns) + '</tr>'

    for result in test_results:
        result_info = {
            'Test name': result.get('Test name', ''),
            'TC ID': result.get('TC ID', ''),
            'User': result.get('User', ''),
            'IBID': result.get('IBID', ''),
            'Results': f"{result.get('Result', '')}" + (
                f", {result.get('Bug', '')}" if 'failed' in result.get('Result', '').lower()
                                                and result.get('Bug', '') else ''
            )
        }
        html += '<tr>' + ''.join(f'<td>{result_info[col]}</td>' for col in columns) + '</tr>'

    html += '</table></body></html>'
    logger.debug('HTML table generated')
    return html


def create_and_send_mail(test_results, from_addr='test.runner@dell.com', to_addr=None, cc_addr=None,
                         subject='Test Runner', file_path=None):
    """
    Create and send an email with test results table embedded in the message.

    :param test_results: List of test result dictionaries
    :type test_results: list
    :param from_addr: Sender's email address
    :type from_addr: str
    :param to_addr: Recipient's email address
    :type to_addr: str
    :param cc_addr: CC email address (optional)
    :type cc_addr: str
    :param subject: The email subject
    :type subject: str
    :param file_path: Path to the attachment file (optional)
    :type file_path: str
    :return: None
    :rtype: None
    """
    logger.debug('Creating and sending email with test results')

    if to_addr is None or not test_results:
        logger.error("Invalid 'to_addr' or 'test_results'")
        return "Invalid 'to_addr' or 'test_results'"

    html_table = generate_html_table(test_results)
    common_link = test_results[0].get('Job URL', '') if test_results else ''
    body = (
        f"<p>Dear Recipient,</p>"
        f"<p>Job URL: <a href='{common_link}'>{common_link}</a></p>"
        f"<p>The table below includes the test results and related information:</p>"
        f"{html_table}"
        f"<p>Best Regards,<br>Test Runner Team</p>"
    )

    always_cc = "Gilad.Rahamim@dell.com,moshe.freind@dell.com,Muhammad.Odetallah@dell.com"
    if cc_addr:
        cc_addr = always_cc + ',' + cc_addr
    else:
        cc_addr = always_cc

    send_mail(from_addr, to_addr, cc_addr, body, subject, markup='html', file_path=file_path)


def report_cases_by_mail(cases):
    """
    Report test cases by email based on user information and send a report per link.

    :param cases: List of test case dictionaries, each containing a 'username' key
    :type cases: list
    :return: None
    :rtype: None
    """
    logger.debug('Reporting test cases by email')
    ldap_obj = ldap.Ldap()
    mail_to_tests = {}

    for case in cases:
        username = case.get('User')

        try:
            mail = ldap_obj.search_user_by_username(username).mail.value
        except Exception as e:
            logger.error(f"Error fetching email for username {username}: {e}")
            continue

        link = case.get('Job URL')
        if mail not in mail_to_tests:
            mail_to_tests[mail] = {}
        if link not in mail_to_tests[mail]:
            mail_to_tests[mail][link] = {'tests': [], 'cc': set()}

        mail_to_tests[mail][link]['tests'].append(case)

        team = case.get('Team')
        if team in conf.MANAGER_GROUP_MAPPING:
            manager_email = conf.MANAGER_GROUP_MAPPING[team]
            mail_to_tests[mail][link]['cc'].add(manager_email)

    for mail, links_info in mail_to_tests.items():
        for link, info in links_info.items():
            tests = info['tests']
            cc_addrs = ','.join(info['cc'])
            timestamp = tests[0].get('timestamp', datetime.now())
            formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M')
            subject = f"Test Runner Report {formatted_timestamp}"
            create_and_send_mail(tests, to_addr=mail, cc_addr=cc_addrs, subject=subject)
            logger.info(f"Report created and sent for {mail} with url {link}")


def get_exexuted_tests():
    """
    Retrieve a dictionary of dictionaries from the test_case_execution table,
    where the key of the outer dictionary is the test case ID (e.g., "TC-123"),
    and the inner dictionary contains information about whether the test case
    is 'in progress' or not, filtered by a specific test_set_name.

    :param test_set_name: The name of the test set to filter the results.
    :type test_set_name: str
    :return: A dictionary where keys are test case IDs and values are dictionaries
             indicating whether the test case is 'in progress' or not.
    :rtype: dict
    """
    records = []
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()

        # Query the database
        records = post_db.select(
            table=conf.TEST_SET_EXECUTION,
            columns=["test_case_name"],
            to_dict=True
        )
    except Exception as e:
        logger.error(f"Error retrieving test case statuses: {e}")
    finally:
        post_db.disconnect()

    return [record['test_case_name'] for record in records]

def get_cluster_for_federation(
    xpool_group: Optional[str] = None,
    xpool_labels: Optional[str] = None
) -> List[list]:
    """
        Finds federation clusters by xpool group and xpool label.
    """
    cmd = BASE_XPOOL_CMD.split()
    cmd.extend(['list'])
    if xpool_group:
        cmd.extend(['-g', xpool_group])
    if xpool_labels:
        cmd.extend(['-l', xpool_labels])
    cmd.extend(['-x', '--federation'])
    p = subprocess.run(cmd, capture_output=True)
    stdout_str = p.stdout.decode()
    pattern = re.compile(r"\[((?:u'[^']*')(?:, u'[^']*')*)\]")
    matches = pattern.findall(stdout_str)
    matches = [i.replace("u'", "'").replace("'", "") for i in matches]
    logger.debug(f'Got {matches} for federation')
    return matches


def wait_at_working_hours(country: str) -> None:
    tz = pytz.country_timezones.get(country)
    if not tz:
        return
    tz = pytz.timezone(tz[0])
    now = datetime.now(tz)
    hour = now.hour
    weekday = now.weekday
    if weekday in [4, 5]:
        return
    if 5 <= hour < 18:
        time_to_sleep = now.replace(hour=18, minute=0, second=0, microsecond=0)
        sleep_duration = (time_to_sleep - now).total_seconds()
        logger.info(f'Going to sleep for {sleep_duration // 3600} hours due to working hours resetractions')
        time.sleep(sleep_duration)

def insert_cluster_to_release_table(cluster_name, server, job_name, build_number, xpool_username, tc_stamps):
    """
    Insert/Delete a record from/into cluster_to_release_tablet.

    :param cluster_name: The name of the cluster.
    :type cluster_name: str
    :param job: Jenkins job name.
    :type job: str
    :param action: action to perfrom insert/delete.
    :type action: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()
        # Create the record
        new_record = {
            "cluster": cluster_name,
            "job_name": job_name,
            "server": server,
            "build_number": build_number,
            "xpool_username": xpool_username,
            "tc_stamps": tc_stamps
        }

        # Insert the record into the database
        post_db.insert(conf.RELEASE_TABLE, new_record)
        logger.info(f"Inserted new record {new_record} to {conf.RELEASE_TABLE} table.")
    except Exception as e:
        logger.error(f"Failed to insert record {new_record} due to: {e}")
    finally:
        post_db.disconnect()

def delete_clusters_from_release_table(ids):
    """
    Insert/Delete a record from/into cluster_to_release_tablet.

    :param cluster_name: The name of the cluster.
    :type cluster_name: str
    :param job: Jenkins job name.
    :type job: str
    :param action: action to perfrom insert/delete.
    :type action: str
    """
    post_db = db.PostgresDB(**conf.DB_PARAMS)

    try:
        post_db.connect()
        post_db.delete_records_by_ids(conf.RELEASE_TABLE, ids)
    except Exception as e:
        logger.error(f"Failed to delete ids {ids} from {conf.RELEASE_TABLE} due to: {e}")
    finally:
        post_db.disconnect()

