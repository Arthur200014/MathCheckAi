# MathCheck AI — OpenTelemetry observability stack

Это локальная учебная конфигурация: **FastAPI / OpenTelemetry Collector / Prometheus /
Grafana / Loki / Jaeger**. Данные отправляются по настоящему OTLP; локальные JSONL
из старого проекта продолжают записываться отдельно и не подменяют OTel-трейсы.

## 1. Подготовка на macOS

Установи Docker Desktop и запусти Docker Engine.

```bash
git pull origin main
docker compose config
docker compose up -d --build
docker compose ps
```

Ollama и модель `qwen3-vl:4b-instruct` остаются на Mac, **не в контейнере**;
MathCheck обращается к `host.docker.internal:11434`. Для полной реальной
проверки требуется запущенная Ollama и скачанная модель. Для тестовой телеметрии
она не нужна.

Если в старом `.env` осталось `MATHCHECK_OTEL_ENABLED=false`, измени на
`MATHCHECK_OTEL_ENABLED=true` либо убери этот параметр из `.env`.
Compose передаёт в контейнер `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`.

## 2. Интерфейсы

| Сервис | URL | Что смотреть |
| --- | --- | --- |
| MathCheckAi | http://localhost:8000 | Основной интерфейс |
| Grafana | http://localhost:3000 | Дашборд «MathCheck AI — Observability», Explore → Loki |
| Prometheus | http://localhost:9090 | Status → Targets и выполнение PromQL |
| Jaeger | http://localhost:16686 | Поиск traces по сервису `mathcheck-ai` |
| Loki | http://localhost:3100/ready | Проверка готовности |
| Collector (host OTLP) | localhost:4317 и localhost:4318 | gRPC и HTTP OTLP, не веб-интерфейс |

Grafana: пользователь `admin`, пароль `GRAFANA_ADMIN_PASSWORD` в локальном
`.env` (учебный пароль по умолчанию `mathcheck-local-demo` — **не использовать
при публикации сервиса в интернет**). Все опубликованные порты привязаны
к `127.0.0.1`.

## 3. Архитектура

```text
MathCheckAi (OTel Python SDK)
  └── OTLP gRPC:4317 → OpenTelemetry Collector
                          ├── metrics → :9464 → Prometheus → Grafana
                          ├── logs → OTLP HTTP → Loki → Grafana Explore
                          └── traces → OTLP gRPC → Jaeger UI
```

Измеряются HTTP-запросы, события и время этапов Vision, Solver,
Reference Verifier, Grader, Reviewer, Report, Persist, вложенные вызовы Ollama.

Важный нюанс: загрузка фото и подтверждение транскрипции происходят в
**разных HTTP-запросах**, поэтому их OTel trace IDs отличаются. Общий
`mathcheck.review_id` — атрибут для поиска связанных трассировок, а
**не** настоящий trace ID.

Изображения, исходный текст решения, промпты, ID учащихся и токены не
пишутся в новые кастомные OTel-события. Их нельзя помещать в metric labels.
Legacy JSONL сохраняется отдельно; перед публикацией его нужно проверить
на наличие конфиденциальных данных.

## 4. Что именно видно в метриках

| OpenTelemetry name | Prometheus metric | Смысл |
| --- | --- | --- |
| `mathcheck.http.requests` | `mathcheck_http_requests_total` | Запросы по route / status_class |
| `mathcheck.http.duration` | `mathcheck_http_duration_seconds_bucket` | Задержки HTTP |
| `mathcheck.stage.calls` | `mathcheck_stage_calls_total` | Выполненные этапы по статусу |
| `mathcheck.stage.duration` | `mathcheck_stage_duration_seconds_bucket` | Длительность этапов |
| `mathcheck.stage.errors` | `mathcheck_stage_errors_total` | Ошибки этапов |
| `mathcheck.reviews.completed` | `mathcheck_reviews_completed_total` | Успешно сохранённые реальные проверки |

Имена Prometheus формируются экспортёром Collector из OTel имён и единиц.
Проверь их фактическое написание через Prometheus после первого запуска.

## 5. Быстрая проверка даже без Ollama

Сначала сгенерируй несколько **настоящих HTTP-запросов**:

```bash
curl -fsS http://localhost:8000/health >/dev/null
curl -fsS http://localhost:8000/api/task-types >/dev/null
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/reviews/missing-demo
```

