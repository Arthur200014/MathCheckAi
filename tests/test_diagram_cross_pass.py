from src.agents.diagram_verifier import diagram_final_verifier_node


def _base_state(first_status, first_signatures, recheck_points, recheck_claims, expected):
    return {
        "task_type": "ege_13",
        "confirmed_transcript": "б) с помощью окружности",
        "diagram_initial_verification_status": first_status,
        "diagram_initial_evidence_signatures": first_signatures,
        "diagram_verification_results": [],
        "diagram_verification_issues": [],
        "diagram_checked_correspondences": 0,
        "diagram_recheck_present": True,
        "diagram_recheck_type": "trig_circle",
        "diagram_recheck_method_used": True,
        "diagram_recheck_confidence": 0.95,
        "diagram_recheck_points": recheck_points,
        "diagram_recheck_claims": recheck_claims,
        "diagram_recheck_uncertain_fragments": [],
        "diagram_recheck_arc_marked": True,
        "diagram_recheck_arc_confidence": 0.95,
        "reference_expected_roots": expected,
    }


def test_second_pass_can_rescue_uncertain_first_pass_to_verified():
    state = _base_state(
        "DIAGRAM_UNVERIFIED",
        [],
        [
            {"point_id": "x1", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x2", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x3", "position": "top", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        [
            {"point_id": "x1", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "x2", "value_text": "-9*pi/4", "confidence": 0.95},
            {"point_id": "x3", "value_text": "-3*pi/2", "confidence": 0.95},
        ],
        ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
    )
    result = diagram_final_verifier_node(state)
    assert result["diagram_verification_status"] == "DIAGRAM_VERIFIED"
    assert result["diagram_part_b_valid"] is True


def test_invalid_requires_same_error_signature_on_reinspection():
    state = _base_state(
        "DIAGRAM_INVALID",
        ["point_value:-9π/4", "point_value:-11π/4"],
        [
            {"point_id": "1", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "2", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "3", "position": "top", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        [
            {"point_id": "1", "value_text": "-9*pi/4", "confidence": 0.95},
            {"point_id": "2", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "3", "value_text": "-3*pi/2", "confidence": 0.95},
        ],
        ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
    )
                                                                     
    state["diagram_initial_evidence_signatures"] = ["point_value:-9*pi/4", "point_value:-11*pi/4"]
    result = diagram_final_verifier_node(state)
    assert result["diagram_verification_status"] == "DIAGRAM_INVALID"
    assert result["diagram_part_b_valid"] is False
    assert result["diagram_cross_pass_confirmed"] is True


def test_conflicting_visual_passes_become_unverified_not_penalty():
    state = _base_state(
        "DIAGRAM_INVALID",
        ["point_value:-3*pi/2"],
        [
            {"point_id": "x1", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x2", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x3", "position": "top", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        [
            {"point_id": "x1", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "x2", "value_text": "-9*pi/4", "confidence": 0.95},
            {"point_id": "x3", "value_text": "-3*pi/2", "confidence": 0.95},
        ],
        ["-11*pi/4", "-9*pi/4", "-3*pi/2"],
    )
    result = diagram_final_verifier_node(state)
    assert result["diagram_verification_status"] == "DIAGRAM_UNVERIFIED_AFTER_REINSPECTION"
    assert result["diagram_part_b_valid"] is None
    assert result["diagram_manual_review_scope"] == ""
    assert result["diagram_reinspection_resolved"] is False
    assert "diagram_final_unverified_no_automatic_penalty" in result["diagram_verification_results"]
# fix
