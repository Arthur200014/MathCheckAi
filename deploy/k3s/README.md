# MathCheckAi / k3s

## План

- [x] Анализ проекта.
- [x] PostgreSQL для истории и прогресса.
- [x] Helm Chart: приложение, CNPG, хранилища, CronJob.
- [ ] Установка и запуск k3s.
- [ ] Проверка двух подов, репликации, бэкапа, восстановления и переключения primary.
- [ ] Проверка запроса к Ollama.

## Запуск

На отдельной Linux-машине с установленными Docker и Helm:

```sh
curl -sfL https://get.k3s.io | sh -
mkdir -p ~/.kube
sudo install -o "$(id -u)" -g "$(id -g)" -m 600 /etc/rancher/k3s/k3s.yaml ~/.kube/mathcheck-k3s.yaml
export KUBECONFIG="$HOME/.kube/mathcheck-k3s.yaml"
kubectl get nodes
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

Бэкап: логический pg_dump каждые шесть часов, отдельный PVC, хранение семь дней. Проверка восстановления в отдельную БД ещё не проведена. Файлы изображений и отчётов находятся на общем PVC и не входят в pg_dump. Для защиты от потери узла копии нужно выносить за пределы узла.

Один узел k3s: оба экземпляра приложения используют общий PVC ReadWriteOnce на этом узле. Это демонстрация отказа пода, а не отказа физической машины. SQLite остаётся вариантом локального запуска. Перенос старых данных не выполняется.

## GitHub Actions

Workflow `k3s` запускает отдельный кластер на Linux runner. Скрипт `MATHCHECK_DEMO=1 bash deploy/k3s/verify.sh` проверяет роли PostgreSQL, запись и чтение между подами, репликацию, создание и восстановление дампа в отдельную базу пересоздание пода приложения и автоматическое переключение primary на реплику. Скрипт удаляет поды приложения и primary PostgreSQL; запускать только в отдельном тестовом кластере. Для теста используются синтетические данные. Ollama в CI не запускается. Кластер runner удаляется по завершении задания; для постоянного доступа нужен отдельный сервер.
