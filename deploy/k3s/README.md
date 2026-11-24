# MathCheckAi / k3s

## План

- [x] Анализ проекта.
- [x] PostgreSQL для истории и прогресса.
- [x] Helm Chart: приложение, CNPG, хранилища, CronJob.
- [x] Установка k3s, CNPG, сборка образа и установка Helm Chart в CI.
- [x] Проверка двух подов, репликации, бэкапа, восстановления и переключения primary.
- [ ] Проверка запроса к Ollama в Kubernetes (не входит в CI).

## Запуск

На отдельной машине с Ubuntu 24.04, Docker и Helm, из корня репозитория:

```sh
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.34.3+k3s1 sh -s - server --disable traefik --disable servicelb
mkdir -p ~/.kube
sudo install -o "$(id -u)" -g "$(id -g)" -m 600 /etc/rancher/k3s/k3s.yaml ~/.kube/mathcheck-k3s.yaml
export KUBECONFIG="$HOME/.kube/mathcheck-k3s.yaml"
kubectl wait --for=condition=Ready nodes --all --timeout=180s
kubectl -n kube-system wait --for=create deployment/coredns --timeout=180s
kubectl -n kube-system rollout status deployment/coredns --timeout=180s
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm repo update
helm upgrade --install cnpg cnpg/cloudnative-pg --version 0.29.2 -n cnpg-system --create-namespace --wait --timeout 5m
kubectl wait --for=condition=Established crd/clusters.postgresql.cnpg.io --timeout=120s
docker build -t mathcheck-ai:k3s .
docker save mathcheck-ai:k3s | sudo k3s ctr images import -
helm lint deploy/k3s/chart
helm upgrade --install mathcheck deploy/k3s/chart -n mathcheck --create-namespace --set-string ollama.baseUrl=http://OLLAMA_HOST:11434
kubectl -n mathcheck wait --for=condition=Ready cluster/mathcheck-db --timeout=600s
kubectl -n mathcheck rollout status deployment/mathcheck-app --timeout=300s
kubectl -n mathcheck port-forward svc/mathcheck-app 8000:8000
```

Вместо OLLAMA_HOST указать доступный из кластера адрес Ollama. Не использовать 127.0.0.1 для внешнего Ollama. Для полной проверки нужны установленные модели. Открыть http://localhost:8000.

## Проверка

```sh
kubectl -n mathcheck get pods,pvc,svc,cluster,cronjob
kubectl -n mathcheck get pods -l cnpg.io/cluster=mathcheck-db -L role
helm list -n mathcheck
kubectl -n mathcheck create job --from=cronjob/mathcheck-backup mathcheck-backup-demo
kubectl -n mathcheck wait --for=condition=complete job/mathcheck-backup-demo --timeout=300s
kubectl -n mathcheck logs job/mathcheck-backup-demo
```

Бэкап: логический pg_dump каждые шесть часов, отдельный PVC, хранение семь дней. В CI проверено восстановление дампа в отдельную БД и наличие исходных записей. Файлы изображений и отчётов находятся на общем PVC и не входят в pg_dump. Для защиты от потери узла копии нужно выносить за пределы узла.

Один узел k3s: оба экземпляра приложения используют общий PVC ReadWriteOnce на этом узле. Это демонстрация отказа пода, а не отказа физической машины. SQLite остаётся вариантом локального запуска. Перенос старых данных не выполняется.

## GitHub Actions

Workflow `k3s` запускает отдельный кластер на Linux runner. Скрипт `MATHCHECK_DEMO=1 bash deploy/k3s/verify.sh` проверяет роли PostgreSQL, запись и чтение между подами, репликацию, создание и восстановление дампа в отдельную базу, пересоздание пода приложения и автоматическое переключение primary на реплику. Скрипт удаляет поды приложения и primary PostgreSQL; запускать только в отдельном тестовом кластере. Для теста используются синтетические данные. Ollama в CI не запускается. Проверка DNS и Kubernetes API выполняется до установки CNPG. При сбое сохраняются состояние кластера, события и логи PostgreSQL и оператора. Кластер runner удаляется по завершении задания; для постоянного доступа нужен отдельный сервер.

CI использует Ubuntu 24.04 вместо ubuntu-latest (26.04). На 26.04 PostgreSQL не завершал CHECKPOINT из-за запрета сигналов между процессами. Перед установкой CNPG проверяется отправка сигналов непривилегированным процессом в контейнере. AppArmor не отключается. См. https://github.com/containerd/containerd/issues/14485.

## Результаты 24.11.2026

Проверенный коммит: `eb18fa70ed74f6b481f6c31045884ba2434927fa`.

| Проверка | Результат |
|---|---|
| k3s, DNS, Helm, CNPG | OK |
| Два пода приложения, две БД | Ready 2/2 для каждого компонента |
| Запись и чтение из разных подов | Cross-pod history, progress and files: OK |
| Репликация PostgreSQL | Replication: OK |
| Дамп и восстановление | Backup and restore: OK |
| Пересоздание пода приложения | Application pod replacement: OK |
| Переключение primary | Primary failover: OK |
| Тесты Python | 222 passed, 1 skipped, 2 warnings |

До отказа: mathcheck-db-1 — primary, mathcheck-db-2 — replica. После отказа: mathcheck-db-2 — primary, mathcheck-db-1 — replica. Обе БД Ready, данные сохранены, запись после переключения прошла.

- [k3s: успешный запуск и логи](https://github.com/Arthur200014/MathCheckAi/actions/runs/45434731370)
- [Тесты приложения](https://github.com/Arthur200014/MathCheckAi/actions/runs/45434754402)

В запуске k3s доступен артефакт `k3s-results` с выводом проверок.

## Демонстрация

1. `kubectl get nodes` — кластер k3s.
2. `helm list -A` — релизы CNPG и MathCheckAi.
3. `kubectl -n mathcheck get deployment,cluster,pods,cronjob,pvc` — два экземпляра приложения, primary и replica, расписание бэкапов, диски.
4. `kubectl -n mathcheck get pods -l cnpg.io/cluster=mathcheck-db -L role` — роли БД.
5. `MATHCHECK_DEMO=1 bash deploy/k3s/verify.sh` — репликация, дамп, восстановление, пересоздание пода и failover (только чистый тестовый кластер).
6. `kubectl -n mathcheck port-forward svc/mathcheck-app 8000:8000` — доступ к интерфейсу и `/ready` с локальной машины. Для проверки решений требуется работающий Ollama.

На GitHub Actions кластер временный. Для показа работающего интерфейса после завершения CI требуется запустить кластер на своей машине или сервере.
