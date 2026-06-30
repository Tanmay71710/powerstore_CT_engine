import sys
import os, csv
import time

print(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask import Blueprint, request, jsonify, render_template, send_file, redirect, session, url_for, flash
from shared.models import TestPlan, TestPlanSchema, db, TestRun, TestSet, TestConfig, TestCaseExecution, NduMapping
from shared.utils import _find_release, extract_release_name, get_the_latest_ibid, create_jenkins_object, \
    xpool_by_labels_and_group, trigger_job, get_main_parameters
from sqlalchemy import cast, Text
from sqlalchemy import or_
import json
from dateutil.parser import parse as date_parser
from sqlalchemy import inspect, text
from datetime import datetime
from shared import db, ldap
from ldap3.core.exceptions import LDAPBindError, LDAPInvalidCredentialsResult
from functools import wraps
from dateutil import parser as date_parser
from shared.log import get_logger
logger = get_logger(__name__)
test_plan_bp = Blueprint('test_plan', __name__)
test_set_bp = Blueprint('test_set_bp', __name__)
test_execution_bp = Blueprint('test_execution_bp', __name__)
shared_bp = Blueprint('shared', __name__)

ADMIN_TABLES = ['users']

ORDERED_COLUMNS = [
    'tc_pid', 'tc_name', 'xpool_labels', 'test_init_params', 'test_case_params',
    'os_environ', 'special_installation', 'ndu', 'add_appliance', 'expect_failure',
    'load_via_testinit', 'replication', 'job_url', 'username', 'io_destructive', 'is_ha', 'executable', 'is_dev'
]


@shared_bp.route('/getJobMainParameters/<string:job_name>/<string:job_id>', methods=['GET'])
def getJobMainParameters(job_name, job_id):
    """Fetch job main parameters by job name and job id (Build Number)."""
    test = TestCaseExecution.query.filter_by(build_number=job_id, job_name=f"Trident/{job_name.lower()}").first()

    if not test:
        return jsonify({"error": "Test case execution not found"}), 404

    testinit_stamp = test.to_dict().get('testinit_stamp')
    main_parametes = get_main_parameters(testinit_stamp)

    return jsonify(main_parametes)


@shared_bp.route('/getJobTestList/<string:job_name>/<string:job_id>', methods=['GET'])
def getJobTestList(job_name, job_id):
    """Fetch job test list by job name and job id (Build Number)."""
    test_cases = TestCaseExecution.query.filter_by(build_number=job_id, job_name=f"Trident/{job_name.lower()}").all()

    if not test_cases:
        return jsonify({"error": "Test case execution not found"}), 404

    test_details = [test.to_dict().get('test_case_name') for test in test_cases]

    return jsonify(test_details)


@shared_bp.route('/getJobIbid/<string:job_name>/<string:job_id>', methods=['GET'])
def getJobIbid(job_name, job_id):
    """Fetch job ibid by job name and job id (Build Number)."""
    test_cases = TestCaseExecution.query.filter_by(build_number=job_id, job_name=f"Trident/{job_name.lower()}").all()

    if not test_cases:
        return jsonify({"error": "Test case execution not found"}), 404

    test_details = list(set(test.to_dict().get('ibid') for test in test_cases))

    return jsonify(test_details)


@shared_bp.route('/getJobUrl/<string:job_name>/<string:job_id>', methods=['GET'])
def getJobUrl(job_name, job_id):
    """Fetch job url by job name and job id (Build Number)."""
    test_cases = TestCaseExecution.query.filter_by(build_number=job_id, job_name=f"Trident/{job_name.lower()}").all()

    if not test_cases:
        return jsonify({"error": "Test case execution not found"}), 404

    test_details = list(set(test.to_dict().get('job_url') for test in test_cases))

    return jsonify(test_details)


@shared_bp.route('/getInProgressJobs/<string:job_name>', methods=['GET'])
def getInProgressJobs(job_name):
    """Fetch in progress jobs by job name."""
    test_cases = TestCaseExecution.query.filter_by(job_name=f"Trident/{job_name.lower()}", job_status='IN PROGRESS')\
        .order_by(TestCaseExecution.timestamp.desc()).all()

    if not test_cases:
        return jsonify({"error": "Test case execution not found"}), 404

    test_details = list(set(test.to_dict().get('build_number') for test in test_cases))

    return jsonify(test_details)


@shared_bp.route('/getJobParameters/<string:job_name>/<string:job_id>', methods=['GET'])
def getJobParameters(job_name, job_id):
    """Fetch job parameters by job name and job id (Build Number)."""
    test = TestCaseExecution.query.filter_by(build_number=job_id, job_name=f"Trident/{job_name.lower()}").first()

    if not test:
        return jsonify({"error": "Test case execution not found"}), 404

    test_details = json.loads(test.to_dict().get('job_params')) \
        if not isinstance(test.to_dict().get('job_params'), dict) else test.to_dict().get('job_params')

    return jsonify(test_details)


@shared_bp.route('/rerun-test/<string:test_id>', methods=['GET'])
def rerun_test_form(test_id):
    """Render the test re-run form with dynamic XPOOL_LABELS."""
    test_case = TestCaseExecution.query.filter_by(execution_stamp=test_id).first()

    if not test_case:
        flash("Test case execution not found!", "error")
        return redirect(url_for('home'))

    xpool_labels = test_case.xpool_labels or "No labels found"

    return render_template('rerun_test.html', test_id=test_id, xpool_labels=xpool_labels)


@shared_bp.route('/test-details/<string:execution_stamp>', methods=['GET'])
def get_test_details(execution_stamp):
    """Fetch test details by execution_stamp (Test ID)."""
    test_case = TestCaseExecution.query.filter_by(execution_stamp=execution_stamp).first()

    if not test_case:
        return jsonify({"error": "Test case execution not found"}), 404

    test_details = test_case.to_dict()

    return jsonify(test_details)


@shared_bp.route('/rerun-test/submit', methods=['POST'])
def rerun_test_submit():
    """Handles form submission, updates job params dynamically, and triggers Jenkins job."""

    execution_stamp = request.form.get('test_id')
    username = request.form.get('username')
    ibid = request.form.get('ibid') if request.form.get('ibid') else None
    xpool_groups = request.form.get('xpool-groups') if request.form.get('xpool-groups') else None
    cluster_name = request.form.get('cluster-name') if request.form.get('cluster-name') else None
    test_case = TestCaseExecution.query.filter_by(execution_stamp=execution_stamp).first()

    if not test_case:
        flash("Test case execution not found!", "error")
        return redirect(url_for('shared.rerun_test_form', test_id=execution_stamp))

    if not test_case.job_name:
        flash("Job name is missing from test execution data!", "error")
        return redirect(url_for('shared.rerun_test_form', test_id=execution_stamp))

    xpool_labels = test_case.xpool_labels or ''

    jenkins = create_jenkins_object()

    job_params = test_case.job_params or {}

    job_params["TEST_CMD"] = execution_stamp
    job_params["USERNAME"] = username
    job_params["JOBLABEL"] = xpool_labels
    job_params.pop("XPOOL_LABEL", None)

    if cluster_name:
        job_params["CLUSTER_NAME"] = cluster_name
    else:
        job_params.pop("CLUSTER_NAME", None)
        job_params["GROUP"] = xpool_groups

    if ibid:
        job_params["IBID"] = ibid
    else:
        job_params.pop("IBID", None)

    try:
        job_data = trigger_job(jenkins, test_case.job_name, job_params)
        build_number = job_data['build_number']
    except Exception as e:
        return jsonify({"error": f"Failed to trigger Jenkins job: {str(e)}"}), 500

    if not build_number:
        return jsonify({"error": "Jenkins job did not start in time"}), 500

    job_url = f"{jenkins.server}/job/{test_case.job_name}/{build_number}/"
    return jsonify({"message": "Test re-run initiated successfully", "job_url": job_url})


@shared_bp.route('/check-cluster', methods=['GET'])
def check_cluster():
    """Check if the provided cluster is suitable for the test based on xpool_labels."""

    cluster_name = request.args.get('cluster_name')
    execution_stamp = request.args.get('test_id')

    if not cluster_name:
        return jsonify({"error": "Cluster name is required"}), 400

    test_case = TestCaseExecution.query.filter_by(execution_stamp=execution_stamp).first()

    if not test_case:
        return jsonify({"error": "Test case execution not found"}), 404

    xpool_labels = test_case.xpool_labels if test_case.xpool_labels else ""

    is_suitable = len(xpool_by_labels_and_group(action='list', free=False, xpool_labels=xpool_labels,
                                                cluster=cluster_name)) > 0

    return jsonify({"suitable": is_suitable, "xpool_labels": xpool_labels})


def user_can_update(username, table_name, column_names=None, column_values=None):
    """
    Checks if `username` is allowed to update a particular row in `table_name`.

    Returns a tuple: (allowed, message)

    Rules:
      - admin: can always update any table, any row.
      - guest: cannot update anything.
      - user: can update only if:
          1) table_name is in user.table_names (comma-separated)
             or
          2) at least one of ['user', 'username', 'user_name'] columns exist in table and
             matches `username` in that row.
    """
    if table_name == 'jira_component_by_uid':
        return True, f"User have permissions for table '{table_name}'."
    user = User.query.filter_by(username=username).first()
    if not user:
        # No such user => no permissions
        return False, "No such user found; cannot update."

    # 1) Guest => never allowed to update
    if user.role == 'guest':
        return False, "Guest users cannot update data."

    # 2) Admin => unrestricted
    if user.role == 'admin':
        return True, "User is admin and can update any table & row"
    if table_name in ADMIN_TABLES:
        return False, "Only admins can update this table"

    # 3) "user" => must match table or row ownership
    if user.role == 'user':

        # 3.1) check user table permissions
        allowed_tables = []
        if user.table_names:
            allowed_tables = [t.strip() for t in user.table_names.split(',')]

        # Check if this table is in the user's allowed list
        if table_name in allowed_tables:
            return True, f"User '{username}' have permissions for table '{table_name}'."

        # 3.2) check if the row "belongs" to user
        # i.e., find if any of the recognized columns has the user's name
        allowed_user_cols = ['user', 'username', 'user_name']

        row_username_value = None
        for col_name, col_value in zip(column_names, column_values):
            if col_name.lower() in allowed_user_cols:
                row_username_value = col_value
                break
        if row_username_value is None:
            return False, "Need permissions for this table"
        elif row_username_value == username:
            return True, f"User '{username}' can update row in table '{table_name}'."
        else:
            return False, "Row does not belong to user."

    # If some unknown role, default to denying
    return False, "Unknown role; cannot update."


# Example User model
class User(db.Model):
    """ User model. """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    role = db.Column(db.String(20), nullable=False, default='guest')
    table_names = db.Column(db.String(255))
    login_count = db.Column(db.Integer, default=0)
    edits_count = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime)


