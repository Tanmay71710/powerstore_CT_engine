"""Module holding jenkins class"""
import time

import jenkins

from shared.log import get_logger
import shared.utils as utils


logger = get_logger(__name__)

JENKINS_URL = "https://osj-ngm-03-prd.cec.delllabs.net/"
JENKINS_USER = "svc_prdsysqafw"
#JENKINS_PASS = utils.get_jenkins_password()


class MyJenkins(jenkins.Jenkins):
    """
    Jenkins internal object.
    """

    @utils.rest_decorator
    def __init__(self, url=JENKINS_URL, username=JENKINS_USER, password=None):
        url = url or JENKINS_URL
        password = password or utils.get_jenkins_password(url)
        super().__init__(url, username, password)
        self._session.verify = False
        self.password = password

    @utils.rest_decorator
    def jenkins_open(self, req, add_crumb=False, resolve_auth=True):
        """
        Return the HTTP response body from a ``requests.Request``.

        :returns: ``str``
        """
        return self.jenkins_request(req, False, resolve_auth).text

    @utils.rest_decorator
    def trigger_job(self, job_name, build_params):
        """
        Triggers a Jenkins job with the specified parameters and waits for the build to start.
        """
        current_build_number = self.get_job_info(job_name)['nextBuildNumber']
        self.build_job(job_name, parameters=build_params)
        while True:
            try:
                build_info = self.get_build_info(job_name, current_build_number)
                break
            except Exception:
                time.sleep(2)
        return build_info

    def get_build_status(self, job_name, build_number):
        """Retrieve the status of a specified build for a specific job."""
        try:
            build_info = self.get_build_info(job_name, build_number)
            return build_info['result']
        except Exception as e:
            logger.warning(msg=f"Error getting build {build_number} status for job '{job_name}': {e}")
            return ''

    def is_in_progress(self, job_name, build_number):
        """Check if the last build of a specific job is still in progress."""
        try:
            build_info = self.get_build_info(job_name, build_number)
            return build_info['inProgress']
        except Exception as e:
            logger.warning(msg=f"Error checking if build {build_number} is in progress for job '{job_name}': {e}")
            return False
