from src.tools.ege13_diagram import verify_ege13_diagram
from src.tools.ege13_rubric import apply_ege13_rubric

EXPECTED = ["-11*pi/4", "-9*pi/4", "-3*pi/2"]


def test_case_a_correct_circle_passes():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "x1", "position": "lower_left", "value_label": "", "role": "selected_root"},
            {"point_id": "x2", "position": "lower_right", "value_label": "", "role": "selected_root"},
            {"point_id": "x3", "position": "top", "value_label": "", "role": "selected_root"},
        ],
        claims=[
            {"point_id": "x1", "value_text": "-11*pi/4"},
            {"point_id": "x2", "value_text": "-9*pi/4"},
            {"point_id": "x3", "value_text": "-3*pi/2"},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
    )
    assert result.status == "DIAGRAM_VERIFIED"
    assert result.part_b_valid is True
    assert result.checked_correspondences == 3
    assert result.issues == []


def test_case_b_swapped_point_labels_is_diagram_error_even_if_root_set_matches():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "(1)", "position": "lower_left", "value_label": "", "role": "selected_root"},
            {"point_id": "(2)", "position": "lower_right", "value_label": "", "role": "selected_root"},
            {"point_id": "(3)", "position": "top", "value_label": "-3*pi/2", "role": "selected_root"},
        ],
        claims=[
            {"point_id": "(1)", "value_text": "-9*pi/4"},
            {"point_id": "(2)", "value_text": "-11*pi/4"},
            {"point_id": "(3)", "value_text": "-3*pi/2"},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
    )
    assert result.status == "DIAGRAM_INVALID"
    assert result.part_b_valid is False
    assert any("diagram_point_value_mismatch:id=1" in x for x in result.issues)
    assert any("diagram_point_value_mismatch:id=2" in x for x in result.issues)
                                                                                     
    assert "diagram_claimed_root_set_matches_reference:true" in result.results


def test_direct_labels_on_reference_style_circle_are_checked_by_geometry():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.98,
        points=[
            {"point_id": "", "position": "left", "value_label": "3*pi", "role": "interval_boundary"},
            {"point_id": "", "position": "top", "value_label": "9*pi/2", "role": "interval_boundary"},
            {"point_id": "", "position": "upper_right", "value_label": "13*pi/3", "role": "selected_root"},
            {"point_id": "", "position": "lower_left", "value_label": "13*pi/4", "role": "selected_root"},
            {"point_id": "", "position": "lower_right", "value_label": "15*pi/4", "role": "selected_root"},
        ],
        claims=[],
        uncertain_fragments=[],
        expected_roots=[],
    )
    assert result.status == "DIAGRAM_VERIFIED"
    assert result.part_b_valid is True
    assert result.checked_correspondences == 5


def test_low_confidence_diagram_fails_closed():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.5,
        points=[],
        claims=[],
        uncertain_fragments=["point labels unreadable"],
        expected_roots=EXPECTED,
    )
    assert result.part_b_valid is None
    assert result.status == "DIAGRAM_LOW_CONFIDENCE"


def test_rubric_scores_one_for_correct_a_and_invalid_diagram_even_if_roots_match():
    llm = {
        "can_grade": True,
        "part_a_status": "correct",
        "part_b_status": "correct",                                            
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": False,
        "confidence": 0.98,
    }
    score, reason, conflicts = apply_ege13_rubric(
        assessment=llm,
        part_a_equivalent=True,
        part_b_matches=True,
        diagram_part_b_valid=False,
        diagram_method_used=True,
    )
    assert score == 1
    assert reason == "part_a_correct_part_b_diagram_error"
    assert conflicts == []


def test_rubric_unreadable_circle_does_not_block_when_math_is_confirmed():
    llm = {
        "can_grade": True,
        "part_a_status": "correct",
        "part_b_status": "correct",
        "overall_sequence_correct_both_parts": True,
        "error_class": "none",
        "manual_review_required": True,                                       
        "confidence": 0.98,
    }
    score, reason, conflicts = apply_ege13_rubric(
        assessment=llm,
        part_a_equivalent=True,
        part_b_matches=True,
        diagram_part_b_valid=None,
        diagram_method_used=True,
    )
    assert score == 2
    assert reason == "both_parts_correct_unreadable_diagram_no_proven_error"
    assert conflicts == []


