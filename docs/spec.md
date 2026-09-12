# Спецификация атрибуции и метрик

> Файл ведёт Диана. Володя создал структуру, содержание — за Дианой.

## 1. Сущности и связи

(Диана описывает: Campaign, Placement, Creative, Channel, User, Touch, Lead, Payment, Order, Course)

## 2. Атрибуция

### Модель
- Last touch (основная)
- Linear (сравнение)

### Окно атрибуции
- 14 дней до покупки
- Обоснование: ...

### Правила распределения revenue
- Если касаний нет → `organic`
- Если касаний несколько → по правилу модели
- Повторные покупки → атрибутируем отдельно, флаг `is_repeat`

### Attribution ≠ Incrementality
- Атрибуция распределяет уже случившуюся выручку.
- Причинный эффект рекламы не доказывает.
- Для проверки нужен A/B, holdout или DiD.

## 3. ROMI

Формула: ROMI = (Attributed Revenue − Cost) / Cost

- ROMI_attr — по модели атрибуции
- ROMI_inc — по incrementality (не считаем, нет данных)
- Если cost неизвестен → ROMI не считаем

## 4. Минимальный набор данных

**Placement:**
- placement_id, channel, publication_time, cost, creative_id

**Touch:**
- touch_id, user_id, placement_id, touch_time

**Purchase:**
- order_id, user_id, amount, courses, purchase_time

## 5. Ограничения

- Исторический ROMI восстановить нельзя.
- Нет cost → нет ROMI.
- Нет касаний → атрибуция только на demo-данных.
- Incrementality не проверяется.

## 6. Что нужно начать собирать в бизнесе

- Уникальные tracking-ссылки на каждое размещение.
- Cost каждого размещения.
- Логирование source у менеджера.
- Флаг повторной покупки.
