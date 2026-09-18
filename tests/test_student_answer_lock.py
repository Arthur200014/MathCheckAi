from src.tools.ege13_student import extract_ege13_explicit_final_answer


def test_extracts_explicit_case_b_part_b_without_reference():
    transcript = r"""Ответ: а) x=...; б) -\frac{3\pi}{4}, -\frac{11\pi}{4}, -\frac{9\pi}{4}"""
    out = extract_ege13_explicit_final_answer(transcript)
    assert out.final_answer_found is True
    assert set(out.final_part_b_roots) == {"-3*pi/4", "-11*pi/4", "-9*pi/4"}
    assert out.errors == []


def test_no_answer_marker_means_no_lock():
    out = extract_ege13_explicit_final_answer(r"б) x_1=-11\pi/4; x_2=-9\pi/4; x_3=-3\pi/2")
    assert out.final_answer_found is False
    assert out.final_part_b_roots == []
