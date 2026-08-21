# Self-review

## Самая слабая часть

Качество ML не доказано: rules, пять KB-записей и три fixtures проверяют связность pipeline, но ничего не говорят о реальных macro-F1, calibration, long-tail, языках и prompt attacks. Также нет замера 500 мс под конкурентной нагрузкой; указанная латентность PoC — локальное время, а не production benchmark.

## Предположения

- 200k тикетов/день и 40% типовых стабильны по году; 30% типовых (12% всех) можно безопасно auto-close.
- Reopen означает один полный повторный цикл за 150 ₽; каналы, сезонность, налоги и стоимость change-management не моделируются.
- LLM стоит в среднем 0,80 ₽/кандидат, platform/команда — 60 млн ₽/год; это budget assumptions, не коммерческие предложения.
- Есть качественная versioned KB, согласие на нужную обработку и возможность связать ticket → reopen/CSAT без утечки PII.
- Support согласует taxonomy и выделит 20 операторов/SME для пилота; legal/DPO утвердят retention/provider policy.

## Нерешённые риски

Главные неизвестные — bias исторических route labels, редкие risk false-negative, качество PII-redaction на obfuscated/mixed-language тексте, устаревание KB и feedback loop от собственных auto-labels. Incident dedup может объединить похожие, но разные сбои. Внешний LLM несёт residency/vendor/availability risk; self-hosted — capacity и качество. Operator adoption и изменение поведения пользователей могут уменьшить расчётный эффект.

## Что сделать за два дополнительных дня

1. Обезличить и вручную разметить 500–1 000 реальных тикетов, добавить evaluation script с confusion matrix, risk recall, route accuracy, calibration и slice-report.
2. Заменить mock retrieval на BM25/embedding adapter с versioned KB, добавить adversarial PII/prompt-injection fixtures и mutation tests policy gates.
3. Поднять простой HTTP endpoint + очередь-заглушку, провести burst test 200 тикетов/с и проверить idempotency/replay/circuit breaker.
4. Провести tabletop с Support, Security/DPO и SRE; утвердить allowlist, retention, kill-switch owner, пилотный dashboard и rollback runbook.

## До production

Нужны HA stores/queue/outbox, IAM/secrets/encryption, DPA и data residency, threat model/red-team, data/model registry, CI security/scans, shadow backfill, online holdout, on-call/runbooks, disaster recovery и проверенный audit retention. Thresholds должны быть intent-specific и подтверждены на временном holdout и canary; KB требует owner/freshness SLA. Ни один auto-send не включается до end-to-end kill-switch drill.

## Что не автоматизировать полностью

Не отдавать модели без человека refunds/chargebacks и другие движения денег, восстановление/блокировку аккаунта, fraud/security, legal/privacy/regulator cases, угрозы и вред, исключения политики/компенсации, конфликтующие источники и любой OOD/low-confidence случай. LLM может суммаризировать или предложить текст, но полномочие действия остаётся у авторизованного оператора.

## Когда остановить проект

Пилот останавливается немедленно при одном подтверждённом risky auto-send или утечке PII. Rollout также прекращается, если зрелое 7-дневное окно показывает CSAT хуже holdout >0,05, reopen выше >0,5 п.п., SLA breach хуже >0,5 п.п., critical-risk recall <99% либо benefit после reopens/inference/ops неположителен. Для H1/H2 отдельный stop-сигнал — transfer/AHT улучшились менее чем на 10% и операторы принимают <40% черновиков после двух недель: в таком случае automation добавляет сложность, не решая исходную боль.

