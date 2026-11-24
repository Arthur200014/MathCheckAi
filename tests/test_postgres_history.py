import os
from uuid import uuid4

import pytest
from src.tools import core

@pytest.mark.skipif(not os.getenv("MATHCHECK_TEST_DATABASE_URL"), reason="requires a disposable PostgreSQL database")
def test_postgres_history(monkeypatch):
    monkeypatch.setenv("MATHCHECK_DATABASE_URL", os.environ["MATHCHECK_TEST_DATABASE_URL"])
    rid = "r-" + uuid4().hex
    student = "k3s-" + uuid4().hex
    try:
        assert core.save_review({"review_id": rid, "student_id": student, "task_type": "ege_13",
                                 "final_score": 2, "max_score": 2, "status": "REVIEWED"}) == "postgresql:reviews"
        assert core.load_review(rid)["final_score"] == 2
        assert core.load_student_history(student)[0]["review_id"] == rid
        core.save_review({"review_id": rid, "student_id": student, "task_type": "ege_13",
                          "final_score": 1, "status": "REVIEWED"})
        assert core.load_review(rid)["final_score"] == 1
    finally:
        with core._connect() as conn:
            conn.execute("DELETE FROM reviews WHERE review_id=?", (rid,))
