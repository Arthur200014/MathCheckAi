# Проверка требований ТЗ

Этот файл показывает, где в проекте закрыт каждый пункт основного задания.

| Требование | Статус | Где смотреть |
|---|---|---|
| Сформировать ТЗ под агента | Готово | `docs/TZ.md` |
| Выбрать движок и обосновать | Готово | `docs/ENGINEERING_DECISIONS.md`, `docs/FINAL_REPORT.md` |
| Рассмотреть варианты изоляции | Готово | `docs/ENGINEERING_DECISIONS.md`, `docs/FINAL_REPORT.md` |
| Запуск в изолированной среде | Готово | `Dockerfile`, `docker-compose.yml` |
| Open source/local LLM | Готово | Ollama + локальные модели |
| Попробовать минимум 3 модели | Готово | `docs/EVAL_RESULTS_SUMMARY.md`, `docs/LLM_SELECTION.md` |
| Аргументировать выбор модели | Готово | `docs/LLM_SELECTION.md` |
| Выбрать agent framework | Готово | LangGraph, `docs/ENGINEERING_DECISIONS.md` |
| Мультиагентная архитектура | Готово | `src/graph.py` |
| Один общий flow | Готово | `src/graph.py` |
| C4 | Готово | `docs/C4.md` |
| Sequence Diagram | Готово | `docs/sequence.mmd` |
| System prompts | Готово | `prompts/` |
| Skills отдельными файлами | Готово | `skills/` |
| Семантические md файлы | Готово | `knowledge/SOUL.md`, `knowledge/EXPERT_RULES_13.md`, `knowledge/FORMATTING_RULES.md` |
| Tools | Готово | `src/tools/` |
| Краткосрочная память | Готово | `ReviewState`, `docs/MEMORY.md` |
| Долгосрочная память | Готово | SQLite, `src/tools/core.py`, `docs/MEMORY.md` |
| Рассмотреть advanced memory | Готово | `docs/MEMORY.md` |
| Объяснить, почему обычный RAG не оптимален | Готово | `docs/MEMORY.md` |
| Evals LLM | Готово | Vision benchmark + `evals/run_model_selection.py` |
| Evals agentic system | Готово | `evals/run_ege13_benchmark.py` |
| Метрики | Готово | `docs/EVAL_RESULTS_SUMMARY.md`, SQLite metrics, timings |
| Логи | Готово | `llm_calls.jsonl` |
| Трейсы | Готово | `traces.jsonl` |
| Алертинг | Готово | `alerts.jsonl`, slow LLM alert |
| Observability описание | Готово | `src/observability/README.md` |
| Unit tests | Готово | `tests/` |
| CI | Готово | `.github/workflows/tests.yml` |
| Human confirmation | Готово | Vision gate + post-confirmation graph |
| Сохранение истории | Готово | SQLite persistence |

## Что важно помнить на защите

В проекте есть старые файлы для экспериментов с чтением тригонометрической окружности. Они не входят в активный graph текущего MVP.

Активный runtime после Reference Verifier идёт сразу в Grader. Ученическая окружность не влияет на score.

`qwen3-vl:4b-instruct` выбрана не потому, что у неё идеальный OCR, а потому что в нашем сравнении она была самой стабильной по завершению запросов и structured output.

Classical RAG не используется как основная память, потому что основная история проекта структурирована и точный SQL для неё подходит лучше.
