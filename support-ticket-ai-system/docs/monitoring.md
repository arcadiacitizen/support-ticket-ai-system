# Monitoring и обратная связь

## Что измеряется

| Слой | Метрики |
|---|---|
| Технический | tickets/s по каналу, error/timeout rate, availability; p50/p95/p99 каждого шага; event-bus lag и oldest-event age; queue depth; retry/DLQ; DB/outbox errors; доля fallback |
| Данные | пустой текст, размер/язык, PII rate, unknown/OOD rate, доли intent/channel, schema violations, freshness KB и пропуски признаков |
| ML/RAG | confidence/calibration, model-rule disagreement, route corrections, transfer rate, retrieval no-hit и Recall@5 на delayed labels, citation validity, operator accept/edit rate, policy-block rate |
| Продукт | safe resolution без оператора и reopen-7d (North Star), first-response/SLA breach, CSAT, reopen-7d, AHT, backlog и стоимость оператора |
| Safety | risky auto-send count, PII до/после redaction, prompt-injection flags, forbidden-action blocks, audit completeness, kill-switch state |

Каждое решение получает `decision_id`, ticket cohort, experiment arm, model/policy/KB versions и timestamps. Raw PII не попадает в метрики. Online label приходит из approve/edit/transfer/resolution, а зрелые outcome-labels — после окна reopen-7d и CSAT. Дашборд сравнивает treatment с постоянным 5% holdout, поэтому рост deflection не маскирует ухудшение качества.

## Стартовые алерты и реакция

| Условие | Окно / уровень | Автоматическая реакция |
|---|---|---|
| p95 hot path > 400 мс / > 500 мс | 5 минут, warning / critical | scale out; при critical отключить необязательные features, оставить rules + routing |
| Oldest safe-generation event > 5 мин / 12 мин | 5 минут | autoscale; около SLA — перевести в operator queue |
| LLM timeout/error > 5% или fallback > 10% | 10 минут | circuit breaker, один provider failover, затем human queue |
| Любой risky auto-send или PII leak detector hit | сразу, critical | kill switch auto-send, quarantine события, Security/DPO incident |
| Auto cohort reopen > control +0,5 п.п. или CSAT < control −0,05 | 7-дневное зрелое окно | остановить canary, сохранить suggest/shadow |
| OOD +5 п.п., PSI > 0,2 или intent JSD > 0,1 | 1 час и 1 день | проверить инцидент/channel; увеличить manual sampling |
| Audit completeness < 99,99% | 5 минут | запретить auto-send до восстановления журнала |

Алерты имеют runbook, owner и ссылку на последние deploy/model/KB changes. Во время массового инцидента динамический baseline сравнивает канал и intent, чтобы ожидаемый рост объёма не создавал тысячи одинаковых alerts.

## Drift или деградация модели

Сначала проверяются схема и upstream: доля пустых полей, версия adapter, язык и PII redaction. Затем параллельно сравниваются входной drift и delayed quality на одинаковых срезах:

| Input drift | Quality drop | Интерпретация / действие |
|---|---|---|
| Нет | Да | model/service regression, плохой deploy или устаревший KB; rollback и replay shadow |
| Да | Нет | поток изменился, но модель держит качество; наблюдать и расширить разметку |
| Да | Да | вероятный concept/domain drift; снизить auto coverage, разметить новый slice, переобучить |
| Нет | Нет, только общий KPI хуже | сменился mix или downstream-процесс; декомпозировать по intent/channel/operator queue |

Для проверки shadow-challenger ежедневно прогоняется на свежей случайной выборке, а 200–500 тикетов в неделю проходят слепой SME audit с oversampling risk/OOD. Нельзя объявлять drift причиной только по embeddings: решение опирается на change-point входа, slice-quality и ручную выборку.

## Стоимость LLM

Gateway пишет provider/model, input/output/cached tokens, retries, latency и расчётную стоимость на `decision_id`. Контролируются ₽/вызов, ₽/успешно решённый тикет, cache hit, tokens по intent и дневной burn-rate. Для расчёта MVP budget — 0,80 ₽ на auto-candidate, ожидаемо 19 200 ₽/день при 24 000 кандидатах; warning — 1,00 ₽/тикет или 25 000 ₽/день, hard cap — 30 000 ₽/день. После cap система использует утверждённый шаблон либо human queue, но не меняет провайдера вне privacy allowlist. Max tokens, один retry, semantic cache только для обезличенных common FAQ и per-tenant quotas ограничивают runaway cost.

## Проверка исходной бизнес-задачи

Еженедельный product review показывает не число ответов модели, а: долю тикетов, безопасно решённых без оператора и без reopen-7d; SLA/CSAT/reopen относительно holdout; сэкономленные минуты и рубли за вычетом inference/ops; backlog операторов и transfers. Рост North Star засчитывается только при прохождении guardrails. Если эффект исчезает после учёта повторных обращений или нагрузка просто переносится в другую очередь, система не решает исходную задачу и rollout останавливается.

