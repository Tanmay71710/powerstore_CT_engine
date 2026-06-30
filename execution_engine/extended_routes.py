import signal
import os
import time
from flask import Blueprint, request, jsonify, Response
from shared import db
from shared.models import TestSet
from shared.log import get_logger

logger = get_logger(__name__)

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'app.log')


def configure_routes(app):
    exexution_bp_routes = Blueprint('exexution_bp_routes', __name__)

    @exexution_bp_routes.route('/log')
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

    @exexution_bp_routes.route('/start', methods=['POST'])
    def start():
        print('------------- start -------------')
        app.runner.start()
        return jsonify({"message": f"{app.test_set_name} started"}), 200

    @exexution_bp_routes.route('/is_alive', methods=['GET'])
    def is_alive():
        if app.runner.is_alive():
            return jsonify({"message": f"{app.test_set_name} alive"}), 200
        else:
            return jsonify({"message": f"{app.test_set_name} not alive"}), 200

    @exexution_bp_routes.route('/pause', methods=['POST'])
    def pause():
        app.runner.pause_event.set()
        return jsonify({"message": f"{app.test_set_name} paused"}), 200

    @exexution_bp_routes.route('/resume', methods=['POST'])
    def resume():
        app.runner.pause_event.clear()
        return jsonify({"message": f"{app.test_set_name} resumed"}), 200

    @exexution_bp_routes.route('/stop', methods=['POST'])
    def stop():
        app.runner.stop_event.set()
        app.runner.join(120)
        return jsonify({"message": f"{app.test_set_name} stopped"}), 200
    
    app.register_blueprint(exexution_bp_routes)