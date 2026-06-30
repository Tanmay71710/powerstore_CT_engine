import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON
from marshmallow import fields, post_dump
from sqlalchemy.orm import relationship, foreign
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql.expression import func
from flask_marshmallow import Marshmallow

from . import ma, db

class NduMapping(db.Model):
    __tablename__ = 'ndu_mapping_table'

    target_rel = db.Column(db.String(50), primary_key=True)
    source_rel = db.Column(db.String(50))
    value = db.Column(db.String(50))

class TestRun(db.Model):
    __tablename__ = 'test_cases'

    case_id = db.Column(db.Integer, primary_key=True)
    properties = db.Column(JSON)
    pid = db.Column(db.String(50))


class TestRunsSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = TestRun
        load_instance = True
        exclude = ('properties',)
    
    responsible_team = fields.Method("get_responsible_team")
    test_level = fields.Method("get_test_level")
    assigned_to = fields.Method("get_user")
    
    
    def get_responsible_team(self, obj):
        return obj.properties.get('Responsible Team', None)
    
    def get_test_level(self, obj):
        return obj.properties.get('Test Level', None)
    
    def get_user(self, obj):
        return obj.properties.get('Assigned To', None)

        return priority

    properties = fields.Raw()


class TestPlan(db.Model):
    __tablename__ = 'test_runs'

    run_id = db.Column(db.Integer, primary_key=True)
    testcase_id = db.Column(db.String(50), nullable=False)
    run_name = db.Column(db.String(50))
    properties = db.Column(JSON)
    pid = db.Column(db.String(50))
    testcase_pid = db.Column(db.String(50))
    release = db.Column(db.String(50))
    is_ct = db.Column(db.Boolean)
    is_active_cycle = db.Column(db.Boolean, nullable=False, default=False)
    category = db.Column(db.String(50))

    test_run = relationship(
        'TestRun',
        primaryjoin=(testcase_id == foreign(TestRun.case_id)),
        backref='test_plans',
        lazy='joined',
        uselist=False
    )

    def __repr__(self):
        return f"<TestPlan {self.test_id}>"
    
    @hybrid_property
    def testcase_pid_prefix(self):
        return self.testcase_pid.split('_')[0]

    @testcase_pid_prefix.expression
    def testcase_pid_prefix(cls):
        return func.split_part(cls.testcase_pid, '_', 1)


class TestPlanSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = TestPlan
        load_instance = True
        exclude = ('properties',)
    
    test_status = fields.Method("get_test_status")
    responsible_team = fields.Method("get_responsible_team")
    test_level = fields.Method("get_test_level")
    execution_priority = fields.Method("compute_priority")
    cycles = fields.Method("get_required_cycles")
    tester = fields.Method("get_tester")
    assigned_to = fields.Method("get_assigned")
    source_version = fields.Method("get_source_version")


    def get_source_version(self, obj):
        return obj.properties.get('Source Version', None)
    def get_test_status(self, obj):
        return obj.properties.get('Status', None)
    
    def get_tester(self, obj):
        return obj.properties.get('Tester (TCI)', None)

    def get_assigned(self, obj):
        return obj.properties.get('Assigned To', None)

    def get_TC_name(self, obj):
        if obj.test_run:
            return obj.test_run.pid
    
    def get_responsible_team(self, obj):
        return obj.test_run.properties.get('Responsible Team', 'N/A') if obj.test_run else 'N/A'
    
    def get_test_level(self, obj):
        return obj.test_run.properties.get('Test Level', 'N/A') if obj.test_run else 'N/A'
    
    def get_required_cycles(self, obj):
        return obj.test_run.properties.get('Required # of Cycles', 1) if obj.test_run else 1

    def compute_priority(self, obj):
        priority = 0
        test_status = self.get_test_status(obj)
        if obj.test_run:
            if obj.test_run.properties.get('Test Level') == 'MSTP_Core':
                priority += 1
            elif obj.test_run.properties.get('Test Level') == 'MSTP':
                priority += 0.8
        if test_status == 'No run':
            priority += 0.8
        elif test_status == 'Passed':
            priority += 0.2
        elif test_status == 'Failed':
            priority += 0.4
        return priority

    properties = fields.Raw()


