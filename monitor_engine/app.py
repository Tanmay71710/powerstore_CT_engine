import sys
import os
import time
from logging.handlers import RotatingFileHandler
print(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
from shared.log import set_logger
from flask_cors import CORS
from release_clusters_monitor import ReleaseCluster

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'app.log')

logger = set_logger(log_file)

app = Flask(__name__)
app.monitor = ReleaseCluster()
app.monitor.start()
time.sleep(10)

CORS(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5004)

