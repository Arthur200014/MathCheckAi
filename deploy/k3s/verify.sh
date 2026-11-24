#!/usr/bin/env bash
set -euo pipefail

ns=mathcheck
k() { kubectl -n "$ns" "$@"; }

k wait --for=condition=Ready cluster/mathcheck-db --timeout=600s
k rollout status deployment/mathcheck-app --timeout=300s
k get pods,pvc,svc,cluster,cronjob -o wide
helm list -n "$ns"
helm list -n cnpg-system

mapfile -t pods < <(k get pods -l app.kubernetes.io/name=mathcheck -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
test "${#pods[@]}" -eq 2
primary=$(k get cluster mathcheck-db -o jsonpath='{.status.currentPrimary}')
mapfile -t dbpods < <(k get pods -l cnpg.io/cluster=mathcheck-db -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')
test "${#dbpods[@]}" -eq 2
replica=""
for p in "${dbpods[@]}"; do
  if [[ "$p" != "$primary" ]]; then replica="$p"; fi
done
test -n "$replica"

sql() { k exec "$1" -c postgres -- psql -X -U postgres -d "$2" -At -v ON_ERROR_STOP=1 -c "$3"; }
test "$(sql "$primary" app 'SELECT pg_is_in_recovery()')" = f
test "$(sql "$replica" app 'SELECT pg_is_in_recovery()')" = t
echo "Primary: $primary; replica: $replica"

rid="r-k3s-$(date +%s)"
k exec "${pods[0]}" -- python -c '
import sys
from src.tools.core import save_review, save_report
from src.progress_store import reset_progress, start_stage
from src.pending_store import save_pending_image
rid = sys.argv[1]
save_review(dict(review_id=rid, student_id="k3s-test", task_type="ege_13", final_score=2, max_score=2, status="REVIEWED"))
save_report(rid, {"test": True})
reset_progress(rid)
start_stage(rid, "solver")
save_pending_image(rid, b"k3s-test")
' "$rid"

k exec "${pods[1]}" -- python -c '
import json, sys, urllib.request
from src.pending_store import load_pending_image_b64
from src.tools.core import REPORTS_DIR
rid = sys.argv[1]
def get(path):
    with urllib.request.urlopen("http://127.0.0.1:8000" + path, timeout=10) as response:
        return json.load(response)
assert get("/health")["storage_backend"] == "postgresql"
assert get("/api/reviews/" + rid)["final_score"] == 2
assert get("/api/reviews/" + rid + "/progress")["current_stage"] == "solver"
assert load_pending_image_b64(rid) == "azNzLXRlc3Q="
assert json.loads((REPORTS_DIR / (rid + ".json")).read_text())["test"]
print("Cross-pod history, progress and files: OK")
' "$rid"

for i in $(seq 1 30); do
  if [[ "$(sql "$replica" app "SELECT count(*) FROM reviews WHERE review_id='$rid'")" == 1 ]]; then break; fi
  sleep 2
done
test "$(sql "$replica" app "SELECT count(*) FROM reviews WHERE review_id='$rid'")" = 1
echo "Replication: OK"

job="backup-$(date +%s)"
k create job --from=cronjob/mathcheck-backup "$job"
k wait --for=condition=complete "job/$job" --timeout=300s
k logs "job/$job"

restore="restore-$(date +%s)"
restore_db="restore_$(date +%s)"
sql "$primary" postgres "CREATE DATABASE $restore_db OWNER app"
k get cronjob mathcheck-backup -o json | python -c '
import json, sys
obj = json.load(sys.stdin)
spec = obj["spec"]["jobTemplate"]["spec"]
c = spec["template"]["spec"]["containers"][0]
c["env"] = [e for e in c["env"] if e["name"] != "PGDATABASE"]
c["env"].append({"name": "PGDATABASE", "value": sys.argv[2]})
c["args"] = ["file=$(ls -t /backups/mathcheck-*.dump | head -n 1); test -s \"$file\"; pg_restore --exit-on-error --no-owner --no-acl --dbname=\"$PGDATABASE\" \"$file\"; echo Restore_OK"]
print(json.dumps({"apiVersion":"batch/v1","kind":"Job","metadata":{"name":sys.argv[1]},"spec":spec}))
' "$restore" "$restore_db" | k apply -f -
k wait --for=condition=complete "job/$restore" --timeout=300s
k logs "job/$restore"
test "$(sql "$primary" "$restore_db" "SELECT count(*) FROM reviews WHERE review_id='$rid' AND final_score=2")" = 1
test "$(sql "$primary" "$restore_db" "SELECT count(*) FROM review_progress WHERE review_id='$rid'")" = 1
echo "Backup and restore: OK"

k delete pod "${pods[0]}" --wait=true
k rollout status deployment/mathcheck-app --timeout=300s
k wait --for=condition=Ready pod -l app.kubernetes.io/name=mathcheck --timeout=300s
k exec deployment/mathcheck-app -- python -c '
import sys
from src.tools.core import load_review
assert load_review(sys.argv[1])["final_score"] == 2
print("Application pod replacement: OK")
' "$rid"
k get pods -o wide
