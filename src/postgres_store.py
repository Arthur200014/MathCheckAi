from contextlib import contextmanager
import os
import threading

_SCHEMA_LOCK = threading.Lock()
_initialized = set()

def postgres_enabled():
    return bool(os.getenv("MATHCHECK_DATABASE_URL"))

class _Connection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=()):
        return self.connection.execute(sql.replace("?", "%s"), params)

@contextmanager
def postgres_connection():
    import psycopg
    from psycopg.rows import dict_row

    dsn = os.environ["MATHCHECK_DATABASE_URL"]
    with psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5) as conn:
        with _SCHEMA_LOCK:
            if dsn not in _initialized:
                with conn.transaction():
                    conn.execute("SELECT pg_advisory_xact_lock(20261124)")
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS reviews (
                            review_id TEXT PRIMARY KEY, student_id TEXT NOT NULL,
                            task_type TEXT NOT NULL, final_score INTEGER,
                            max_score INTEGER, status TEXT NOT NULL, error_class TEXT,
                            summary TEXT, created_at TEXT NOT NULL, payload_json TEXT NOT NULL
                        )
                    """)
                    conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_student ON reviews(student_id, created_at)")
                    conn.execute("CREATE TABLE IF NOT EXISTS review_progress (review_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL)")
                _initialized.add(dsn)
        yield _Connection(conn)
