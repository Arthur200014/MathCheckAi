# MathCheck AI — OpenTelemetry (этап 1)

Это первая часть подключения observability. Здесь включены **реальные OTel traces и metrics**,
а не только локальные JSONL-файлы. Локальные JSONL остаются для совместимости.

## Что инструментировано

- HTTP-запросы FastAPI (через `opentelemetry-instrumentation-fastapi`);
- этапы LangGraph: Vision, Solver, Verifier, Grader, Reviewer, Report, Persist;
- четырe custom metrics: `mathcheck.stage.calls`, `mathcheck.stage.duration`,
  `mathcheck.stage.errors`, `mathcheck.reviews.completed`;
- группировка этапов через безопасный атрибут `mathcheck.review_id`.

Загрузка фотографии и подтверждение решения — **два отдельных HTTP-запроса**.
Они будут иметь разные trace ID, но общий `mathcheck.review_id`, по которому их
можно найти. Нельзя трактовать JSONL review ID как настоящий 128-битный OTel trace ID.

## Включение

По умолчанию отключено: обычная разработка без Collector не меняется.

```bash
export MATHCHECK_OTEL_ENABLED=true
export OTEL_SERVICE_NAME=mathcheck-ai
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

Затем запустите обычный FastAPI/MathCheckAi. Endpoint должен указывать на работающий
OTLP/gRPC Collector. В Docker Compose используйте `http://otel-collector:4317`.
Данные не появятся в Prometheus/Grafana/Jaeger до настройки Collector и backends
(следующий этап).

Ни фотографии, ни текст решения, ни промпты, ни ID учащихся не добавляются
к кастомным OTel span attributes/metric labels. Не выставляйте Collector и UI
в открытый интернет без аутентификации и защиты доступа.

## Проверка на текущем этапе

```bash
python -m pytest tests/test_otel_instrumentation.py -q
```

Существующий `tests/test_ege13_diagram_routing.py` уже падал на `main`
до внедрения OpenTelemetry. Это отдельная проблема бизнес-логики.
