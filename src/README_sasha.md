# ROMI-калькулятор (Саша)

> Файл ведёт Саша.

## Что нужно сделать

Скрипт `src/romi.py`, который:

1. Читает `src/placements.csv` (реестр размещений с cost).
2. Читает `src/mock_touches.csv` (касания user → placement).
3. Читает `data/base.xlsx` (реальные продажи).
4. Связывает: user → placement → purchase.
5. Считает Attributed Revenue по placement.
6. Считает ROMI = (Revenue − Cost) / Cost.
7. Сохраняет результат в `outputs/romi_demo.csv`.

## Формат результата

| placement_id | channel | cost | attributed_revenue | romi |
|---|---|---|---|---|
| p001 | @channel_A | 20000 | 60000 | 2.0 |
| p002 | @channel_B | 30000 | 20000 | −0.33 |

## Demo-данные

Если реальных нет — генерируем mock. В README проекта это помечено.
