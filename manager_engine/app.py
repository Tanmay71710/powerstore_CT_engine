import sys
import os
import logging
from logging.handlers import RotatingFileHandler
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

from shared.log import set_logger
from shared import db, ma
from shared.routes import test_plan_bp, test_set_bp, test_execution_bp, shared_bp
from flask_cors import CORS

log_dir = os.path.dirname(os.path.abspath(__file__))
log_file = os.path.join(log_dir, 'app.log')

logger = set_logger(log_file)

app = Flask(__name__, template_folder='../shared/templates')

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

db.init_app(app)
ma.init_app(app)

app.register_blueprint(test_plan_bp)
app.register_blueprint(test_set_bp)
app.register_blueprint(test_execution_bp)
app.register_blueprint(shared_bp)


from extended_routes import manager_bp
app.register_blueprint(manager_bp)

SWAGGER_URL = '/swagger'
API_URL = '/static/swagger.json'
from flask_swagger_ui import get_swaggerui_blueprint
swaggerui_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
CORS(app)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)

