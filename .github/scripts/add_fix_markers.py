from pathlib import Path

FILES = [
    ".env.example",
    "evals/compare_models.py",
    "evals/prepare_ege13_images.py",
    "evals/run_ege13_benchmark.py",
    "evals/run_ege13_vision_benchmark.py",
    "evals/validate_ege13_release.py",
    "release_check.sh",
    "src/agents/diagram_verifier.py",
    "src/agents/diagram_vision.py",
    "src/agents/grader.py",
    "src/agents/persistence.py",
    "src/agents/reference_verifier.py",
    "src/agents/reviewer.py",
    "src/agents/solver.py",
    "src/agents/vision.py",
    "src/extra_api.py",
    "src/graph.py",
    "src/llm/__init__.py",
    "src/llm/config.py",
    "src/llm/ollama_client.py",
    "src/multi_photo_api.py",
    "src/observability/runtime.py",
    "src/pending_store.py",
    "src/progress_store.py",
    "src/run_app.py",
    "src/tools/__init__.py",
    "src/tools/core.py",
    "src/tools/display_math.py",
    "src/tools/ege13_diagram.py",
    "src/tools/ege13_fast_reference.py",
    "src/tools/ege13_reasoning.py",
    "src/tools/ege13_reference.py",
    "src/tools/ege13_report.py",
    "src/tools/ege13_report_v2.py",
    "src/tools/ege13_report_v3.py",
    "src/tools/ege13_rubric.py",
    "src/tools/ege13_student.py",
    "src/tools/ege13_task_input.py",
    "src/tools/ege13_user_report.py",
    "src/tools/ege13_user_report_exact.py",
    "src/tools/solution_steps.py",
    "tests/test_agents.py",
    "tests/test_diagram_cross_pass.py",
    "tests/test_ege13_diagram_verifier.py",
    "tests/test_real_grader.py",
    "tests/test_real_reviewer.py",
    "tests/test_solver_structured_output.py",
    "tests/test_stage2974_source_locked_grading.py",
    "tests/test_stage29_architecture.py",
    "update.sh",
]

for name in FILES:
    path = Path(name)
    text = path.read_text(encoding="utf-8")
    if text.rstrip().endswith("# fix"):
        continue
    path.write_text(text.rstrip() + "\n# fix\n", encoding="utf-8")

Path(".github/scripts/add_fix_markers.py").unlink()
Path(".github/workflows/add-fix-markers.yml").unlink()