Затем отдельно создай **явно синтетическую** последовательность span,
логов и длительностей агентов. Здесь нейросеть не вызывается, а имена
этапов имеют префикс `demo_`; счётчик реальных сохранённых проверок не
увеличивается:

```bash
docker compose exec mathcheck python -m scripts.demo_observability
```

По умолчанию скрипт создаёт **только успешные этапы**. Если нужно специально
продемонстрировать обнаружение ошибки, запусти второй режим:

```bash
docker compose exec mathcheck python -m scripts.demo_observability --with-error
```

Только этот запуск добавляет `langgraph.demo_failure` со статусом ERROR
и метрику ошибки. Старые красные трассировки в Jaeger не исчезают сразу:
можно ограничить поиск последними минутами или найти новый `review_id`.
Реальные ошибки в обычной работе приложения продолжают регистрироваться
независимо от режима демо.

Через несколько секунд открой:

1. Prometheus → Status → Targets. Цель `mathcheck-otel` должна быть UP.
2. Grafana → Dashboards → MathCheck AI — Observability. Посмотри количество запросов и длительности этапов.
3. Grafana → Explore → Loki, запрос `{service_name="mathcheck-ai"}`. Можно искать `demo_` и `stage.finished`.
4. Jaeger → Service `mathcheck-ai` → Find Traces. Открой `demo.review` и вложенные `langgraph.demo_*`.
5. После обычного запуска в новом `demo.review` **не должно** быть `demo_failure`; после запуска с `--with-error` этот span будет красным, а в Loki появится событие об ошибке.

**Демонстрационные измерения не являются результатами реальной проверки.**
Для полной защиты повтори сценарий с фотографией, работающей Ollama,
подтверждением OCR и готовым отчётом.

## 6. Как читать обновлённый дашборд

- `HTTP traffic` показывает шаблоны известных путей (например, `/docs` и
  `/api/reviews/{review_id}`), а не реальные идентификаторы пользователей.
  Неизвестные запросы остаются под общей меткой `unmatched`.
- `LangGraph average duration` отображает среднюю длительность этапов
  сразу после первого тестового запуска — для него не требуется несколько
  точек во временном ряду.
- `LangGraph p95 latency` и `HTTP p95 latency` оцениваются по накопленным
  bucket гистограммам. При одном тестовом событии это только **грубая оценка
  по бакету**, а не статистически достоверный 95-й перцентиль.
- Для HTTP (миллисекунды) и агентов (секунды и минуты) настроены отдельные
  границы гистограмм. Предыдущий p95 около 5 секунд у быстрых HTTP-запросов
  был артефактом стандартного первого бакета 0–5 секунд.

Чтобы получить новые метрики на Mac после обновления `main`:

```bash
git pull origin main
docker compose up -d --build
curl -fsS http://localhost:8000/docs >/dev/null
docker compose exec mathcheck python -m scripts.demo_observability
```

В Grafana открой дашборд и выбери `Last 15 minutes`. Старые точки с
`unmatched` могут временно оставаться в выбранном интервале, пока
не выйдут из окна отображения.

## 6. Диагностика

```bash
docker compose ps
docker compose logs --tail=100 mathcheck otel-collector prometheus loki jaeger grafana
curl -fsS http://localhost:8000/health
curl -fsS http://localhost:9090/-/ready
curl -fsS http://localhost:3100/ready
```

Если нет метрик: проверь `MATHCHECK_OTEL_ENABLED`, доступность
`otel-collector:4317`, Collector logs и Target `otel-collector:9464`.
Если нет логов: проверь pipeline `logs` и Loki OTLP endpoint `/otlp`.
Если нет трейсов: проверь pipeline `traces` и service name в Jaeger.
Вкладка Grafana Explore покажет логи только после реальных запросов
или запуска синтетического сценария.

Остановить сервисы без удаления данных:

```bash
docker compose down
```

Не выполняй `docker compose down -v`, если нужно сохранить Prometheus,
Loki, Grafana и пользовательские данные.

## 7. Проверка CI

```bash
docker compose config --quiet
python -m pytest tests/test_otel_instrumentation.py tests/test_observability_stack.py -q
python -m pytest -q
```

CI выполняет два независимых сценария: `tests.yml` проверяет Compose,
конфигурации и тесты Python; `observability-smoke.yml` **поднимает весь Docker-стек
на GitHub runner**, создаёт синтетическую телеметрию и проверяет её наличие
в Prometheus, Loki и Jaeger. Реальную проверку математической работы
с локальной Ollama по-прежнему необходимо показать на машине с моделью.
