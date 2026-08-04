import os
from contextlib import contextmanager

import psycopg2


def get_connection():
    url = os.environ["DATABASE_URL"]
    return psycopg2.connect(url)


@contextmanager
def db_conn():
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