def login_required(f):
    """ Login required decorator. """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('test_set_bp.login'))
        return f(*args, **kwargs)
    return decorated_function


@test_set_bp.route('/login', methods=['GET', 'POST'])
def login():
    """ Login page. """
    if request.method == 'GET':
        return render_template('login.html')

    username = request.form.get('username')
    password = request.form.get('password')

    if not username or not password:
        return "Username or password cannot be empty", 400

    try:
        ldap_obj = ldap.Ldap()
        ldap_obj.authenticate_user(username, password)  # Replace with your actual LDAP logic
    except LDAPInvalidCredentialsResult:
        return "Invalid username or password", 401
    except Exception as e:
        print(f"LDAP error: {e}")
        return "An error occurred during LDAP authentication", 500

    # Check if user exists in local DB
    existing_user = User.query.filter_by(username=username).first()
    if not existing_user:
        # Create a new user
        new_user = User(
            username=username,
            role='guest',
            login_count=1,                # First login
            last_login=datetime.utcnow()  # Record initial login time
        )
        db.session.add(new_user)
        db.session.commit()

        session['user_id'] = new_user.id
        session['username'] = new_user.username
    else:
        # Existing user: increment login_count and update last_login
        existing_user.login_count = (existing_user.login_count or 0) + 1
        existing_user.last_login = datetime.utcnow()
        db.session.commit()

        session['user_id'] = existing_user.id
        session['username'] = existing_user.username

    return redirect('/')


