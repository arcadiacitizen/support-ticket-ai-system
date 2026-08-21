# Safe Support Ticket Automation

Минимальный PoC AI/ML-системы, которая классифицирует обращение, применяет risk-policy, ищет релевантное знание, выбирает автоответ или маршрут оператору и пишет audit event. Система нужна бизнесу, чтобы убрать повторную работу из потока 200k тикетов/день и удерживать 15-минутный SLA во время всплесков. Пользователь быстрее получает проверяемый ответ на безопасный FAQ, оператор — меньше ручной сортировки, а бизнес — экономию с контролем CSAT/reopen и стоимости. Денежные, security, legal и low-confidence решения остаются у человека.

## Быстрый запуск

Нужен Python 3.10+; внешние пакеты, сеть и API-ключи не требуются.

```bash
make demo
make smoke
```

`make demo` запускает три детерминированных сценария и добавляет решения в `artifacts/decisions.jsonl`. `make smoke` выполняет unit-тесты, end-to-end demo, проверяет три audit events и локальные ссылки документации.

Отдельный сценарий:

```bash
python3 -m support_ticket_ai.demo --scenario happy
python3 -m support_ticket_ai.demo --scenario risky
python3 -m support_ticket_ai.demo --scenario llm_down
```

Контейнер:

```bash
docker build -t support-ticket-poc .
docker run --rm support-ticket-poc
```

## Что демонстрируется

| Сценарий | Вход | Результат |
|---|---|---|
| Happy path | «Как изменить язык приложения?» | `general_faq`, KB hit, safe auto-reply, `auto_send=true` |
| Risky path | двойное списание + email/телефон | PII редактируется, `payment/high`, маршрут `payments_l2`, отправки нет |
| Fallback | safe FAQ, генератор недоступен | fail-closed: `generation_fallback_queue`, отправки нет |

Решение считается автоматическим только если тема находится в versioned allowlist, confidence/risk/retrieval gates пройдены и генератор доступен. Audit не содержит тело тикета: сохраняются fingerprint, причины, версии, latency и outcome.

## Реализация и дизайн

Реально работают: нормализация, regex PII-redaction, rules-классификатор, risk/low-confidence gate, лексический retrieval по маленькой KB, шаблонный генератор, fallback и JSONL audit. Это orchestration PoC, не доказательство ML-качества. В целевой архитектуре rules дополняются локальной intent-моделью и NER, JSON KB — hybrid/vector retrieval, шаблон — асинхронным RAG/LLM gateway, а JSONL — транзакционным decision store и append-only audit.

Допущения: русский язык и три demo-интента, 12% потока достижимы для safe auto-close, средний LLM-вызов стоит 0,80 ₽, один reopen снова требует 150 ₽ работы. PoC не имеет HTTP API, авторизации, брокера, настоящей модели/LLM, распределённых хранилищ и load test; production-границы явно описаны в документации.

## Карта репозитория

- [`support_ticket_ai/engine.py`](support_ticket_ai/engine.py) — pipeline и safety gates; [`examples/`](examples/) — mock tickets; [`tests/`](tests/) — четыре проверки.
- [`docs/product.md`](docs/product.md) — гипотезы, метрики, экономика и пилот.
- [`docs/architecture.md`](docs/architecture.md) — Mermaid-архитектура, потоки, stores и отказоустойчивость.
- [`docs/ml.md`](docs/ml.md) — baselines, данные/разметка, thresholds и валидация.
- [`docs/monitoring.md`](docs/monitoring.md) — technical/ML/product monitoring, алерты, drift и LLM cost.
- [`docs/risks-and-ops.md`](docs/risks-and-ops.md) — highload, privacy, safety и audit.
- [`AI_USAGE.md`](AI_USAGE.md), [`WORKLOG.md`](WORKLOG.md), [`SELF_REVIEW.md`](SELF_REVIEW.md) — прозрачность процесса и ограничения.
