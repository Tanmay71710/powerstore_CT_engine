import time
import threading
import traceback
from shared.log import get_logger
from shared.utils import delete_clusters_from_release_table, create_jenkins_object, xpool_by_labels_and_group, fetch_job_extend
from shared import config as conf
import shared.database as db

logger = get_logger(__name__)


class ReleaseCluster(threading.Thread):
    """ test set runner.

    """

    def __init__(self):
        """ Class Init

            :param hostObj: The host the monitor is running from.
            :type hostObj: trident.host.Host
            :returns: None
        """
        super(ReleaseCluster, self).__init__()
        self.post_db = db.PostgresDB(**conf.DB_PARAMS)

    def get_records(self):
        try:
            self.post_db.connect()
            records = self.post_db.select(table=conf.RELEASE_TABLE, to_dict=True)
            return records
        except Exception as e:
            logger.error()
        finally:
            self.post_db.disconnect()
    
    def check_for_install_issue(self, jenkins_client, job_name, build_number, build_info):
        try:
            res = jenkins_client.get_build_console_output(job_name, build_number)
            if res:
                cluster_name = next(i['value'] for i in build_info['actions'][0]['parameters'] if i['name'] == 'CLUSTER_NAME')
                if 'InstallFailureHandler' in res:
                    cluster_name = next(i['value'] for i in build_info['actions'][0]['parameters'] if
                                        i['name'] == 'CLUSTER_NAME')
                    logger.error(f'InstallFailureHandler found in build {build_info["url"]} for cluster {cluster_name}')
                    #TODO add some logic here
                    #send_mail(to_addr='gilad.rahamim@dell.com', subject=f'Install Failure found in build {build_info["url"]} for cluster {cluster_name}', message=res)
                    return True
        except Exception as e:
            logger.critical(f'Failed to get console output for build {build_number} due to {e}')

    def run(self):
        logger.info(f'Starting release clusters monitor')
        jenkins_obj = None
        removed_ids = set()
        while True:
            try:
                records = self.get_records()
                user_per_cluster = {}
                ids_to_remove = []
                for record in records:
                    if record['id'] in removed_ids:
                        delete_clusters_from_release_table([record['id']])
                        continue
                    stamps = record['tc_stamps']
                    if not jenkins_obj or jenkins_obj.server != record.get('server'):
                        jenkins_obj = create_jenkins_object(url=record.get('server'))
                    job_name = record['job_name']
                    is_dev = 'dev' in job_name
                    build_number =  record['build_number']
                    build_info = jenkins_obj.get_build_info(job_name, build_number)
                    status = build_info['result']
                    if status and status in ['SUCCESS', 'FAILURE', 'ABORTED']: 
                        logger.info(f"Job '{job_name}', build number {build_number} status: {status}, Going to check the extend rules for stamps {stamps}")
                        if not is_dev:
                            if any(fetch_job_extend(stamp) for stamp in stamps) or self.check_for_install_issue(jenkins_obj, job_name, build_number, build_info):
                                logger.info(f"will not release {record['cluster']}")
                                delete_clusters_from_release_table([record['id']])
                                continue            
                        user_per_cluster.update({record['cluster']: record['xpool_username']})
                        removed_ids.add(record['id'])
                        ids_to_remove.append(record['id'])
                if user_per_cluster:
                    delete_clusters_from_release_table(ids_to_remove)
                    logger.info(f'Going to release {list(user_per_cluster.keys())}')
                    for cluster, user in user_per_cluster.items():
                        xpool_by_labels_and_group(action='release', cluster=cluster, user=user)
                time.sleep(300)
            except Exception as e:
                logger.critical(f'release cluster monitor failed due to {e}, traceback: {traceback.print_exc()}')
                time.sleep(300)