# Route to display tables
@test_set_bp.route('/')
@login_required
def show_tables():
    """ Show all tables in the connected database. """
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()  # List all tables in the connected database
    return render_template('table_list.html', tables=tables)


@test_set_bp.route('/add_row_to_table', methods=['POST'])
def add_row_to_table():
    """ Add a new row to a specified table. """
    table_name = request.args.get('table_name')
    if not table_name:
        return jsonify(success=False, error="No table_name provided"), 400

    # --------------------------------
    # Check User Session + Permissions
    # --------------------------------
    username = session.get('username')
    if not username:
        return "User not logged in", 401

    # new_row_data is a dict like {"username": "alice", "age": "30"}
    new_row_data = request.get_json()
    if not new_row_data:
        return jsonify(success=False, error="No JSON body provided"), 400

    # Example: columns = ["username", "age"], values = ["alice", "30"]
    columns = list(new_row_data.keys())
    values = list(new_row_data.values())

    is_allowed, reason = user_can_update(
        username=username,
        table_name=table_name,
        column_names=columns,
        column_values=values
    )
    if not is_allowed:
        return jsonify({"success": False, "error": reason}), 403

    # Build the INSERT statement with named placeholders (e.g. :username, :age)
    # 1) Create a comma-separated list of quoted column names
    col_names_str = ", ".join(f'"{col}"' for col in columns)
    # 2) Create placeholders for each column like :colname
    placeholders = ", ".join(f":{col}" for col in columns)

    # Our final SQL uses named placeholders
    # Example: INSERT INTO "my_table" ("username","age") VALUES (:username,:age)
    sql = text(f'INSERT INTO "{table_name}" ({col_names_str}) VALUES ({placeholders})')

    # Build a dict mapping placeholder->value, e.g. { "username": "alice", "age": "30" }
    param_dict = {}
    for col, val in new_row_data.items():
        param_dict[col] = val

    print("SQL:", sql)
    print("Param Dict:", param_dict)

    try:
        with db.engine.begin() as conn:
            # Pass a single dictionary for the named placeholders
            conn.execute(sql, param_dict)

        return jsonify(success=True), 200

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@test_set_bp.route('/get_table_columns', methods=['GET'])
def get_table_columns():
    """ Get columns for a specified table. """
    table_name = request.args.get('table_name')
    if not table_name:
        return jsonify(success=False, error="No table_name provided"), 400

    inspector = inspect(db.engine)  # use your engine
    # We'll fetch columns and build a list of { name, type }
    try:
        col_info = inspector.get_columns(table_name)  # reflection
        columns = []
        for c in col_info:
            if str(c["type"]) == "TIMESTAMP":
                continue
            columns.append({
                "name": c["name"],
                "type": str(c["type"])
            })
        return jsonify(success=True, columns=columns), 200

    except Exception as e:
        return jsonify(success=False, error=str(e)), 500


@test_set_bp.route('/get_column_values', methods=['GET'])
def get_column_values():
    """ Get column values for a specified table and column. """
    try:
        table_name = request.args.get('table_name')
        column_name = request.args.get('column_name')
        search_query = request.args.get('search_query', '').strip()

        if not table_name or not column_name:
            return {"success": False, "error": "Missing table or column name"}, 400

        query = f"SELECT DISTINCT {column_name} FROM {table_name}"
        params = {}

        # Add search filter if provided
        if search_query:
            query += " WHERE CAST({column_name} AS TEXT) ILIKE :search_query"
            params['search_query'] = f"%{search_query}%"

        result = db.session.execute(text(query), params)
        values = [row[0] for row in result.fetchall() if row[0] is not None]

        return {"success": True, "values": values}
    except Exception as e:
        return {"success": False, "error": str(e)}, 500


