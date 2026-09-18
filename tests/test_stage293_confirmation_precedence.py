from unittest.mock import patch

from src.api import TranscriptConfirmationRequest, confirm_transcript


class _Graph:
    def __init__(self):
        self.seen = None
    def invoke(self, state):
        self.seen = state
        return dict(state)


def test_human_confirmation_overrides_pending_ocr():
    graph = _Graph()
    payload = TranscriptConfirmationRequest(
        review_id="r-test",
        student_id="s1",
        task_type="ege_13",
        task_statement="task",
        original_transcript="old",
        confirmed_transcript="corrected by human",
    )
    pending = {
        "transcript": "old",
        "confirmed_transcript": "",
        "transcript_confirmed": False,
        "needs_confirmation": True,
        "status": "NEEDS_TRANSCRIPT_CONFIRMATION",
    }
    with patch("src.api.load_pending_image_b64", return_value=None), \
         patch("src.api.load_pending_state", return_value=pending), \
         patch("src.api.post_confirmation_graph", graph), \
         patch("src.api.delete_pending", return_value=None):
        result = confirm_transcript(payload)
    assert graph.seen["transcript"] == "corrected by human"
    assert graph.seen["confirmed_transcript"] == "corrected by human"
    assert graph.seen["transcript_confirmed"] is True
    assert graph.seen["needs_confirmation"] is False
    assert result["status"] == "TRANSCRIPT_CONFIRMED"
