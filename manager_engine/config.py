import os
POSTGRES_IP = '10.55.236.78'
USER = 'postgres'
POSTGRES_PASS = 'postgres'
PERF_DB_NAME = 'endurance'
class Config:
    SQLALCHEMY_DATABASE_URI = f'postgresql://{USER}:{POSTGRES_PASS}@{POSTGRES_IP}/qTest'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
