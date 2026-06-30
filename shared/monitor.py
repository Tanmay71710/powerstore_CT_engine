"""Module holding monitor class"""
import multiprocessing
import threading
import time

from shared.log import get_logger
from shared.utils import monitor_jobs

logger = get_logger(__name__)


class BackgroundProcess(multiprocessing.Process):
    """Background Process Class"""
    def __init__(self, test_set, task_queue, stop_event, cluster_to_exclude, cluster_in_use):
        """
        Initialize the BackgroundProcess.
        :param test_set: The test set to monitor.
        :type test_set: dict
        :param task_queue: A queue object holding the tasks to be executed.
        :type task_queue: multiprocessing.Queue
        :param stop_event: An event object used to stop the background process.
        :type stop_event: multiprocessing.Event
        """
        super().__init__()
        self.cluster_to_exclude = cluster_to_exclude
        self.cluster_in_use = cluster_in_use
        self.test_set = test_set
        self.stop_event = stop_event
        self.task_queue = task_queue
        self.threads = []
        self.commands = {
            "start_jenkins_monitor": monitor_jobs
        }
        self.commands_args = {
            "start_jenkins_monitor": (self.test_set, self.stop_event, self.cluster_to_exclude, self.cluster_in_use)
        }

    def run(self):
        """
        Start the background process.
        """
        logger.info(f"{self.name} starting...")
        try:
            while not self.stop_event.is_set():
                if not self.task_queue.empty():
                    task_name = self.task_queue.get()
                    # Create a new thread to run the task
                    t = threading.Thread(target=self.commands[task_name], args=self.commands_args[task_name])
                    t.start()
                    self.threads.append(t)
                    self.task_queue.task_done()
                time.sleep(1)

            logger.info(f"{self.name} stopping...")
        except Exception as e:
            logger.error(f"{self.name} encountered an error: {e}")
        finally:
            for thread in self.threads:
                thread.join()
            logger.info(f"All threads in {self.name} have been stopped.")
