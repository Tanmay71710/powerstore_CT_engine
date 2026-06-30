# Define your application-specific routes here
from flask import Blueprint, request, jsonify, current_app, Response
from shared import db
from shared.models import TestSet, TestCaseExecution
from shared.routes import add_server_to_execution
from shared.log import get_logger
import time
from kubernetes_api import KubernetesApi
import requests
import os

logger = get_logger(__name__)

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'app.log')

manager_bp = Blueprint('manager_bp_routes', __name__)

@manager_bp.route('/log')
def log():
    try:
        with open(log_file, 'r') as f:
            log_content = f.readlines()
            log_content_html = "".join(f"<p>{line}</p>" for line in log_content)

            # Define color for each log level
            log_level_colors = {
                'DEBUG': 'gray',
                'INFO': 'blue',
                'WARNING': 'orange',
                'ERROR': 'red',
                'CRITICAL': 'darkred'
            }

            # HTML template with background color
            log_content_html = "<html><body style='background-color: #f4f4f9;'>"

            # Process each line and wrap it in <p> tags with appropriate color
            for line in log_content:
                print(line)
                # Default to black if no log level is found
                color = 'black'

                # Check log level in line and set color accordingly
                for level, level_color in log_level_colors.items():
                    if level in line:
                        color = level_color
                        break

                # Append each line as a <p> tag with the assigned color
                log_content_html += f"<p style='color: {color};'>{line.strip()}</p>"

            log_content_html += "</body></html>"

            return Response(log_content_html, mimetype='text/html')
    except Exception as e:
        logger.error('Error accessing log file: %s', e)
        return "Error accessing log file"

@manager_bp.route('/testsets', methods=['POST'])
def create_test_set():
    data = request.get_json()
    logger.debug(f'Going to create test set with data {data}')
    
    name = data.get('name')
    if not name:
        return jsonify({"error": "Test set name is mandatory"}), 400
    
    filter_data = data.get('filter', {})
    priority_rule = data.get('priority_rule', {})
    test_list = []
    xpool_groups = data.get('xpool_groups') or ''
    xpool_reservation_limit = data.get('xpool_reservation_limit')
    xpool_username = data.get('xpool_username')
    execuation_time_zone = data.get('execuation_time_zone')
    jenkins_server = data.get('jenkins_server')

    test_set = TestSet(name=name, filter=filter_data, tests=test_list, priority_rule=priority_rule, xpool_groups=xpool_groups, 
                       xpool_reservation_limit=xpool_reservation_limit, xpool_username=xpool_username,
                       execuation_time_zone=execuation_time_zone, jenkins_server=jenkins_server)
    db.session.add(test_set)
    db.session.commit()

    return jsonify(test_set.to_dict()), 201

@manager_bp.route('/testsets/<string:name>', methods=['DELETE'])
def delete_test_set(name):
    try:
        test_set = TestSet.query.filter_by(name=name).first()
        if not test_set:
            return jsonify({"error": "Test set not found"}), 404

        if test_set:
            db.session.delete(test_set)
        
        db.session.commit()
        return jsonify({"message": "Test set deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@manager_bp.route('/execute_test_set/<string:name>', methods=['POST'])
def execute_test_set(name):
    """
    Execute a Test Set by name and deploy its associated service.
    Returns the IP, port, and service URL of the deployed service.
    """
    try:
        data = request.get_json()
        qaenv = data.get("qaenv") if data else None

        kubObj = KubernetesApi()
        port = kubObj.find_next_unused_port()
        app_name = f'{name}-app'

        kubObj.create_deployment(app_name, port, name)
        kubObj.create_service(app_name, port)

        # Wait for service readiness
        for _ in range(10):  # Check readiness for up to 10 seconds
            try:
                ip, port = kubObj.get_load_balancer_info(app_name)
                if ip and port:
                    break
            except Exception as e:
                time.sleep(1)
        else:
            return jsonify({"error": "Service did not become ready in time"}), 500

        add_server_to_execution(name, ip, port, qaenv)
        time.sleep(5)
        # url = f'http://{ip}:{port}/start'
        # response = requests.post(url, headers={'accept': 'application/json'}, data='')
        # if response.status_code != 200:
        #     return jsonify({"error": f"Failed to start test set: {response.text}"}), 500

        return jsonify({"ip": ip, "port": port, "service_url": f"{ip}:{port}"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@manager_bp.route('/stop_test_set/<string:name>', methods=['POST'])
def stop_test_set(name):
    test_set = TestSet.query.filter_by(name=name).first()
    server_info = test_set.server
    url = 'http://{0}:{1}/stop'.format(server_info['ip'], server_info['port'])
    requests.post(url, headers={'accept': 'application/json'}, data='')
    kubObj = KubernetesApi()
    app_name = f'{name}-app'
    kubObj.delete_deployment(app_name)
    kubObj.delete_service(app_name)
    test_set.server = {}
    db.session.commit()
    return jsonify({"message": "Test set execution stopped and deleted successfully"}), 200


def configure_app_specific_routes(app):
    app.register_blueprint(bp)

 