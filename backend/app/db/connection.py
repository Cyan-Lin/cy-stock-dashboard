import os

import psycopg2


def get_connection():
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url)