class TestSet(db.Model):
    __tablename__ = 'tests_sets'

    name = db.Column(db.String, nullable=False, primary_key=True)
    filter = db.Column(JSON, nullable=True)
    tests = db.Column(JSON, nullable=False)
    priority_rule = db.Column(JSON, nullable=False)
    server = db.Column(JSON, nullable=False)
    qaenv = db.Column(db.String)
    xpool_groups = db.Column(db.String)
    xpool_reservation_limit = db.Column(db.String)
    xpool_username = db.Column(db.String)
    execuation_time_zone = db.Column(db.String)
    jenkins_server = db.Column(db.String)

    # def __init__(self, name, filter=None, tests=None, priority_rule=None, server=None):
    #     self.name = name
    #     self.filter = filter
    #     self.tests = tests or []
    #     self.priority_rule = priority_rule
    #     self.server = server or {}

    def to_dict(self):
        return {
            'name': self.name,
            'filter': self.filter,
            'tests': self.tests,
            "priority_rule": self.priority_rule,
            "server": self.server,
            "qaenv": self.qaenv,
            "xpool_groups": self.xpool_groups,
            "xpool_reservation_limit": self.xpool_reservation_limit,
            "xpool_username": self.xpool_username,
            "execuation_time_zone": self.execuation_time_zone,
            "jenkins_server": self.jenkins_server
        }


class TestCaseExecution(db.Model):
    __tablename__ = 'test_case_execution'

    execution_stamp = db.Column(db.Text, primary_key=True)  # Primary key
    test_set_name = db.Column(db.Text, nullable=False, default="")  # Test set name
    job_name = db.Column(db.Text, nullable=True)  # Jenkins job name
    build_number = db.Column(db.Integer, nullable=True)  # Build number
    job_url = db.Column(db.Text, nullable=True)  # Jenkins job URL
    test_case_name = db.Column(db.Text, nullable=True)  # Test case name
    test_case_status = db.Column(db.Text, nullable=True)  # Status of the test case
    job_status = db.Column(db.Text, nullable=True)  # Status of the Jenkins job
    ibid = db.Column(db.Integer, nullable=True)  # ibid
    timestamp = db.Column(db.TIMESTAMP, nullable=False, default=db.func.now())  # Timestamp with default
    mdt = db.Column(db.Text, nullable=True)  # MDT ticket
    job_params = db.Column(db.JSON, nullable=True)  # Jenkins Job Parameters
    xpool_labels = db.Column(db.Text, nullable=True)  # Xpool Labels
    testinit_stamp = db.Column(db.Text, nullable=True)  # Testinit stamp

    def to_dict(self):
        """
        Convert the SQLAlchemy object to a dictionary for serialization.

        :return: A dictionary representation of the object.
        """
        return {
            'execution_stamp': self.execution_stamp,
            'test_set_name': self.test_set_name,
            'job_name': self.job_name,
            'build_number': self.build_number,
            'job_url': self.job_url,
            'test_case_name': self.test_case_name,
            'test_case_status': self.test_case_status,
            'job_status': self.job_status,
            'ibid': self.ibid,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %H:%M:%S') if self.timestamp else None,
            'mdt': self.mdt,
            'job_params': self.job_params,
            'xpool_labels': self.xpool_labels,
            'testinit_stamp': self.testinit_stamp
        }


class TestConfig(db.Model):
    __tablename__ = 'test_case_config'

    tc_pid = db.Column(db.String, nullable=False, primary_key=True)
    tc_name = db.Column(db.String, nullable=False)
    xpool_labels = db.Column(db.String, nullable=False)
    test_init_params = db.Column(JSON, nullable=False)
    test_case_params = db.Column(JSON, nullable=False)
    os_environ = db.Column(JSON, nullable=False)
    username = db.Column(db.String, nullable=False, default='none')
    lease_params = db.Column(db.String(255), nullable=True)
    special_installation = db.Column(db.String, nullable=True)
    ndu = db.Column(db.Boolean, nullable=True)
    add_appliance = db.Column(db.String, nullable=True)
    expect_failure = db.Column(db.String, nullable=True)
    load_via_testinit = db.Column(db.String, nullable=True)
    replication = db.Column(db.String, nullable=True)
    job_url = db.Column(db.String, nullable=True)
    executable = db.Column(db.Boolean, default=False)
    duration_in_min = db.Column(db.Integer, nullable=True)
    io_destructive = db.Column(db.Boolean, nullable=False, default=False)
    is_ha = db.Column(db.Boolean, nullable=False, default=False)
    is_dev = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            'tc_pid': self.tc_pid,
            'tc_name': self.tc_name,
            'xpool_labels': self.xpool_labels,
            'test_init_params': self.test_init_params,
            'test_case_params': self.test_case_params,
            'os_environ': self.os_environ,
            'username': self.username,
            'lease_params': self.lease_params,
            'special_installation': self.special_installation,
            'ndu': self.ndu,
            'add_appliance': self.add_appliance,
            'expect_failure': self.expect_failure,
            'load_via_testinit': self.load_via_testinit,
            'replication': self.replication,
            'job_url': self.job_url,
            'executable': self.executable,
            'duration_in_min': self.duration_in_min,
            'io_destructive': self.io_destructive,
            'is_ha': self.is_ha,
            'is_dev': self.is_dev
        }
