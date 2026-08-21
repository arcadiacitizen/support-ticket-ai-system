# Risks & Operations

## Highload и надёжность

1. **Разделить пути.** PII, rules, локальная классификация и routing синхронны (`p95 ≤ 500 мс`); retrieval/LLM/проверка ответа идут через durable queue и не блокируют приём тикета.
2. **Пережить всплеск.** Пик 20k/10 минут — 33,3 тикета/с; ingress рассчитан на 200/с, очередь — на 120k событий. Autoscaling следует consumer lag, а incident dedup не запускает тысячи одинаковых генераций.
3. **Fail closed.** Timeout LLM, плохой retrieval, OOD или исчерпанный бюджет дают один retry и затем operator queue. Kill switch отключает auto-send независимо от маршрутизации; события идемпотентны, outbox исключает потерю.
4. **Защитить SLA.** Risky и приближающиеся к 15 минутам тикеты получают приоритет; при backlog черновики отключаются первыми, а тикет остаётся виден оператору с исходным временем SLA.

## Privacy, safety и risk

1. **PII до LLM.** Тексты шифруются и редактируются локально; номера карт, документы, credentials, health/legal data и прямые идентификаторы запрещено отправлять внешнему LLM. Provider допускается только после DPA, residency и zero-retention review.
2. **Human-in-the-loop.** Возвраты/платежи, account access, fraud/security, юридические и privacy-запросы, угрозы/вред, жалобы регулятору, low-confidence и конфликт источников нельзя закрывать автоматически.
3. **Prompt injection.** Текст пользователя считается недоверенными данными: не попадает в system instructions, retrieval фильтруется по опубликованной KB/ACL, tools отсутствуют либо allowlisted, output проходит schema/citation/policy checks и adversarial tests.
4. **Аудит и доступ.** Для решения сохраняются входной fingerprint, причины риска, confidence, KB/model/policy versions, tokens, результат и human override; сам текст хранится отдельно по RBAC/retention. Любая отправка воспроизводима, автоответ можно отключить одним kill switch.

