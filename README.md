# MathCheck AI — Stage 2.9.7.8

Рабочая сборка ЕГЭ №13 с единым пользовательским потоком **«одно фото → подтверждение условия и решения → проверка → отчёт»**.

## Основной пользовательский поток

1. Открыть `http://127.0.0.1:8000/`.
2. Указать только ID ученика.
3. Загрузить одно PNG/JPG/WEBP, где видны условие и решение.
4. Vision за один проход извлекает отдельно:
   - формулировку задания, уравнение и пункт б / интервал;
   - решение ученика.
5. На странице рядом со сканом появляются два редактируемых поля: **«Условие задания»** и **«Решение ученика»**.
6. Пользователь исправляет любой OCR и подтверждает оба поля одной кнопкой.
7. Только после подтверждения `confirmed_task_statement` идёт в Solver/reference verifier, а `confirmed_transcript` — в source-locked student grading.
8. На странице показываются балл, комментарии, шаги, правильный ответ и эталонная окружность.
9. Внизу остаются OCR JSON и финальный JSON с кнопками копирования для диагностики.

## Важные инварианты

- Отдельно вводить условие до сканирования не нужно.
- Условие и решение извлекаются **одним Vision-вызовом из одного изображения**.
- Vision-результат всегда является черновиком и никогда не идёт прямо в оценивание.
- Если условие не попало в кадр, пользователь может вручную заполнить поле на шаге подтверждения — второй Vision-вызов не выполняется.
- После подтверждения источники истины: `confirmed_task_statement` и `confirmed_transcript`.
- Source-lock не позволяет Grader/Reviewer подменять решение ученика эталоном.
- Single-pass Grader/Reviewer, deterministic score и activity-aware Ollama transport сохранены.
- UI не использует внешние JS/CSS-библиотеки.

Swagger: `http://127.0.0.1:8000/docs`.

## Stage 2.9.7.8 — human-readable confirmation editor

Human confirmation no longer exposes raw OCR LaTeX such as `\\frac`, `\\sqrt`,
`\\pi`, or literal `\\n`. The browser receives additional presentation-only
fields `display_task_statement` and `display_transcript` and shows ordinary
Unicode mathematics (`π`, `√`, `≤`, `∈ ℤ`, real line breaks).

The raw OCR output is still preserved unchanged in the technical JSON at the
bottom of the page. The text edited by the human becomes the authoritative
`confirmed_task_statement` / `confirmed_transcript`; the existing tolerant
parsers accept this human-readable notation directly.
