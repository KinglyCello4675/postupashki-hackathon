# Поступашки: от рекламы в Telegram до ROMI

MVP системы измерения маркетинга для проекта «Поступашки».

## Проблема

Бизнес продаёт курсы через Telegram. Он видит покупки, но не видит путь пользователя к покупке: неизвестно, откуда пришёл покупатель; нет журнала рекламных размещений и их стоимости; нет связи между рекламным касанием и покупкой.

Главный вопрос: какие рекламные активности приносят деньги и куда направить следующий бюджет?

Исторический ROMI посчитать нельзя — не хватает данных. Поэтому мы строим систему, которая начнёт их собирать.

## Решение

Три части: реестр размещений (фиксируем каждую рекламу: канал, дата, стоимость, идентификатор); связка «реклама → покупка» через уникальный source; расчёт эффективности — Attributed Revenue, Cost и ROMI по размещениям.

Схема: реклама → placement_id → пользователь → покупка → выручка → атрибуция → ROMI → решение по бюджету.

## Структура репозитория

```
postupashki-hackathon/
├── README.md
├── data/
│   ├── base.xlsx
│   ├── history_analysis_beta.xlsx
│   ├── mock_purchases.csv
│   ├── post_labels_manual.csv
│   └── posts.csv
├── src/
│   ├── romi.py
│   ├── collect_posts.py
│   ├── generate_test_dataset.py
│   ├── placements.csv
│   ├── mock_touches.csv
│   └── notebooks/
│       ├── 01_sales_layer.ipynb
│       └── 02_attribution.ipynb
├── outputs/
│   ├── results_romi.md
│   ├── buyers_daily and median_price.png
│   ├── sales_daily.png
│   ├── subscribers_daily.png
│   ├── romi_by_channel.csv
│   └── romi_demo.csv
└── docs/
    ├── architecture.md
    ├── history.md
    ├── pdf_plan.md
    ├── spec.md
    └── tracking.md
```

> Файлы `src/placements.csv`, `src/mock_touches.csv`, `data/mock_purchases.csv`, `outputs/romi_demo.csv`, `outputs/romi_by_channel.csv` создаются скриптами. Они уже закоммичены для удобства просмотра — при необходимости воспроизводятся заново запуском команд ниже.

## Данные: что реальное, что синтетика

Реальные: `data/base.xlsx` (продажи от организаторов), `data/posts.csv` (собран из публичного канала через t.me/s/), `data/post_labels_manual.csv` (ручная проверка ИИ-разметки).

Синтетика: `src/placements.csv` (demo-реестр размещений), `src/mock_touches.csv` (demo-касания), `data/mock_purchases.csv` (demo-покупки).

Синтетические данные помечены явно. Они нужны только для демонстрации работы калькулятора.

## Запуск

```bash
pip install pandas openpyxl
python src/generate_test_dataset.py
python src/romi.py
jupyter notebook src/notebooks/01_sales_layer.ipynb
jupyter notebook src/notebooks/02_attribution.ipynb
```

Результаты сохраняются в `outputs/`: `romi_demo.csv` — ROMI по размещениям, `romi_by_channel.csv` — ROMI по каналам.

## Как работает ROMI-калькулятор

1. Читает `placements.csv` (реестр с cost), `mock_touches.csv` (касания), `base.xlsx` (продажи).
2. Нормализует идентификаторы, валидирует данные.
3. Отбирает касания в окне 14 дней до покупки.
4. Применяет модель атрибуции (last touch или linear).
5. Считает Attributed Revenue и ROMI = (Revenue − Cost) / Cost.
6. Сохраняет результат по размещениям и каналам.

Скрипт универсален: как только у бизнеса появится реальный `placements.csv` с cost и реальные касания — ROMI посчитается без изменений кода.

## Атрибуция

Last touch — вся выручка идёт последнему касанию. Linear — выручка делится поровну между всеми касаниями в окне. Окно — 14 дней (три всплеска длятся по 3 дня, между ними 10–14 дней затишья). Органика: если касаний нет — заказ идёт в `organic`. Повторные покупки атрибутируются отдельно, флаг `is_repeat`.

## ROMI

Формула: ROMI = (Attributed Revenue − Cost) / Cost.

Считается только для внешних размещений — у них есть cost. Для собственного канала, акций и органики cost = 0, ROMI не считается. `ROMI_attr` — по модели атрибуции. `ROMI_inc` — по incrementality (не считаем, нет данных).

## Attribution ≠ Incrementality

Атрибуция распределяет уже случившуюся выручку, но не доказывает причинный эффект рекламы. Рост продаж после поста не означает, что пост дал этот рост.

Пример из наших данных: третий всплеск (04–06.09) не связан с просмотрами постов — медианные 20к просмотров и обычная цена. Возможная причина — запуск разборов стажировки в Т-Банк в линейке ПРО. Это пример, когда корреляция «пост → продажи» отсутствует, а бизнес-событие работает.

Для проверки причинного эффекта нужны: A/B-тест, holdout, difference-in-differences, interrupted time series.

## Ограничения

Исторический ROMI по конкретным размещениям восстановить нельзя: нет cost, нет касаний. Incrementality не проверяется: нет экспериментальных данных. Атрибуция работает только на demo-данных, пока бизнес не начнёт собирать реальные события.

## Что нужно начать собирать в бизнесе

| Событие | Поля | Кто пишет |
|---|---|---|
| placement | channel, campaign, creative, publication_time, cost | вручную при закупке |
| bot_start | user_hash, source, timestamp | бот по deep link |
| conversation_started | user_hash, product_interest, timestamp | менеджер / бот |
| payment | user_hash, amount, course, timestamp | как сейчас |

Из этих четырёх таблиц ROMI считается детерминированно, и весь код работает без изменений — меняется только источник `touches`.

## Ответ на вопрос «300 000 ₽ на рекламу»

Не выбирайте канал по прошлой выручке. Сначала: соберите placement-level data; оцените attribution; проведите incrementality test (A/B, holdout); сравните ROMI по каналам; перераспределите бюджет.

## Команда

Владимир — интеграция, архитектура, README, PDF. Максим — исторический анализ, EDA. Диана — модель данных, атрибуция, метрики. Георгий — ноутбуки, сбор постов. Александр — ROMI-калькулятор.