def test_rubric_unreadable_circle_still_manual_when_math_itself_is_ambiguous():
    llm = {
        "can_grade": True,
        "part_a_status": "correct",
        "part_b_status": "uncertain",
        "overall_sequence_correct_both_parts": False,
        "error_class": "none",
        "manual_review_required": True,
        "confidence": 0.98,
    }
    score, reason, _ = apply_ege13_rubric(
        assessment=llm,
        part_a_equivalent=True,
        part_b_matches=None,
        diagram_part_b_valid=None,
        diagram_method_used=True,
    )
    assert score is None
    assert reason in {"llm_requested_manual_review", "ambiguous_assessment"}


def test_point_ids_are_not_parsed_as_angle_labels_and_claim_equalities_use_final_value():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "x1", "position": "lower_left", "value_label": "x1", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x2", "position": "lower_right", "value_label": "x2", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x3", "position": "top", "value_label": "x3", "role": "selected_root", "confidence": 0.95},
        ],
        claims=[
            {"point_id": "x1", "value_text": "-3*pi + pi/4 = -11*pi/4", "confidence": 0.95},
            {"point_id": "x2", "value_text": "-2*pi - pi/4 = -9*pi/4", "confidence": 0.95},
            {"point_id": "x3", "value_text": "-3*pi/2", "confidence": 0.95},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
    )
    assert result.status == "DIAGRAM_VERIFIED"
    assert result.part_b_valid is True
    assert not any("value_label" in x and "parse" in x for x in result.issues)
    assert "diagram_claimed_root_set_matches_reference:true" in result.results


def test_one_high_confidence_geometry_conflict_does_not_auto_penalize_student():
                                                                              
                                                                               
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "x1", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x2", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x3", "position": "upper_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        claims=[
            {"point_id": "x1", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "x2", "value_text": "-9*pi/4", "confidence": 0.95},
            {"point_id": "x3", "value_text": "-3*pi/2", "confidence": 0.95},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
    )
    assert result.status == "DIAGRAM_UNVERIFIED"
    assert result.part_b_valid is None
    assert any("diagram_single_or_nonredundant_mismatch_count:1" == x for x in result.results)


def test_two_independent_high_confidence_mismatches_are_enough_for_invalid():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "(1)", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "(2)", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "(3)", "position": "top", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        claims=[
            {"point_id": "(1)", "value_text": "-9*pi/4", "confidence": 0.95},
            {"point_id": "(2)", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "(3)", "value_text": "-3*pi/2", "confidence": 0.95},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
    )
    assert result.status == "DIAGRAM_INVALID"
    assert result.part_b_valid is False
    assert "diagram_redundant_mismatch_count:2" in result.results


def test_incomplete_claim_extraction_goes_to_unverified_not_invalid():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "x1", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x2", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        claims=[
            {"point_id": "x1", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "x2", "value_text": "-9*pi/4", "confidence": 0.95},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
    )
    assert result.status == "DIAGRAM_UNVERIFIED"
    assert result.part_b_valid is None
    assert any(x.startswith("diagram_claimed_root_set_not_safely_comparable:") for x in result.issues)


def test_missing_arc_can_be_candidate_invalid_but_requires_upstream_cross_pass_confirmation():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.95,
        points=[
            {"point_id": "L", "position": "left", "value_label": "-3*pi", "role": "interval_boundary", "confidence": 0.95},
            {"point_id": "T", "position": "top", "value_label": "-3*pi/2", "role": "interval_boundary", "confidence": 0.95},
            {"point_id": "x1", "position": "lower_left", "value_label": "", "role": "selected_root", "confidence": 0.95},
            {"point_id": "x2", "position": "lower_right", "value_label": "", "role": "selected_root", "confidence": 0.95},
        ],
        claims=[
            {"point_id": "x1", "value_text": "-11*pi/4", "confidence": 0.95},
            {"point_id": "x2", "value_text": "-9*pi/4", "confidence": 0.95},
        ],
        uncertain_fragments=[],
        expected_roots=EXPECTED,
        arc_marked=False,
        arc_confidence=0.96,
    )
    assert result.status == "DIAGRAM_INVALID"
    assert "diagram_required_arc_missing" in result.issues


def test_unreadable_single_point_stays_unverified_not_student_error():
    result = verify_ege13_diagram(
        diagram_present=True,
        diagram_type="trig_circle",
        method_used=True,
        confidence=0.91,
        points=[
            {"point_id": "x1", "position": "unknown", "value_label": "", "role": "selected_root", "confidence": 0.55},
        ],
        claims=[{"point_id": "x1", "value_text": "-11*pi/4", "confidence": 0.92}],
        uncertain_fragments=["point x1 almost on an axis; position unreadable"],
        expected_roots=EXPECTED,
        arc_marked=True,
        arc_confidence=0.9,
    )
    assert result.status == "DIAGRAM_UNVERIFIED"
    assert result.part_b_valid is None
# fix
