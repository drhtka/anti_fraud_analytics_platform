# API

Планируемые endpoints:

- `/health` - проверка, что сервис работает;
- `/score` - скоринг транзакции;
- `/explain` - объяснение, какие признаки и правила повлияли на риск.

Сейчас уже доступны:

- `GET /health`
- `POST /score`
- `POST /explain`

`/explain` использует тот же payload, что и `/score`, но возвращает:

- `explanation_text` - короткое человекочитаемое объяснение;
- `explanation_points` - список ключевых причин;
- `active_signals` - какие risk signals сработали;
- `feature_values` - какие признаки реально ушли в модель.

На текущем этапе достаточно `Swagger/OpenAPI` и простого Python-клиента через `requests`.

Запуск клиента:

```bash
python -m api.score_client
```

Свой payload:

```bash
python -m api.score_client --payload-file my_score_payload.json
```

Готовые payload-файлы для контрастного прогона:

- `api/payloads/high_risk.json`
- `api/payloads/medium_ish.json`
- `api/payloads/low_risk.json`

{
"transaction_id": 1000002,
"transaction_amount": 50,
"product_cd": "W",
"card1": 13926,
"card4": "visa",
"card6": "debit",
"p_emaildomain": "yahoo.com",
"r_emaildomain": null
}

- Почему при feat_amount_gt_card1_avg_plus_3std = 0 модель все равно дала высокий риск?
- Чем отличается fraud_score от needs_manual_review ?
- Почему для бизнеса полезно видеть не только score, но и active_signals ?
- Что именно показывает threshold_used ?
