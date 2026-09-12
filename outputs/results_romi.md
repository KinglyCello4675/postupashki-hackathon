# Результаты ROMI demo

## Что было проверено

- 795 строк продаж из `data/base.xlsx`;
- генерация 10 demo-размещений в `src/placements.csv`;
- генерация 500 demo-покупок в `data/mock_purchases.csv`;
- генерация 153 demo-касания для 133 пользователей в `src/mock_touches.csv`;
- модели `last_touch` и `linear`;
- окно атрибуции 14 дней;
- сохранение общей выручки без потерь и дублей;
- удаление временных файлов после пробного запуска.

## Основной результат

Файл `romi_demo.csv` содержит ROMI по размещениям:

- attributed revenue по размещению;
- cost;
- ROMI в виде коэффициента, где `1.0 = 100%`;
- `p010` не имеет ROMI, потому что его cost равен нулю;
- покупки без подходящего касания отражены как `organic`.

Последний запуск на `base.xlsx`:

- обработано `795` покупок в режиме `last_touch`;
- общая выручка: `5 904 671,67 ₽`;
- attributed revenue по платным размещениям: `1 205 536,67 ₽`;
- organic revenue: `4 699 135 ₽` (`79,58%` общей выручки);
- общий cost размещений: `500 000 ₽`;
- ROMI платных размещений: `93,81–298,13%`;
- размещение `p010` с `cost = 0` исключено из ROMI.

Отдельная проверка demo-набора:

- обработано `500` покупок в режиме `linear`;
- общая demo-выручка сохранена без потерь и дублей;
- значение `-1` в итоговом ROMI отсутствует.

## Файлы

| Файл | Назначение |
|---|---|
| `romi_demo.csv` | ROMI по отдельным размещениям |
| `romi_by_channel.csv` | Агрегация выручки, затрат и ROMI по каналам |
| `romi_linear.csv` | Результат linear attribution на 500 demo-покупках |
| `romi_linear_by_channel.csv` | Linear attribution по demo-каналам |
| `src/generate_test_dataset.py` | Генератор placements, touches и mock-покупок |
| `src/placements.csv` | Сгенерированный реестр из 10 demo-размещений |
| `src/mock_touches.csv` | Сгенерированные 153 demo-касания для 133 пользователей |
| `data/mock_purchases.csv` | Сгенерированные 500 demo-покупок |

CSV-файлы demo и результаты в `outputs` создаются при запуске и могут быть удалены после проверки.

## Запуск

Из корня проекта:

```powershell
cd C:\Users\Asus\Desktop\postupashki-hackathon
python -m py_compile src\romi.py src\generate_test_dataset.py
python src\generate_test_dataset.py
python src\romi.py --purchases data\base.xlsx
```

Для linear attribution:

```powershell
python src\romi.py --model linear `
  --purchases data\mock_purchases.csv `
  --output outputs\romi_linear.csv `
  --channel-output outputs\romi_linear_by_channel.csv
```

Для запуска на 500 demo-покупках:

```powershell
python src\romi.py `
  --purchases data\mock_purchases.csv `
  --output outputs\romi_demo_mock.csv `
  --channel-output outputs\romi_demo_mock_by_channel.csv
```

Данные касаний и размещений синтетические и предназначены для демонстрации работы атрибуции. Они не являются доказательством исторического ROMI.

После пробного запуска удалить созданные файлы можно так:

```powershell
Remove-Item `
  src\placements.csv, `
  src\mock_touches.csv, `
  data\mock_purchases.csv, `
  outputs\romi_demo.csv, `
  outputs\romi_by_channel.csv, `
  outputs\romi_linear.csv, `
  outputs\romi_linear_by_channel.csv, `
  src\__pycache__ `
  -Recurse -Force -ErrorAction SilentlyContinue
```

## Функции `src/romi.py`

| Функция | Назначение |
|---|---|
| `read_csv(path)` | Проверяет наличие CSV-файла и загружает его в таблицу pandas. |
| `read_purchases(path)` | Загружает продажи из CSV или Excel и приводит колонки к единой схеме. |
| `_normalize_identifier(value)` | Приводит идентификаторы из Excel и CSV к строковому виду. |
| `normalize_identifiers(...)` | Нормализует ID размещений, касаний, пользователей и заказов перед объединением таблиц. |
| `require_columns(data, required, name)` | Проверяет наличие обязательных колонок во входной таблице. |
| `_parse_datetime(data, column, name)` | Преобразует колонку в даты и сообщает об ошибочных значениях. |
| `validate_inputs(...)` | Проверяет структуру данных, уникальность ID, суммы, даты и соответствие размещений касаниям. |
| `attribute_purchases(...)` | Связывает покупки с касаниями и распределяет выручку через `last_touch` или `linear`. |
| `_add_romi(data)` | Добавляет к результату прибыль и ROMI по формуле `(revenue - cost) / cost`. |
| `calculate_romi(...)` | Выполняет полный расчёт по размещениям, каналам и деталям атрибуции. |
| `main()` | Читает параметры командной строки, запускает расчёт и сохраняет CSV-результаты. |

### Последовательность работы

```text
прочитать входные файлы
→ нормализовать идентификаторы
→ проверить данные
→ отобрать касания в 14-дневном окне
→ применить модель атрибуции
→ посчитать выручку и ROMI
→ сохранить результаты по размещениям и каналам
```
