#!/usr/bin/env bash
# One-command local observability demo. No fake grades and no data deletion.
set -Eeuo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

RUNS="${DEMO_RUNS:-30}"
HTTP_REQUESTS="${DEMO_HTTP_REQUESTS:-150}"
OPEN_BROWSER=1
WITH_ERROR=0
PHOTOS_DIR=""

usage() {
  cat <<'EOF'
MathCheckAi: запуск мониторинга и наполнение демонстрационными данными.
  bash demo.sh                          30 тестовых проверок + 150 HTTP-запросов
  bash demo.sh --with-error             то же, с одной намеренной тестовой ошибкой
  bash demo.sh --photos PATH            дополнительно: OCR фотографий из локальной папки
  bash demo.sh --runs 50 --http 200     другое количество данных
  bash demo.sh --no-open                не открывать браузер
Примечание: демо не увеличивает число настоящих завершённых проверок.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --with-error) WITH_ERROR=1; shift;;
    --photos)
      [[ $# -ge 2 ]] || { echo "Укажи папку после --photos" >&2; exit 2; }
      PHOTOS_DIR="$2"; shift 2;;
    --runs)
      [[ $# -ge 2 ]] || exit 2
      RUNS="$2"; shift 2;;
    --http)
      [[ $# -ge 2 ]] || exit 2
      HTTP_REQUESTS="$2"; shift 2;;
    --no-open) OPEN_BROWSER=0; shift;;
    --help|-h) usage; exit 0;;
    *) echo "Неизвестный параметр: $1" >&2; usage; exit 2;;
  esac
done

if [[ ! "$RUNS" =~ ^[0-9]+$ ]] || (( RUNS < 1 || RUNS > 200 )); then
  echo "Количество демо-проверок должно быть от 1 до 200" >&2
  exit 2
fi
if [[ ! "$HTTP_REQUESTS" =~ ^[0-9]+$ ]] || (( HTTP_REQUESTS < 1 || HTTP_REQUESTS > 1000 )); then
  echo "Количество HTTP-запросов должно быть от 1 до 1000" >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1; then
  echo "Docker не установлен: https://www.docker.com/products/docker-desktop/" >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker Engine не запущен."
  if [[ "$(uname -s)" == "Darwin" ]]; then
    echo "Открываю Docker Desktop..."
    open -a Docker || { echo "Не удалось открыть Docker Desktop" >&2; exit 1; }
  fi
  for i in {1..90}; do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 2
  done
  docker info >/dev/null 2>&1 || { echo "Docker Engine недоступен" >&2; exit 1; }
fi

echo "Поднимаю MathCheckAi, Prometheus, Grafana, Loki и Jaeger..."
docker compose up -d --build

echo "Проверяю доступность приложения и Prometheus..."
ready=0
for i in {1..90}; do
  if curl -fsS -o /dev/null http://127.0.0.1:8000/health \
     && curl -fsS -o /dev/null http://127.0.0.1:9090/-/ready; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" != "1" ]]; then
  echo "Контейнеры запущены, но приложение или Prometheus ещё не готовы." >&2
  docker compose ps
  exit 1
fi

echo "Генерирую $RUNS синтетических проверок и $HTTP_REQUESTS реальных HTTP-запросов..."
docker compose exec -T mathcheck python -m scripts.demo_http_load \
  --requests "$HTTP_REQUESTS" --interval 0.18 &
http_pid=$!

stage_args=(--runs "$RUNS" --delay 0.12)
if [[ "$WITH_ERROR" == "1" ]]; then
  stage_args+=(--with-error)
fi

if ! docker compose exec -T mathcheck python -m scripts.demo_observability "${stage_args[@]}"; then
  wait "$http_pid" || true
  echo "Не удалось сгенерировать демо-телеметрию" >&2
  exit 1
fi
wait "$http_pid"

if [[ -n "$PHOTOS_DIR" ]]; then
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Для OCR локальных фотографий нужен Python 3 на Mac" >&2
    exit 1
  fi
  echo "Дополнительно отправляю фотографии в локальный MathCheckAi..."
  python3 scripts/demo_photos.py --directory "$PHOTOS_DIR"
fi

echo "Обновляю данные Prometheus..."
for i in {1..18}; do
  if curl -fsSG --data-urlencode 'query=mathcheck_demo_reviews_total' \
      http://127.0.0.1:9090/api/v1/query | grep -q '"mode"'; then
    break
  fi
  sleep 2
done

if [[ "$OPEN_BROWSER" == "1" && "$(uname -s)" == "Darwin" ]]; then
  open "http://127.0.0.1:3000/d/mathcheck-overview/mathcheck-ai-observability" >/dev/null 2>&1 || true
  open "http://127.0.0.1:16686" >/dev/null 2>&1 || true
fi

echo ""
echo "Готово: $RUNS синтетических проверок; $HTTP_REQUESTS HTTP-запросов."
echo "Grafana:    http://localhost:3000"
echo "Prometheus: http://localhost:9090"
echo "Jaeger:     http://localhost:16686"
echo "Loki:       Grafana → Explore"
echo "Для новых измерений запусти эту же команду повторно."
