# ML/LLM-дизайн

## Разложение задач

| Задача | Первый baseline | Целевой подход и происхождение модели | Почему так |
|---|---|---|---|
| PII и жёсткий риск | regex/DLP-словари, risk rules | Self-hosted NER (открытая multilingual encoder-модель, дообученная на внутренней разметке) + rules | Детерминированные запреты объяснимы; NER повышает recall вариантов PII |
| Intent и маршрут | word/char TF-IDF + logistic regression | Небольшой multilingual encoder, fine-tuned внутри на исторических очередях; ONNX/CPU | Работает в hot path без LLM, дешёв, воспроизводим и укладывается в 500 мс |
| Дубликаты инцидента | нормализованный hash + BM25/MinHash | Self-hosted multilingual sentence embeddings + online clustering | Семантически объединяет разные формулировки массового сбоя |
| Поиск знаний | BM25 по опубликованной KB | Hybrid BM25 + embeddings, metadata filters и при необходимости cross-encoder reranker | Возвращает проверяемый источник; версия KB входит в audit |
| Черновик и суммаризация | утверждённый шаблон / extractive summary | LLM с RAG через gateway; сравниваются внешний API и self-hosted open model | Нужна гибкость языка, но результат не является источником истины |
| Финальное risk-решение | policy/rules | Policy/rules + calibrated scores; **не LLM** | Refund, блокировка, доступ и безопасность требуют стабильных правил и human-in-the-loop |

LLM не принимает решение о переводе денег, блокировке аккаунта, личности пользователя, компенсации или приоритете критического риска. Он не вызывается на синхронном пути и не «вспоминает» факты без retrieval. Без подходящего KB-документа, при конфликте источников или таймауте ответ не отправляется.

## Данные и разметка

Стартовый датасет — 90 дней закрытых тикетов: редактированный текст, канал/язык, первоначальная и финальная очередь, переводы между очередями, решение, правки черновика, reopen-7d, CSAT и связь с инцидентом. Автоматические теги и финальная очередь дают weak labels, но выборка очищается от ботов, дублей, устаревшей taxonomy и утечек из подписей операторов.

Для gold set стратифицируем по intent, каналу, языку, редким risky-классам и инцидентам. Два support-SME независимо размечают intent, маршрут, риск, PII span, нужность ответа и релевантный KB id; disagreements решает senior SME/DPO. Цель — Cohen's kappa ≥ 0,8. Active learning еженедельно отдаёт на разметку low-confidence, OOD, model/rule disagreement и частые operator corrections. Доступ к сырому тексту — только в изолированном контуре; training export псевдонимизирован.

## Offline- и online-валидация

Разбиение делается по времени, а дубликаты одного пользователя/инцидента остаются в одном split, иначе оценка будет завышена. Последние 2 недели — untouched test; дополнительно считаются slices по каналу, языку, intent, длине, наличию PII и инцидентному/обычному режиму.

| Слой | Метрики и стартовый gate |
|---|---|
| Intent/route | macro-F1 ≥ 0,85; top-1 route accuracy ≥ 0,90; для auto-eligible precision ≥ 0,96; ECE ≤ 0,05 |
| Risk/PII | recall критического risk ≥ 0,99; PII span recall ≥ 0,98; отдельно число false-negative на gold set |
| Retrieval | Recall@5 ≥ 0,92; nDCG@5; answerable-ticket coverage; ручная релевантность top-1 ≥ 0,90 |
| Generation | grounded/citation-correct ≥ 0,98 на allowlist; policy violation = 0; полнота и tone по blind SME review |
| End-to-end | safe resolution без reopen-7d, operator acceptance/edit distance, transfer rate, latency и цена на решённый тикет |

Порог 0,96 — precision, а не общая accuracy: для автоответа важнее не охватить сомнительные тикеты. Перед production offline gates дополняются adversarial-набором: prompt injection, инструкции «игнорируй правила», смешанные языки, obfuscated PII, ложные цитаты, пустые и очень длинные тексты.

## Уверенность и выбор действия

Вероятности классификатора калибруются temperature scaling на свежем validation window. Тикет уходит оператору, если: confidence ниже intent-specific threshold; модель и hard rules расходятся; OOD score выше порога; найденный документ ниже retrieval threshold/просрочен; присутствует risky topic или sensitive PII; post-check не подтверждает цитату. Для auto-send одновременно должны пройти все gates, тема должна быть в versioned allowlist, а генерация — соответствовать утверждённой схеме ответа.

Shadow mode сначала измеряет thresholds без влияния на пользователя. Затем 2 недели suggest-режима собирают acceptance и edits; только safe intent с нижней границей 95% confidence interval выше product gate допускается к малому auto-close canary. Thresholds и taxonomy версионируются вместе с моделью; rollback — на предыдущую связку model + policy + KB snapshot.

## Связь с PoC

PoC намеренно использует rules и лексический scorer: это прозрачный baseline, а не заявка на готовое ML-качество. Файл [`support_ticket_ai/data/kb.json`](../support_ticket_ai/data/kb.json) заменяет versioned search index, `TemplateGenerator` — RAG/LLM, а ручные confidence формулы — калиброванную модель. Такое упрощение позволяет проверить orchestration, gates, fallback и audit без ложного впечатления, что три примера валидируют качество.

