# Local eval images (not stored in the project)

Real student/expert solution images are intentionally **not bundled** with the repository/project.

For local end-to-end checks, keep them in any folder outside the project and upload them through
`POST /api/reviews/photo`, or pass their path directly to the benchmark script.

Recommended local-only folder (gitignored if you choose to create it inside the project):

```text
local_eval_data/
  13.1.1_score2.png
  13.1.2_score1.png
  13.1.4_score0.png
  reference_circle_example.png
```

The machine-readable expected geometry remains in `evals/task_13/diagram_cases.json`, which contains
no student photo bytes.
