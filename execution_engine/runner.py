import json
import time
import threading
import traceback
from multiprocessing import Event, JoinableQueue, Manager, Value
from shared.monitor import BackgroundProcess
from flask import current_app
from shared.log import get_logger
from shared.routes import get_test_set
from shared.utils import sort_tests_by_priority, xpool_by_labels_and_group, get_xpool_labels, create_jenkins_object, \
    build_test_init_params, create_lease_params, build_test_case_params, trigger_job, update_test_execution_table, \
    build_test_params, get_the_latest_ibid, get_possible_tests_to_run_with, get_test_cases_status_dict, get_cluster_for_federation, wait_at_working_hours, insert_cluster_to_release_table

logger = get_logger(__name__)


JOB_NAME = 'Trident/test_executer'
DEV_JOB_NAME = 'Trident/dev_test_executer'
XPOOL_GROUPS = 'QA-TestRunner'


class Runner(threading.Thread):
    """ test set runner.

    """

    cluster_to_exclude = Manager().dict()
    cluster_in_use = Value('i', 0)

    def __init__(self, test_set_name, app):
        """ Class Init

            :param hostObj: The host the monitor is running from.
            :type hostObj: trident.host.Host
            :returns: None
        """
        super(Runner, self).__init__()
        print(test_set_name)
        self.app = app
        self.test_set_name = test_set_name 
        self.stop_event = Event()
        self.pause_event = Event()
        self.executed_tests = []
        test_set_info = self.test_set
        logger.debug(f'At init - test_set_info: {test_set_info}')
        self.qaenv = test_set_info.get('qaenv') or '/home/trqa-dev'
        self.xpool_groups = test_set_info.get('xpool_groups') or XPOOL_GROUPS
        self.reservation_limit = test_set_info.get('xpool_reservation_limit')
        self.federation_clusters = get_cluster_for_federation(self.xpool_groups)
        self.is_dev = test_set_info.get('filter', {}).get('dev_test', False) == 'True'
        self.pr_tester = test_set_info.get('filter', {}).get('pr_tester', False) == 'True'
        self.xpool_username = test_set_info.get('xpool_username') or 'svc_prdsysqafw'
        self.jenkinsObj = create_jenkins_object(url=test_set_info.get('jenkins_server'))
        self.monitor_process = None
        self._task_queue = None
        self.start_monitor_process()


    def start_monitor_process(self):
        """
        Initializes monitor process.
        """
        self._task_queue = JoinableQueue()
        self._task_queue.put("start_jenkins_monitor")
        self.monitor_process = BackgroundProcess(self.test_set, self._task_queue, self.stop_event, self.cluster_to_exclude,
                                                 self.cluster_in_use)
        self.monitor_process.start()

    @property
    def test_cases_status(self):
        """
        Getter for test cases status that is associated with the current test set.
        """
        return get_test_cases_status_dict(self.test_set_name)

    @property
    def test_set(self):
        """
        Getter for test set from the database.

        :parameter: None
        :return: test set information
        :rtype: dict
        """
        for _ in range(5):
            try:
                res = self.get_test_set()
                if not res or len(res.get('tests', [])) <= 1:
                    time.sleep(5)
                else:
                    return res
            except:
                time.sleep(5)
        return {'tests': []}

    def get_test_set(self):
        """
        Getter function for test set from the database.
        :return: test set information
        :rtype: dict
        """
        with self.app.app_context():
            return get_test_set(self.test_set_name).get_json()
    
    def run(self):
        logger.info(f'Starting test runner for {self.test_set_name}, xpool user: {self.xpool_username}')
        time.sleep(120)
        check_lease_params = [test for test in self.test_set['tests'] if test['config']['lease_params'] != 'None']
        if check_lease_params:
            create_lease_params(check_lease_params)
        logger.debug(f'test set data: {self.test_set}')
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                time.sleep(60)
                continue
            try:
                test_set_info = self.test_set
                if not test_set_info:
                    logger.critical('Got empty set')
                    time.sleep(120)
                    continue
                logger.debug(f'test set data: {test_set_info}')
                if test_set_info.get('execuation_time_zone'):
                    wait_at_working_hours(test_set_info.get('execuation_time_zone'))
                #assume we have single relaese in a test set
                version = next(test['version'] for test in test_set_info['tests'])
                ibid_info = get_the_latest_ibid(version, not self.is_dev)
                test_cases_status = self.test_cases_status
                tests_in_progress = [test['TC'] for test in test_set_info['tests'] if test_cases_status.get(test['TC'].split('_')[0], {}).get('in_progress', False)]
                logger.info(f"tests_in_progress: {tests_in_progress}")
                tests_to_run = [test for test in test_set_info['tests'] if test['TC'] not in tests_in_progress]
                for test in tests_to_run:
                   if test_cases_status.get(test['TC'], {}).get('status'):
                       test['priority'] -= 0.5
                   if 'passed' in test_cases_status.get(test['TC'], {}).get('status', '').lower():
                      test['priority'] -= 0.5
                sorted_set = sort_tests_by_priority(tests_to_run, ibid_info)
                self.run_tests(sorted_set, version)
                if self.pr_tester:
                    self.stop_event.set()
                time.sleep(300)
            except Exception as e:
                logger.critical(f'Runner failed on {str(e)}, traceback: {traceback.print_exc()}')
                time.sleep(60)

        # Stop background tasks
        self._task_queue.join()
        self.monitor_process.join()
        logger.info("All background tasks have stopped.")

    def run_tests(self, tests: list, version: str):
        """
        create jenkins object

        :parameters: none
        :return: jenkins object
        :rtype: jenkinsapi.jenkins.Jenkins
        """
        executed = []
        logger.info(f'run_tests: TCs to run: {[test["TC"] for test in tests]}')
        federation_clusters_to_exclude = self.federation_clusters if any(test for test in tests if test.get("federation_size")) else None
        for test in tests:
            if self.reservation_limit and self.reservation_limit >= self.cluster_in_use:
                logger.info(f'reached reservation limit, will wait...')
                time.sleep(600)
                break
            main_test_ndu = test.get("config", {}).get("ndu", False)
            num_of_appliances = test.get("federation_size")
            if main_test_ndu:
                test['priority'] = 20
            if self.stop_event.is_set():
                break
            if self.pause_event.is_set():
                time.sleep(60)
                continue
            if test in executed:
                continue
            logger.debug(f'Got: {test.get("TC")} - {test.get("config", {}).get("tc_name")}')
            xpool_labels = get_xpool_labels(test)
            # if not test.get("federation_size") and federation_clusters_to_exclude:
            #     xpool_labels += ','.join(f'@{i.strip()}' for i in federation_clusters_to_exclude)
            cluster_to_use = xpool_by_labels_and_group('lease', self.xpool_groups, xpool_labels, free=False,
                                                       num_of_appliances=num_of_appliances, user=self.xpool_username)
            if cluster_to_use:
                cluster_to_use = cluster_to_use[0]
                with self.cluster_in_use.get_lock():
                    self.cluster_in_use.value += 1
            logger.debug(f'lease {cluster_to_use} for {test.get("TC")}')
            #TODO should be a prop for all test_set not per test
            ibid = get_the_latest_ibid(version, not self.is_dev)['ibid_id']
            MIN_IBID = ibid
            if cluster_to_use:
                tests_to_run = [test]
                possible_tests_to_run = get_possible_tests_to_run_with(test, [i for i in tests if i != test and i not in executed and
                                                                              (not main_test_ndu or (not i.get("config", {}).get("ndu", False)
                                                                               and not i.get('add_appliance')))], cluster_to_use)

                ndu_tests = [test for test in possible_tests_to_run if test.get("config", {}).get("ndu", False)]
                if ndu_tests:
                    for ndu in ndu_tests:
                        possible_tests_to_run.remove(ndu)
                    ndu_test = sort_tests_by_priority(ndu_tests)[0]
                    ndu_test['priority'] = 20
                    possible_tests_to_run.append(ndu_test)
                #TODO limit until we an calculate based on test time
                possible_tests_to_run = possible_tests_to_run[:3]
                if possible_tests_to_run:
                    logger.info(f'Found that {test.get("TC")} can run with {[i["TC"] for i in possible_tests_to_run]}') 
                    tests_to_run.extend(possible_tests_to_run)
                executed.extend(tests_to_run)
                ndu = next((i for i in tests_to_run if i.get("config", {}).get("ndu", False)), None)
                test_init_params = build_test_init_params(self.test_set_name, tests_to_run)
                logger.debug(f'test_init_params: {test_init_params}')
                test_id, tc_stamps = build_test_case_params(self.test_set_name, sort_tests_by_priority(tests_to_run), ibid=ibid if ndu else None)
                job_params = {'QAENV': self.qaenv, 'CLUSTER_NAME': f'{cluster_to_use}', 'USERNAME': self.xpool_username}

                if ndu:
                    ibid = ndu.get("config", {}).get("source_version")
                    logger.info(f'Going to take {ibid} ibid for NDU source version')
                    job_params.update({'UPGRADE_SCHEDULE': 'none'})
                if test_init_params:
                    load_type = next((i for i in test_init_params.split(',') if '-L' in i), None)
                    if load_type:
                        job_params.update({'LOAD_TYPE': load_type.split("=")[-1]})
                    job_params.update({'OTHER_PARAMETERS': test_init_params.replace('=', ' ').replace(',', ' ')})
                job_params.update({'IBID': ibid})
                job_params.update({'TEST_CMD': test_id})
                job_params.update({'MIN_IBID': MIN_IBID})
                r = {k: v for d in [test.get('config', {}).get('os_environ', {}) for test in tests_to_run] for k, v in d.items()}
                job_params.update(r)
                if 'HBA_SETUP' in job_params['OTHER_PARAMETERS']:
                    OTHER_PARAMETERS = job_params['OTHER_PARAMETERS'].replace('HBA_SETUP', r.get('HBA_SETUP', 'Any'))
                    job_params['OTHER_PARAMETERS'] = OTHER_PARAMETERS
                if '--hbaSetup XXX' in job_params['OTHER_PARAMETERS']:
                    OTHER_PARAMETERS = job_params['OTHER_PARAMETERS'].replace('--hbaSetup XXX', '--hbaSetup {0}'.format(r.get('HBA_SETUP', 'Any')))
                    job_params['OTHER_PARAMETERS'] = OTHER_PARAMETERS
                logger.info(f'Going to trigger {[test_data.get("TC") for test_data in tests_to_run]}, with job params: {job_params}')
                job_name = DEV_JOB_NAME if self.is_dev else JOB_NAME
                logger.info(f'Going to use job: {job_name}')
                job_data = trigger_job(self.jenkinsObj, job_name, build_params=job_params)
                if not job_data.get('build_number'):
                    logger.critical('Failed to get jenkins job build number for {cluster_to_use}, will not relase it...')
                elif job_name != DEV_JOB_NAME:
                    insert_cluster_to_release_table(cluster_to_use, self.jenkinsObj.server, job_data['job_name'],
                                                    job_data['build_number'], self.xpool_username, list(tc_stamps.values()))
                job_data['ibid'] = MIN_IBID
                job_data['job_status'] = 'IN PROGRESS'
                job_data['job_params'] = json.dumps(job_params)
                job_data['xpool_labels'] = xpool_labels
                for tc in [test_data.get("TC") for test_data in tests_to_run]:
                    update_test_execution_table(f"{self.test_set_name}", tc.split('_')[0], job_data, stamp=tc_stamps.get(tc.split('_')[0]))