# Route to display a specific table's data
@test_set_bp.route('/table/<string:table_name>')
@login_required
def show_table_data(table_name, reset=False, export=False, ordered_columns=None):
    """
    Display a specific table's data.

    :param table_name: Name of the table to display.
    :param reset: If True, reset the filter parameters.
    :param export: If True, export the table data as a CSV file.
    :param ordered_columns: A list of column names in the desired order.
    :return: HTML template with the table data.
    """
    try:
        inspector = inspect(db.engine)
        if table_name not in inspector.get_table_names():
            return f"Error: Table '{table_name}' does not exist."

        # Get column names for dropdown filter
        column_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = :table_name
        """)

        # Execute the query
        column_result = db.session.execute(column_query, {'table_name': table_name})
        column_names = [row[0] for row in column_result.fetchall()]

        # If no specific order is provided, use SELECT *
        # Otherwise, SELECT only the columns provided in the list
        if ordered_columns:
            column_str = ", ".join(ordered_columns)
        else:
            column_str = "*"

        # Construct dynamic SQL query
        base_query = f"SELECT {column_str} FROM {table_name}"
        where_clauses = []
        params = {}

        # Search and column filter parameters
        # Fetch multiple filters
        f_columns = [] if reset else request.args.getlist('column[]')
        f_filter = [] if reset else request.args.getlist('filter[]')
        f_include_exclude = [] if reset else request.args.getlist('include_exclude[]')
        operators = []
        i = 0
        while i < len(f_include_exclude):
            if i + 1 < len(f_include_exclude) and f_include_exclude[i + 1] == "include":
                # This filter's final mode is "include"
                operators.append("=")
                i += 2
            else:
                # This filter's final mode is "exclude"
                operators.append("!=")
                i += 1
        print(f_columns, f_filter, operators, f_include_exclude)
        # Add to WHERE clauses
        # Ensure only valid column-value pairs are applied
        for col, val, op in zip(f_columns, f_filter, operators):
            if col and val.strip():  # Check both column and value are non-empty
                unique_param = f"param_{len(params)}"  # Generate unique param name
                where_clauses.append(f"{col} {op} :{unique_param}")
                params[unique_param] = val.strip()

        # Build WHERE clause if there are filters
        if where_clauses:
            base_query += " WHERE " + " AND ".join(where_clauses)

        # Pagination parameters
        page = request.args.get('page', 1, type=int)
        rows_per_page = 50
        start = (page - 1) * rows_per_page
        end = start + rows_per_page

        # Execute the query without pagination
        query = db.session.execute(text(base_query), params)
        columns = query.keys()
        rows = query.fetchall()

        # Export the table data as a CSV file
        if export:
            return columns, rows

        # Reverse the rows for newest-first display
        rows = rows[::-1]
        # Apply pagination to the reversed rows
        paginated_rows = rows[start:end]
        total_rows = len(rows)
        # Construct the filter parameters
        filters = [] if reset else [
            {"column": col, "value": val, "operator": op}
            for col, val, op in zip(f_columns, f_filter, operators)
            if col and val and op
        ]

        return render_template(
            'table_data.html',
            table_name=table_name,
            columns=columns,
            f_columns=f_columns,
            f_filter=f_filter,
            f_include_exclude=f_include_exclude,
            rows=paginated_rows,
            page=page,
            column_names=column_names,
            total_rows=total_rows,
            current_count=len(paginated_rows),
            filters=filters,
            start=start,
            end=min(end, total_rows),
        )

    except Exception as e:
        return f"Error: {str(e)}"


@test_set_bp.route('/update_row', methods=['POST'])
def update_row():
    """
    Update a row in a table.
    """
    try:
        # --------------------------------
        # 1) Parse Incoming Data
        # --------------------------------
        data = request.json
        table_name = request.args.get('table_name')

        original_columns = data.get('original_columns')  # List of original column names
        original_values = data.get('original_values')    # List of original values
        changed_columns = data.get('changed_columns')    # List of changed column names
        changed_values = data.get('changed_values')      # List of changed values

        # For debugging
        print("Table Name:", table_name)
        print("Original Columns:", original_columns)
        print("Original Values:", original_values)
        print("Changed Columns:", changed_columns)
        print("Changed Values:", changed_values)

        # --------------------------------
        # 2) Check User Session + Permissions
        # --------------------------------
        username = session.get('username')
        if not username:
            return "User not logged in", 401

        is_allowed, reason = user_can_update(
            username=username,
            table_name=table_name,
            column_names=original_columns,
            column_values=original_values
        )
        if not is_allowed:
            return jsonify({"success": False, "error": reason}), 403

        # --------------------------------
        # 3) Basic Validations
        # --------------------------------
        if not table_name or not original_columns or not original_values \
           or not changed_columns or not changed_values:
            return jsonify({"success": False, "error": "Missing required data"}), 400

        # Prevent SQL injection by ensuring table_name is a valid identifier
        if not table_name.isidentifier():
            return jsonify({"success": False, "error": "Invalid table name"}), 400

        # --------------------------------
        # 4) Helper Functions
        # --------------------------------
        def sanitize_json(value):
            """If value is JSON-like string, reformat it safely; else return as-is."""
            if not isinstance(value, str):
                return value
            try:
                # Replace single quotes with double quotes
                sanitized = value.replace("'", '"')
                # Validate and load JSON
                parsed = json.loads(sanitized)
                # Re-dump to ensure proper formatting
                return json.dumps(parsed)
            except (ValueError, TypeError):
                return value  # Not valid JSON, return raw

        def detect_type(value):
            """Return a string representing the 'type' of the value."""
            if isinstance(value, str):
                try:
                    # Try parsing as JSON to see if it's dict or list
                    parsed = json.loads(value.replace("'", '"'))
                    if isinstance(parsed, dict):
                        return "dict"
                    elif isinstance(parsed, list):
                        return "list"
                except (ValueError, TypeError):
                    pass
                return "string"
            return type(value).__name__

        def is_datetime_like(value):
            """Returns True if 'value' is a string that can be parsed as a datetime."""
            if not isinstance(value, str):
                return False
            try:
                date_parser(value)
                return True
            except (ValueError, TypeError):
                return False

        def parse_value_as_best_type(val):
            """
            Attempts to convert digit-only strings to int, etc.
            Extend this if you want to handle floats, etc.
            """
            if val is None or val == 'None':
                return None
            if isinstance(val, str) and val.isdigit():
                # Convert purely numeric string to integer
                return int(val)
            return val

        # --------------------------------
        # 5) Cross-Check Type Consistency
        # --------------------------------
        # (Ensures changed_value type matches original_value type)
        for col, changed_val in zip(changed_columns, changed_values):
            if col in original_columns:
                orig_index = original_columns.index(col)
                orig_val = original_values[orig_index]
                orig_type = detect_type(orig_val)
                changed_type = detect_type(changed_val)
                if orig_type != changed_type:
                    return jsonify({
                        "success": False,
                        "error": f"Type mismatch in column '{col}': "
                                 f"original type is '{orig_type}', "
                                 f"but updated value is of type '{changed_type}'. "
                                 "Please ensure the value matches the original type and syntax."
                    }), 400

        # --------------------------------
        # 6) Build WHERE Clause
        # --------------------------------
        where_clauses = []
        for col, val in zip(original_columns, original_values):
            # Skip datetime-like columns to avoid precision mismatches
            if is_datetime_like(val):
                continue

            val = sanitize_json(val)
            # Convert strings-of-digits to int
            val = parse_value_as_best_type(val)

            if val is None:
                continue
            elif isinstance(val, str) and val.startswith('{'):
                continue
            else:
                where_clauses.append(f'"{col}" = :orig_{col}')

        where_clause = " AND ".join(where_clauses)
        if not where_clause:
            # If all columns were datetime-like or otherwise excluded
            return jsonify({
                "success": False,
                "error": "No valid columns available for WHERE clause."
            }), 400

        # --------------------------------
        # 7) Build SET Clause
        # --------------------------------
        set_clauses = []
        for col, val in zip(changed_columns, changed_values):
            val = sanitize_json(val)
            val = parse_value_as_best_type(val)
            if isinstance(val, str) and val.startswith('{'):
                set_clauses.append(f'"{col}" = :new_{col}')
            else:
                set_clauses.append(f'"{col}" = :new_{col}')

        set_clause = ", ".join(set_clauses)

        # --------------------------------
        # 8) Final Query + Params
        # --------------------------------
        query = f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause}'
        print("Query:", query)

        params = {}
        # original values
        for col, val in zip(original_columns, original_values):
            if not is_datetime_like(val):
                # Only pass the columns we used in WHERE
                val = sanitize_json(val)
                val = parse_value_as_best_type(val)
                params[f"orig_{col}"] = val

        # changed values
        for col, val in zip(changed_columns, changed_values):
            val = sanitize_json(val)
            val = parse_value_as_best_type(val)
            params[f"new_{col}"] = val

        print("Params:", params)

        # Execute
        db.session.execute(text(query), params)
        db.session.commit()

        return jsonify({"success": True}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@test_set_bp.route('/batch_update_rows', methods=['POST'])
def batch_update_rows():
    """
    Apply the same column changes to multiple rows identified by their primary key.

    Expected JSON payload:
    {
        "table_name": "test_case_config",
        "id_column": "tc_pid",
        "row_ids": ["TC-89471", "TC-2471"],
        "changed_columns": ["xpool_labels", "username"],
        "changed_values": ["Riptide", "new_user"]
    }
    """
    try:
        # ---- 1) Parse Incoming Data ----
        data = request.json
        table_name = data.get('table_name')
        id_column = data.get('id_column')
        row_ids = data.get('row_ids', [])
        changed_columns = data.get('changed_columns', [])
        changed_values = data.get('changed_values', [])

        # ---- 2) Check User Session + Permissions ----
        username = session.get('username')
        if not username:
            return jsonify({"success": False, "error": "User not logged in"}), 401

        is_allowed, reason = user_can_update(
            username=username,
            table_name=table_name,
            column_names=[id_column],
            column_values=[row_ids[0]] if row_ids else ['']
        )
        if not is_allowed:
            return jsonify({"success": False, "error": reason}), 403

        # ---- 3) Validations ----
        if not table_name or not id_column or not row_ids or not changed_columns or not changed_values:
            return jsonify({"success": False, "error": "Missing required data"}), 400

        if not table_name.isidentifier():
            return jsonify({"success": False, "error": "Invalid table name"}), 400

        if len(changed_columns) != len(changed_values):
            return jsonify({"success": False, "error": "Columns and values length mismatch"}), 400

        # ---- 4) Helper to sanitize JSON values ----
        def sanitize_json(value):
            if not isinstance(value, str):
                return value
            try:
                sanitized = value.replace("'", '"')
                parsed = json.loads(sanitized)
                return json.dumps(parsed)
            except (ValueError, TypeError):
                return value

        def parse_value_as_best_type(val):
            if val is None or val == 'None':
                return None
            if isinstance(val, str) and val.isdigit():
                return int(val)
            return val

        # ---- 5) Build SET clause (with optional JSON merge) ----
        merge_modes = data.get('merge_modes', [])
        set_clauses = []
        params = {}
        for i, (col, val) in enumerate(zip(changed_columns, changed_values)):
            mode = merge_modes[i] if i < len(merge_modes) else 'replace'
            val = sanitize_json(val)
            if mode == 'merge':
                # Merge new JSON keys into existing value: existing || new
                set_clauses.append(f'"{col}" = COALESCE("{col}"::jsonb, \'{{}}\'::jsonb) || :new_{col}::jsonb')
                params[f"new_{col}"] = val if isinstance(val, str) else json.dumps(val)
            else:
                val = parse_value_as_best_type(val)
                set_clauses.append(f'"{col}" = :new_{col}')
                params[f"new_{col}"] = val

        set_clause = ", ".join(set_clauses)

        # ---- 6) Build WHERE clause with IN ----
        id_placeholders = []
        for i, rid in enumerate(row_ids):
            param_name = f"id_{i}"
            id_placeholders.append(f":{param_name}")
            params[param_name] = rid

        where_clause = f'"{id_column}" IN ({", ".join(id_placeholders)})'

        # ---- 7) Execute ----
        query = f'UPDATE "{table_name}" SET {set_clause} WHERE {where_clause}'
        logger.info(f"Batch update query: {query}")
        logger.info(f"Batch update params: {params}")

        result = db.session.execute(text(query), params)
        db.session.commit()

        updated_count = result.rowcount
        return jsonify({"success": True, "updated_count": updated_count}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Batch update error: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@test_set_bp.route('/table/<string:table_name>/refresh')
def refresh_table_data(table_name):
    """
        Refresh data for a table.
    """
    is_allowed, reason = user_can_update(
        username=session.get('username', None),
        table_name='test_runner_mdt'
    )
    if not is_allowed:
        return redirect('/table/' + table_name)

    job_name = None
    if table_name == 'test_runner_mdt':
        job_name = 'Trident/test_runner_utils/update_test_runner_mdt'
    elif table_name == 'test_cases' or table_name == 'test_runs':
        job_name = 'Trident/test_runner_utils/update_test_runner_db'

    if job_name:
        jenkins = create_jenkins_object()
        build_params = {'QAENV': '/home/trqa-dev'}
        try:
            job_data = trigger_job(jenkins, job_name, build_params)
            build_number = job_data['build_number']
        except Exception as e:
            return jsonify({"error": f"Failed to trigger Jenkins job: {str(e)}"}), 500

        if not build_number:
            return jsonify({"error": "Jenkins job did not start in time"}), 500

        time.sleep(2)
        # Check if the job is still in progress
        while jenkins.is_in_progress(job_name, build_number):
            time.sleep(5)

    return redirect('/table/' + table_name)

# Route to export table data to CSV
@test_set_bp.route('/table/<string:table_name>/export')
def export_table_data(table_name):
    """
        Export a table as a CSV file in a specified column order.
    :param table_name: Name of the table to export.
    :return: CSV file containing the table data.
    """
    ordered_columns = ORDERED_COLUMNS if table_name == "test_case_config" else None
    try:
        inspector = inspect(db.engine)
        if table_name not in inspector.get_table_names():
            return f"Error: Table '{table_name}' does not exist."

        columns, rows = show_table_data(table_name, export=True, ordered_columns=ordered_columns)

        # Write data to CSV
        export_file = os.path.join(os.path.dirname(__file__), f"{table_name}_export.csv")
        with open(export_file, 'w', newline='', encoding='utf-8') as csv_file:
            writer = csv.writer(csv_file)
            # Write the header row
            writer.writerow(columns)
            # Write each subsequent data row
            writer.writerows(rows)

        # Return the CSV file as a download
        return send_file(export_file, as_attachment=True, download_name=f"{table_name}_export.csv")

    except Exception as e:
        return f"Error: {str(e)}"

@test_plan_bp.route('/testplans', methods=['GET'])
def get_test_plans():
    """
    Retrieve a list of test plans based on optional filters such as test status,
    release, responsible team, run ID, test case ID, test level, execution priority,
    and continuous testing category.

    Query parameters:
        - test_status: Filter by test status (e.g., "Passed", "Failed").
        - release: Filter by release name.
        - responsible_team: Filter by the responsible team.
        - run_id: Filter by specific run ID.
        - testcase_id: Filter by specific test case ID.
        - test_level: Filter by test level (e.g., "Unit", "Integration").
        - execution_priority: Filter by execution priority (0-10).
        - is_ct: Filter by whether it's part of continuous testing.

    Returns:
        JSON response containing a list of matching test plans.
    """
    # Get query parameters
    test_status = request.args.get('test_status')
    release = request.args.get('release')
    responsible_team = request.args.get('responsible_team')
    run_id = request.args.get('run_id')
    testcase_id = request.args.get('testcase_id')
    test_level = request.args.get('test_level')
    execution_priority = request.args.get('execution_priority')
    is_ct = request.args.get('is_ct')

    try:
        query = TestPlan.query

        # Apply filters
        if run_id:
            query = query.filter(TestPlan.run_id == int(run_id))
        if testcase_id:
            query = query.filter(TestPlan.testcase_id == int(testcase_id))
        if test_status:
            query = query.filter(TestPlan.properties['Status'].astext == test_status)
        if release:
            query = query.filter(TestPlan.release == release)
        if responsible_team:
            query = query.join(TestPlan.test_run).filter(
                TestRun.properties['Responsible Team'].astext == responsible_team
            )
        if test_level:
            query = query.join(TestPlan.test_run).filter(
                TestRun.properties['Test Level'].astext == test_level
            )
        if execution_priority:
            query = query.filter(
                cast(TestPlan.properties['Execution Priority'].astext, db.Float) == float(execution_priority)
            )
        if is_ct is not None:
            query = query.filter(TestPlan.is_ct == (is_ct.lower() == 'true'))

        # Fetch results
        test_plans = query.all()

        # Serialize the results
        schema = TestPlanSchema(many=True)
        return jsonify(schema.dump(test_plans)), 200

    except ValueError as e:
        return jsonify({"message": "Invalid query parameter value."}), 400
    except Exception as e:
        return jsonify({"message": "Internal server error."}), 500


def get_priority(test, priority_rule):
    status_priority = priority_rule.get('current_status', {}).get(test['current_status'], 0)
    level_priority = priority_rule.get('test_level', {}).get(test.get('test_level', ''), 0)
    category_priority = priority_rule.get('category', {}).get(test.get('category', ''), 0)
    priority = status_priority + level_priority + category_priority
    if test['current_status'] == 'No Run' and (test.get('add_appliance') or test.get('federation')):
        priority += test.get('add_appliance') and 25 or test.get('federation_size') and 20
    return priority

def sort_tests_by_priority(tests, priority_rule):
    def get_priority(test):
        status_priority = priority_rule.get('current_status', {}).get(test['current_status'], 0)
        level_priority = priority_rule.get('test_level', {}).get(test.get('test_level', ''), 0)
        category_priority = priority_rule.get('category', {}).get(test.get('category', ''), 0)
        return status_priority + level_priority + category_priority
    
    return sorted(tests, key=get_priority, reverse=True)


@test_set_bp.route('/testsets', methods=['GET'])
def get_test_sets():
    test_sets = TestSet.query.all()
    return jsonify([test_set.to_dict() for test_set in test_sets])


@test_set_bp.route('/testsets/<string:name>', methods=['GET'])
def get_test_set(name):
    test_set = TestSet.query.get(name)
    if not test_set:
        return jsonify({"error": "Test set not found"}), 404
    query = TestPlan.query
    test_set_dict = test_set.to_dict()
    filter_data = test_set_dict.get('filter', {})
    dev_test = filter_data.get('dev_test')
    pr_tester = filter_data.get('pr_tester')
    priority_rule = test_set_dict.get('priority_rule')
    query = query.filter(or_(TestPlan.category != 'Pre-Merge', TestPlan.category==None))
    if not dev_test and not pr_tester:
        query = query.filter(or_(TestPlan.category != 'Mainline Stability', TestPlan.category==None))
    if filter_data:
        if 'run_id' in filter_data:
            query = query.filter_by(run_id=int(filter_data['run_id']))
        if 'test_status' in filter_data:
            query = query.filter(TestPlan.properties['Status'].astext == filter_data['test_status'])
        if 'tc_list' in filter_data:
            query = query.filter(TestPlan.testcase_pid.in_(filter_data['tc_list']))
        if 'release' in filter_data:
            query = query.filter(TestPlan.release == filter_data['release'])
            query = query.filter(TestPlan.is_active_cycle.is_(True))
        if 'use_config_table' in filter_data:
            config_query = TestConfig.query
            test_configs = config_query.all()
            testcase_pid_parts = [i.tc_pid.split('_')[0] for i in test_configs]
            query = query.filter(TestPlan.testcase_pid_prefix.in_(testcase_pid_parts))
        if filter_data.get('executable', '') != 'False':
            query = query.filter(TestPlan.testcase_pid_prefix.in_([i.tc_pid for i in test_configs if i.executable]))
        # Add other filter conditions as needed
        if 'is_ct' in filter_data:
            query = query.filter(TestPlan.is_ct == filter_data['is_ct'])

    test_plans = query.all()
    schema = TestPlanSchema(many=True)
    test_plans = jsonify(schema.dump(test_plans))
    data = json.loads(test_plans.response[0].decode('utf-8'))
    if filter_data and 'team' in filter_data:
        data = [test for test in data if test['responsible_team'] == filter_data['team']]
    tc_ids = [i['testcase_pid'].split('_')[0] for i in data] if not pr_tester else filter_data['tc_list']
    config_query = TestConfig.query
    config_query = config_query.filter(TestConfig.tc_pid.in_(tc_ids))
    if not dev_test and not pr_tester:
        config_query = config_query.filter(TestConfig.is_dev == False)
    test_configs = config_query.all()
    test_configs_dict = {i.tc_pid: i.to_dict() for i in test_configs}
    test_list = []
    data = {i['testcase_pid']: i for i in data} if not pr_tester else {i: {'testcase_pid': i} for i in tc_ids}
    for plan in data.values():
        config = test_configs_dict.get(plan['testcase_pid'].split('_')[0], {})
        if not config:
            continue
        config['test_init_params'].update({"--skipPanicDetector": ""})
        if config.get('test_init_params', {}).get('--failOnPanics') is not None:
            config['test_init_params'].pop('--failOnPanics')
            config['test_case_params'].update({"--failOnPanic": ""})
        if config.get('test_init_params', {}).get('--failOnMDCorruption') is not None:
            config['test_init_params'].pop('--failOnMDCorruption')
            config['test_case_params'].update({"--failOnMDCorruption": ""})
        if 'NVME' in config.get('xpool_labels', '') and not config.get('os_environ', {}).get('HBA_SETUP'):
            import random
            config['os_environ'].update({'HBA_SETUP': random.choice(['NVMeTCP', 'NVMeOFC'])})
            xpool_labels = config.get('xpool_labels').replace('NVME', 'NVMeOF-FC' if config['os_environ']['HBA_SETUP'] == 'NVMeOFC' else '')
            config['xpool_labels'] = xpool_labels
        config.update({'cycles': plan.get('cycles', 1)})
        config.update({'tester': config.get('username') or 'rahamg'})  # TODO need to decide from whre we want to get this value
        version = plan.get('release', '') or filter_data.get('release', '')
        add_app_params = config.get('os_environ', {}).get('ADD_APPLIANCE_PREPARE')
        if add_app_params:
            add_app_params = add_app_params.replace('ibid', str(get_the_latest_ibid(version)['ibid_id']))
            config['os_environ']['ADD_APPLIANCE_PREPARE'] = add_app_params
        if config.get('ndu'):
            qtest_version = plan['source_version'].replace('V', "")
            try:
                source_rel = qtest_version if (len(qtest_version) == 5 or qtest_version[-1] != '0') else qtest_version[:-2]
            except:
                logger.error(f"no source_version in QTEST for NDU test run {plan['pid']}")
                continue
            #source_rel = qtest_version if (len(qtest_version) == 5 or qtest_version[-1] != '0') else qtest_version[:-2]
            build_revision = get_the_latest_ibid(version).get('build_revision')
            if build_revision:
                target_rel = build_revision.split('-')[0]
                target_rel = target_rel[:-2]
                nduData_query = NduMapping.query
                nduData_query = nduData_query.filter_by(target_rel=target_rel, source_rel=source_rel)
                if not nduData_query:
                    logger.error(f'Failed to get NDU mapping for {target_rel} {source_rel}')
                else:
                    source_version = nduData_query[0].value
                    if not source_version:
                        logger.error(f'There is no source_version in NDU mapping for test run {plan["pid"]}')
                        continue
                    config.update({'source_version': nduData_query[0].value})
        test_run = {
            'run_id': plan.get('run_id'),
            'test_id': plan.get('testcase_id'),
            'test_level': plan.get('test_level'),
            'current_status': plan.get('test_status', 'No Run'),
            'execution_status': 'No Run',
            'execution_URLs': [],
            'TR': plan.get('pid'),
            'TC': plan.get('testcase_pid'),
            'version': version,
            'config': config,
            'is_ct': plan.get('is_ct', False),
            'federation_size': 0,
            'add_appliance': config.get('add_appliance', False) == "True",
            'category': plan.get('category')
        }

        if config.get('os_environ', {}).get('NUM_OF_APPLIANCES'):
            test_run.update({'federation_size': config.get('os_environ', {}).get('NUM_OF_APPLIANCES')})
        elif config.get('os_environ', {}).get('ADD_APPLIANCES'):
            test_run.update({'federation_size': sum(map(int, config.get('os_environ', {}).get('ADD_APPLIANCES').split(',')))})
        test_list.append(test_run)
    # TODO add values for num of pass/fail + MDT status + identify Failed not Analyzed
    if not priority_rule:
        priority_rule = {'current_status': {'No Run': 0.9, 'Passed': 0.1, 'Failed': 0.3, 'Failed not Analyzed': 0.2},
                         "test_level": {'MPTC': 1, 'Legacy': 0.5},
                         "category": {'High Frequency': 2, 'Medium Frequency': 1, 'Low Frequency': 0.5, 'Mainline Stability': 2, 'Pre-Merge': 2}}
    if priority_rule:
        for test in test_list:
            test['priority'] = get_priority(test, priority_rule)
        test_list = sorted(test_list, key=lambda x: x['priority'], reverse=True)

    test_set_dict['tests'] = test_list
    return jsonify(test_set_dict)

@test_plan_bp.route('/testsets/<string:name>', methods=['PUT'])
def update_test_set(name):
    data = request.get_json()
    test_set = TestSet.query.get(name)
    
    if not test_set:
        return jsonify({"error": "Test set not found"}), 404
    
    test_set.name = data.get('name', test_set.name)
    test_set.filter = data.get('filter', test_set.filter)
    test_set.priority_rule = data.get('priority_rule', test_set.priority_rule)
    test_set.server = data.get('server', test_set.server)
    test_set.execuation_time_zone = data.get('execuation_time_zone', test_set.execuation_time_zone)
    test_set.jenkins_server = data.get('jenkins_server', test_set.jenkins_server)
    test_set.xpool_username = data.get('xpool_username', test_set.xpool_username)
    test_set.xpool_groups = data.get('xpool_groups', test_set.xpool_groups)
    test_set.qaenv = data.get('qaenv', test_set.qaenv)

    db.session.commit()
    
    return jsonify(test_set.to_dict())


@test_execution_bp.route('/testset_execution', methods=['GET'])
def get_tests_set_execution():
    test_sets_execution = TestCaseExecution.query.all()
    return jsonify([test_set.to_dict() for test_set in test_sets_execution])
    # return jsonify(test_sets_execution.to_dict()), 201
#
# @test_execution_bp.route('/testset_execution/<string:name>/add_tests', methods=['PUT'])
# def add_tests_to_execution(name):
#     data = request.get_json()
#
#
#     test_set_execution = TestSetExecution.query.filter_by(name=name).first()
#
#     if not test_set_execution:
#         return jsonify({"error": "TestSetExecution not found"}), 404
#
#     new_tests = data.get('tests', [])
#
#     if not isinstance(new_tests, list):
#         return jsonify({"error": "Invalid format, 'tests' should be a list"}), 400
#
#     current_tests = test_set_execution.tests
#     updated_tests = current_tests + new_tests
#
#     test_set_execution.tests = updated_tests
#
#     db.session.commit()
#
#     return jsonify(test_set_execution.to_dict()), 200
#
#
# @test_execution_bp.route('/testset_execution/<test_set_name>/tests/<int:run_id>', methods=['PUT'])
# def update_test_in_testset(test_set_name, run_id):
#     data = request.json  # Get new data from the request body
#
#     test_set_execution = TestSetExecution.query.filter_by(name=test_set_name).first()
#
#     if not test_set_execution:
#         return jsonify({"error": "TestSetExecution not found"}), 404
#
#     tests = test_set_execution.tests
#
#     test_to_update = next((test for test in tests if test['run_id'] == run_id), None)
#
#     if not test_to_update:
#         return jsonify({"error": "Test with run_id {} not found".format(run_id)}), 404
#
#     tests = [test for test in tests if test['run_id'] != run_id]
#
#     if 'execution_status' in data:
#         test_to_update['execution_status'] = data['execution_status']
#     if 'execution_urls' in data:
#         test_to_update['execution_urls'].extend(data['execution_urls'])
#
#
#     tests.append(test_to_update)
#
#     test_set_execution.tests = tests
#     db.session.commit()
#
#     return jsonify(test_set_execution.to_dict()), 200


@test_execution_bp.route('/testset_execution/<string:name>/add_server', methods=['PUT'])
def add_server_to_execution(name, ip=None, port=None, qaenv=None):
    """
    Updates the server information for a Test Set Execution.
    Accepts IP and port from the request or function arguments, and optionally qaenv.
    """
    try:
        if not ip:
            ip = request.args.get('ip') or (request.get_json() or {}).get('ip')
        if not port:
            port = request.args.get('port') or (request.get_json() or {}).get('port')
        if not qaenv:
            qaenv = request.args.get('qaenv') or (request.get_json() or {}).get('qaenv')

        if not ip or not port:
            return jsonify({"error": "IP and port are required"}), 400

        # Find the Test Set Execution by name
        test_set_execution = TestSet.query.filter_by(name=name).first()
        if not test_set_execution:
            return jsonify({"error": f"Test Set Execution '{name}' not found"}), 404

        test_set_execution.server = {'ip': ip, 'port': port}
        if qaenv:
            test_set_execution.qaenv = qaenv

        db.session.commit()

        return jsonify(test_set_execution.to_dict()), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

