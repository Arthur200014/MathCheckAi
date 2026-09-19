# Evals для ЕГЭ №13

Здесь лежит воспроизводимый benchmark для сдачи проекта. Цель — не написать «мы пробовали три модели», а получить реальные цифры на одном и том же наборе экспертно размеченных работ.

## Набор

`task_13/benchmark_cases.json` содержит 12 сбалансированных кейсов:

- 4 работы на 2 балла;
- 4 работы на 1 балл;
- 4 работы на 0 баллов.

Экспертные баллы и комментарии взяты из `sources/ЕГЭ_13_критерии_решения_сканы.pdf`.

Для Vision нельзя отправлять всю страницу PDF: сверху напечатан официальный ответ, снизу — комментарий и балл эксперта. Поэтому `prepare_ege13_images.py` вырезает только рукописную часть. Crop-координаты зафиксированы в JSON, чтобы все модели получали одни и те же изображения.

## 1. Подготовить изображения

```bash
pip install -r requirements-eval.txt
python evals/prepare_ege13_images.py
```

Получится `local_eval_data/` с PNG. Папка gitignored и не попадает в репозиторий.

Перед benchmark быстро открой несколько PNG и проверь, что в crop не попали печатный официальный ответ и комментарий эксперта.

## 2. Быстрый пробный benchmark

Сначала не надо ждать весь набор:

```bash
python evals/run_ege13_benchmark.py --limit 1 --models qwen3-vl:4b-instruct
```

Потом можно проверить по одному кейсу на всех трёх моделях:

```bash
python evals/run_ege13_benchmark.py --limit 1
```

Модели по умолчанию берутся из `src/llm/config.py`:

- `qwen3-vl:4b-instruct`;
- `qwen2.5-vl:7b`;
- `granite3.2-vision:2b`.

Если модель ещё не установлена в Ollama, сначала скачай её через `ollama pull ...`.

## 3. Финальный benchmark

```bash
python evals/run_ege13_benchmark.py
```

Для каждой пары `модель × работа` benchmark:

1. отправляет только рукописный crop в Vision;
2. берёт распознанный текст как подтверждённое решение;
3. подставляет экспертно зафиксированные уравнение и интервал;
4. запускает Solver → reference verifier → Grader → Reviewer;
5. сравнивает итоговый балл 0/1/2 с баллом эксперта;
6. записывает latency каждого агента и manual-review.

Результаты сохраняются в `evals/results/` одновременно как JSON, CSV и Markdown.

## Метрики

Основные метрики для отчёта:

- `score_accuracy` — доля точных совпадений балла с экспертом;
- `mean_abs_score_error` — средняя абсолютная ошибка балла;
- `vision_success_rate`;
- `reference_success_rate`;
- `manual_review_rate`;
- latency Vision / Solver / Grader / Reviewer / end-to-end;
- `false_error_rate_on_expert_2` — консервативный proxy ложной ошибки: эксперт дал 2, а система дала меньше;
- `positive_score_rate_on_expert_0` — эксперт дал 0, а система дала положительный балл.

`mean_vision_similarity` считается только для кейсов, где вручную заполнено поле `manual_transcript`. Его можно добавлять постепенно после ручной сверки OCR.

## Что попадёт в отчёт

Из финального Markdown/CSV берём таблицу примерно такого вида:

| Model | Score accuracy | Mean abs error | Manual review | Avg total time |
|---|---:|---:|---:|---:|
| model A | ... | ... | ... | ... |
| model B | ... | ... | ... | ... |
| model C | ... | ... | ... | ... |

Выбор основной модели делаем после реального прогона, а не заранее.
