import sys
import os
import logging
from logging.handlers import RotatingFileHandler
import argparse
import socket
print(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask
# New configuration system
try:
    from shared.config_loader import get_config, get_config_dict
    from shared.environment import get_environment
    CONFIG_SYSTEM = 'new'
except ImportError:
    from shared.config import Config
    CONFIG_SYSTEM = 'legacy'

from shared import db, ma
from shared.routes import test_plan_bp, test_set_bp, test_execution_bp, shared_bp
from shared.log import set_logger
from flask_cors import CORS
from runner import Runner

app = Flask(__name__)

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'app.log')
logger = set_logger(log_file)

# Load configuration based on available system
if CONFIG_SYSTEM == 'new':
    try:
        # New configuration system
        config_dict = get_config_dict()
        app.config['SQLALCHEMY_DATABASE_URI'] = config_dict.get('SQLALCHEMY_DATABASE_URI')
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config_dict.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
        app.config['SECRET_KEY'] = config_dict.get('SECRET_KEY', 'change-this-secret-key')
        logger.info(f"Using new configuration system, environment: {get_environment()}")
    except Exception as e:
        # Fallback to legacy config if new system fails
        logger.warning(f"New configuration system failed, falling back to legacy: {e}")
        app.config.from_object(Config)
        CONFIG_SYSTEM = 'legacy'
else:
    app.config.from_object(Config)

def create_app(args):
    # Load configuration based on available system
    if CONFIG_SYSTEM == 'new':
        try:
            config_dict = get_config_dict()
            app.config['SQLALCHEMY_DATABASE_URI'] = config_dict.get('SQLALCHEMY_DATABASE_URI')
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = config_dict.get('SQLALCHEMY_TRACK_MODIFICATIONS', False)
            app.config['SECRET_KEY'] = config_dict.get('SECRET_KEY', 'change-this-secret-key')
        except Exception as e:
            logger.warning(f"Configuration loading failed: {e}")
            # Use minimal fallback configuration
            app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///fallback.db'
            app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
            app.config['SECRET_KEY'] = 'fallback-secret-key'
    else:
        app.config.from_object(Config)
    
    app.port = args.port
    app.test_set_name = args.test_set_name

    db.init_app(app)
    ma.init_app(app)

    app.register_blueprint(test_plan_bp)
    app.register_blueprint(test_set_bp)
    app.register_blueprint(test_execution_bp)
    app.register_blueprint(shared_bp)

    from extended_routes import configure_routes
    with app.app_context():
        configure_routes(app)

    SWAGGER_URL = '/swagger'
    API_URL = '/static/swagger.json'
    from flask_swagger_ui import get_swaggerui_blueprint
    swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
    app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
    CORS(app)
    # loopback_ip = socket.gethostbyname('localhost')
    # print(loopback_ip)
    # base_url = f'http://{loopback_ip}:{app.port}'
    app.runner = Runner(app.test_set_name, app=app)
    app.runner.start()
    return app

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run the Flask app')
    parser.add_argument('--port', type=int, default=5000, help='Port number to run the Flask app on')
    parser.add_argument('--test_set_name', type=str, help='test set to run')

    args = parser.parse_args()

    app = create_app(args)
    print('+++++++++++++++++++++++', app.runner.is_alive())
    app.run(host='0.0.0.0', port=app.port)

