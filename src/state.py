from typing import Any, TypedDict


class ReviewState(TypedDict, total=False):
    review_id: str
    student_id: str
    task_type: str
    task_statement: str
    detected_task_statement: str
    original_task_statement: str
    confirmed_task_statement: str
    task_statement_confidence: float
    task_uncertain_fragments: list[str]
    task_statement_confirmation_source: str

    task_profile_ok: bool
    task_title: str
    task_max_score: int
    task_profile: dict[str, Any]

    image_b64: str
    image_filename: str
    image_width: int
    image_height: int
    image_format: str
    image_original_bytes: int
    image_preprocessing: str

    transcript: str
    original_transcript: str
    confirmed_transcript: str
    transcript_steps: list[str]
    transcript_confidence: float
    uncertain_fragments: list[str]
    needs_confirmation: bool
    transcript_confirmed: bool
    human_confirmation_required: bool
    human_confirmation_completed: bool
    transcript_confirmation_source: str
    vision_model: str
    vision_elapsed_seconds: float
    vision_ollama_total_seconds: float | None
    vision_ollama_load_seconds: float | None
    vision_ollama_prompt_eval_seconds: float | None
    vision_ollama_generation_seconds: float | None
    vision_ollama_prompt_tokens: int | None
    vision_ollama_output_tokens: int | None
    vision_ollama_prompt_tokens_per_second: float | None
    vision_ollama_generation_tokens_per_second: float | None
    vision_ollama_done_reason: str | None
    vision_num_ctx: int | None
    vision_num_predict_custom_cap: bool

    diagram_analysis_ok: bool
    diagram_model: str
    diagram_present: bool
    diagram_type: str
    diagram_method_used: bool
    diagram_confidence: float
    diagram_center_visible: bool
    diagram_axes_visible: bool
    diagram_points: list[dict[str, Any]]
    diagram_claims: list[dict[str, Any]]
    diagram_arc_marked: bool
    diagram_arc_description: str
    diagram_uncertain_fragments: list[str]
    diagram_notes: list[str]
    diagram_visual_quality: str
    diagram_bbox: dict[str, Any]
    diagram_arc_confidence: float
    diagram_initial_verification_status: str
    diagram_initial_evidence_signatures: list[str]
    diagram_reinspection_needed: bool
    diagram_reinspection_used: bool

    diagram_recheck_analysis_ok: bool
    diagram_recheck_model: str
    diagram_recheck_present: bool
    diagram_recheck_type: str
    diagram_recheck_method_used: bool
    diagram_recheck_confidence: float
    diagram_recheck_visual_quality: str
    diagram_recheck_bbox: dict[str, Any]
    diagram_recheck_center_visible: bool
    diagram_recheck_axes_visible: bool
    diagram_recheck_points: list[dict[str, Any]]
    diagram_recheck_claims: list[dict[str, Any]]
    diagram_recheck_arc_marked: bool
    diagram_recheck_arc_confidence: float
    diagram_recheck_arc_description: str
    diagram_recheck_uncertain_fragments: list[str]
    diagram_recheck_notes: list[str]
    diagram_verification_status: str
    diagram_part_b_valid: bool | None
    diagram_verification_results: list[str]
    diagram_verification_issues: list[str]
    diagram_checked_correspondences: int
    diagram_cross_pass_confirmed: bool
    diagram_cross_pass_signatures: list[str]
    diagram_manual_review_scope: str
    diagram_manual_review_reasons: list[str]
    diagram_unverified_reasons: list[str]
    diagram_reinspection_resolved: bool

    solver_ok: bool
    solver_model: str
    solver_elapsed_seconds: float
    solver_confidence: float
    reference_solution: str
    reference_steps: list[str]
    reference_answer: str
    reference_answer_raw: str
    reference_answer_part_a: str
    key_checkpoints: list[str]
    solver_notes: str
    solver_error: str
    solver_machine_spec: dict[str, Any]

    reference_verification_ok: bool
    reference_verification_status: str
    reference_verification_results: list[str]
    reference_verification_errors: list[str]
    reference_expected_roots: list[str]
    reference_solver_selected_roots: list[str]
    reference_answer_part_b_verified: str
    reference_answer_part_a_verified: str
    reference_equation_source: str
    reference_verified_families: list[dict[str, str]]
    solver_fallback_used: bool

    criteria: str
    verification_results: list[str]
    grader_mode: str
    grader_context_preview: dict[str, Any]
    grader_ok: bool
    grader_model: str
    grader_elapsed_seconds: float
    grader_retry_used: bool
    grader_error_code: str
    grader_output_chars: int
    grader_raw_output_length: int
    grader_output_tokens: int | None
    grader_done_reason: str | None
    grader_raw_output_preview: str
    grader_score_source: str
    grader_confidence: float
    grader_manual_review_required: bool
    grader_review_advisory_only: bool
    grader_review_advisories: list[str]
    grader_student_evidence_source: str
    grader_student_evidence: dict[str, Any]
    grader_invariant_overrides: list[str]
    grader_error: str
    grader_part_a_status: str
    grader_part_b_status: str
    grader_error_class: str
    grader_overall_sequence_correct_both_parts: bool
    grader_evidence: list[str]
    grader_feedback: str
    grader_proposed_score_llm: int
    grader_student_machine_spec: dict[str, Any]
    grader_llm_selected_roots_before_answer_lock: list[str]
    grader_student_answer_lock_applied: bool
    grader_student_final_answer_part_b: list[str]
    grader_student_final_answer_source_text: str
    grader_student_answer_extraction_errors: list[str]
    grader_student_math_results: list[str]
    grader_student_math_errors: list[str]
    grader_part_a_equivalent: bool | None
    grader_part_b_roots_match: bool | None
    grader_student_selected_roots: list[str]
    grader_rubric_reason: str
    grader_diagram_override_applied: bool
    grader_diagram_unverified_ignored_for_score: bool
    grader_conflicts: list[str]
    student_steps: list[dict[str, str]]
    grader_step_assessments: list[dict[str, str]]
    criteria_source: str
    criteria_rubric: str
    criteria_loaded: bool

    reviewer_ok: bool

    reviewer_retry_used: bool
    reviewer_error_code: str
    reviewer_output_chars: int
    reviewer_raw_output_length: int
    reviewer_output_tokens: int | None
    reviewer_done_reason: str | None
    reviewer_raw_output_preview: str
    reviewer_score_source: str

    history_saved: bool
    history_db_path: str
    report_json_path: str
    student_history: list[dict[str, Any]]
    reviewer_model: str
    reviewer_elapsed_seconds: float
    reviewer_confidence: float
    reviewer_manual_review_required: bool
    reviewer_review_advisory_only: bool
    reviewer_error: str
    reviewer_part_a_status: str
    reviewer_part_b_status: str
    reviewer_error_class: str
    reviewer_evidence: list[str]
    reviewer_assessment: str
    reviewer_proposed_score_llm: int
    reviewer_student_machine_spec: dict[str, Any]
    reviewer_llm_selected_roots_before_answer_lock: list[str]
    reviewer_student_answer_lock_applied: bool
    reviewer_student_final_answer_part_b: list[str]
    reviewer_student_final_answer_source_text: str
    reviewer_student_answer_extraction_errors: list[str]
    reviewer_student_math_results: list[str]
    reviewer_student_math_errors: list[str]
    reviewer_part_a_equivalent: bool | None
    reviewer_part_b_roots_match: bool | None
    reviewer_independent_score: int | None
    reviewer_rubric_reason: str
    reviewer_conflicts: list[str]
    reviewer_overrides: list[str]
    reviewer_diagram_override_applied: bool
    reviewer_diagram_unverified_ignored_for_score: bool

    draft_score: int
    final_score: int
    max_score: int
    feedback: str
    status: str
    errors: list[str]
    warnings: list[str]
    manual_review_scope: str
    manual_review_reason: str
    manual_review_items: list[str]
    manual_review_auto_verified: dict[str, Any]
    report: dict[str, Any]
    report_circle_url: str
    trace_id: str
