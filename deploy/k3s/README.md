# Kubernetes homework — MathCheckAi
Deadline: 25 November 2026. Target: k3s + Helm + CNPG primary/replica + backups + multiple app pods.

## Plan / handoff
- [x] Inspect main: FastAPI, Dockerfile port 8000, external Ollama, SQLite history, local pending files, in-memory progress.
- [x] Implement opt-in PostgreSQL history adapter and integration test (execution pending).
- [ ] Move pending images/state and progress to shared durable storage; handle report files across pods and accurate UI storage labels.
- [ ] Prepare Helm charts: CloudNativePG cluster (2 instances), app Deployment (2 replicas), Service, health checks, configuration and secrets.
- [ ] Configure backups (scheduled pg_dump to separate persistent storage and verify restore; native CNPG object storage backups if required by rubric).
- [ ] Install k3s and operator via Helm, build/import app image, deploy to isolated namespace.
- [ ] Verify both pods, primary/replica, cross-pod review state, backup/restore, failover, and real Ollama workflow.
- [ ] Document commands and real evidence; do not report unexecuted checks as passed.

## Decisions
Separate branch, no changes to main or existing Docker Compose. Single-node k3s is sufficient for the homework demo, not node-level HA. PostgreSQL is optional outside Kubernetes. Existing SQLite data is not migrated automatically; demo uses a fresh database. No credentials in Git.
Existing Dockerfile is reusable. Ollama runs separately and must be reachable from pods; full model execution requires model resources.
