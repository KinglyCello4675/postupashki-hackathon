
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data"
DEFAULT_PLACEMENTS = ROOT / "src" / "placements.csv"
DEFAULT_TOUCHES = ROOT / "src" / "mock_touches.csv"
DEFAULT_PURCHASES = ROOT / "data" / "base.xlsx"
DEFAULT_PLACEMENT_OUTPUT = ROOT / "outputs" / "romi_demo.csv"
DEFAULT_CHANNEL_OUTPUT = ROOT / "outputs" / "romi_by_channel.csv"


def read_csv(path: Path) -> pd.DataFrame:
    """Прочитать CSV-файл и сообщить об отсутствии файла."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    return pd.read_csv(path)


def read_purchases(path: Path) -> pd.DataFrame:
    """Прочитать продажи из CSV или Excel и привести их к единой схеме."""
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if path.suffix.lower() in {".xls", ".xlsx"}:
        data = pd.read_excel(path)
        if len(data.columns) < 4:
            raise ValueError("Purchases workbook must contain at least four columns")
        # В base.xlsx используются бизнес-названия колонок, поэтому берём их по позиции.
        data = data.iloc[:, :4].copy()
        data.columns = ["user_id", "amount", "courses", "purchase_time"]
        data.insert(0, "order_id", [f"order_{index + 1:04d}" for index in range(len(data))])
        data["is_repeat"] = False
        return data
    return read_csv(path)


def _normalize_identifier(value: object) -> str:
    """Привести идентификатор из Excel или CSV к единому строковому виду."""
    if pd.isna(value):
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def normalize_identifiers(
    placements: pd.DataFrame,
    touches: pd.DataFrame,
    purchases: pd.DataFrame,
) -> None:
    """Нормализовать идентификаторы во всех таблицах перед объединением."""
    for data, columns in (
        (placements, ("placement_id",)),
        (touches, ("touch_id", "user_id", "placement_id")),
        (purchases, ("order_id", "user_id")),
    ):
        for column in columns:
            # Excel может загрузить числовой ID как float, а CSV хранит его как строку.
            data[column] = data[column].map(_normalize_identifier)


def require_columns(data: pd.DataFrame, required: set[str], name: str) -> None:
    """Проверить наличие обязательных колонок в таблице."""
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"{name} is missing columns: {sorted(missing)}")


def _parse_datetime(data: pd.DataFrame, column: str, name: str) -> None:
    """Преобразовать колонку в даты и отклонить некорректные значения."""
    data[column] = pd.to_datetime(data[column], errors="coerce")
    if data[column].isna().any():
        raise ValueError(f"{name}.{column} must contain valid datetimes")


def validate_inputs(
    placements: pd.DataFrame,
    touches: pd.DataFrame,
    purchases: pd.DataFrame,
) -> None:
    """Проверить структуру, значения и временную согласованность входных данных."""
    require_columns(
        placements,
        {"placement_id", "channel", "publication_time", "cost"},
        "placements",
    )
    require_columns(
        touches,
        {"touch_id", "user_id", "placement_id", "touch_time"},
        "touches",
    )
    require_columns(
        purchases,
        {"order_id", "user_id", "amount", "purchase_time"},
        "purchases",
    )

    if placements["placement_id"].isna().any() or placements["placement_id"].eq("").any():
        raise ValueError("placements.placement_id must not be empty")
    if placements["placement_id"].duplicated().any():
        raise ValueError("placements.placement_id must be unique")
    if touches["touch_id"].duplicated().any():
        raise ValueError("touches.touch_id must be unique")
    if purchases["order_id"].duplicated().any():
        raise ValueError("purchases.order_id must be unique")

    placements["cost"] = pd.to_numeric(placements["cost"], errors="coerce")
    purchases["amount"] = pd.to_numeric(purchases["amount"], errors="coerce")
    if purchases["amount"].isna().any():
        raise ValueError("purchases.amount must contain numeric values")
    if (placements["cost"] < 0).any() or (purchases["amount"] < 0).any():
        raise ValueError("cost and amount cannot be negative")

    _parse_datetime(placements, "publication_time", "placements")
    _parse_datetime(touches, "touch_time", "touches")
    _parse_datetime(purchases, "purchase_time", "purchases")

    unknown = set(touches["placement_id"]) - set(placements["placement_id"])
    if unknown:
        raise ValueError(f"touches contains unknown placement_id values: {sorted(unknown)}")

    touch_placements = touches.merge(
        placements[["placement_id", "publication_time"]],
        on="placement_id",
        how="left",
        validate="many_to_one",
    )
    if (touch_placements["touch_time"] < touch_placements["publication_time"]).any():
        raise ValueError("touches.touch_time cannot precede placement publication_time")


def attribute_purchases(
    placements: pd.DataFrame,
    touches: pd.DataFrame,
    purchases: pd.DataFrame,
    window_days: int = 14,
    model: str = "last_touch",
) -> pd.DataFrame:
    """Распределить выручку покупок по размещениям выбранной моделью."""
    if window_days <= 0:
        raise ValueError("window_days must be positive")
    if model not in {"last_touch", "linear"}:
        raise ValueError("model must be 'last_touch' or 'linear'")

    placement_ids = set(placements["placement_id"])
    touch_by_user = {
        user_id: frame.sort_values("touch_time")
        for user_id, frame in touches.groupby("user_id", sort=False)
    }
    rows: list[dict[str, object]] = []
    for purchase in purchases.to_dict("records"):
        purchase_time = purchase["purchase_time"]
        user_touches = touch_by_user.get(purchase["user_id"], touches.iloc[0:0])
        # Учитываем только касания до покупки и внутри заданного окна атрибуции.
        eligible = user_touches[
            (user_touches["touch_time"] <= purchase_time)
            & (
                user_touches["touch_time"]
                >= purchase_time - pd.Timedelta(days=window_days)
            )
        ]
        if eligible.empty:
            rows.append(
                {
                    "order_id": purchase["order_id"],
                    "user_id": purchase["user_id"],
                    "amount": purchase["amount"],
                    "is_repeat": purchase.get("is_repeat", False),
                    "placement_id": "organic",
                    "attribution_share": 1.0,
                    "attributed_revenue": purchase["amount"],
                }
            )
            continue

        selected = eligible.tail(1) if model == "last_touch" else eligible
        # Линейная модель делит выручку, а last-touch отдаёт её последнему касанию.
        share = 1 / len(selected)
        for touch in selected.to_dict("records"):
            placement_id = touch["placement_id"]
            if placement_id not in placement_ids:
                raise ValueError(f"Unknown placement_id after validation: {placement_id}")
            rows.append(
                {
                    "order_id": purchase["order_id"],
                    "user_id": purchase["user_id"],
                    "amount": purchase["amount"],
                    "is_repeat": purchase.get("is_repeat", False),
                    "placement_id": placement_id,
                    "attribution_share": share,
                    "attributed_revenue": purchase["amount"] * share,
                }
            )
    return pd.DataFrame(rows)


def _add_romi(data: pd.DataFrame) -> pd.DataFrame:
    """Добавить к таблице прибыль и ROMI."""
    result = data.copy()
    result["profit"] = result["revenue"] - result["cost"]
    # Для нулевой выручки или бесплатного размещения оставляем ROMI пустым.
    has_attributed_revenue = result["revenue"] > 0
    result["romi"] = result["profit"].div(
        result["cost"].where((result["cost"] > 0) & has_attributed_revenue)
    )
    return result


def calculate_romi(
    placements_path: Path,
    touches_path: Path,
    purchases_path: Path,
    window_days: int = 14,
    model: str = "last_touch",
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Рассчитать ROMI по размещениям, каналам и деталям атрибуции."""
    placements = read_csv(placements_path)
    touches = read_csv(touches_path)
    purchases = read_purchases(purchases_path)
    normalize_identifiers(placements, touches, purchases)
    validate_inputs(placements, touches, purchases)
    attributed = attribute_purchases(placements, touches, purchases, window_days, model)

    revenue = attributed.groupby("placement_id", as_index=False)["attributed_revenue"].sum()
    placement_result = placements.merge(revenue, on="placement_id", how="left")
    placement_result["attributed_revenue"] = placement_result["attributed_revenue"].fillna(0)
    placement_result = placement_result.rename(columns={"attributed_revenue": "revenue"})
    placement_result = placement_result[["placement_id", "channel", "cost", "revenue"]]
    organic_revenue = attributed.loc[
        attributed["placement_id"].eq("organic"), "attributed_revenue"
    ].sum()
    if organic_revenue:
        placement_result = pd.concat(
            [
                placement_result,
                pd.DataFrame(
                    [{"placement_id": "organic", "channel": "organic", "cost": 0, "revenue": organic_revenue}]
                ),
            ],
            ignore_index=True,
        )
    placement_result = _add_romi(placement_result).sort_values(
        "romi", ascending=False, na_position="last", ignore_index=True
    )

    channel_revenue = (
        placement_result.groupby("channel", as_index=False)["revenue"].sum()
    )
    channel_cost = placements.groupby("channel", as_index=False)["cost"].sum(min_count=1)
    channel_result = channel_cost.merge(channel_revenue, on="channel", how="outer")
    channel_result["cost"] = channel_result["cost"].fillna(0)
    channel_result["revenue"] = channel_result["revenue"].fillna(0)
    channel_result = _add_romi(channel_result[["channel", "cost", "revenue"]])
    channel_result = channel_result.sort_values(
        "romi", ascending=False, na_position="last", ignore_index=True
    )
    return placement_result, channel_result, attributed


def main() -> None:
    """Обработать аргументы командной строки и сохранить результаты расчёта."""
    parser = argparse.ArgumentParser(
        description="Расчёт атрибутированной выручки и ROMI"
    )
    parser.add_argument("--placements", type=Path, default=DEFAULT_PLACEMENTS)
    parser.add_argument("--touches", type=Path, default=DEFAULT_TOUCHES)
    parser.add_argument("--purchases", type=Path, default=DEFAULT_PURCHASES)
    parser.add_argument("--output", type=Path, default=DEFAULT_PLACEMENT_OUTPUT)
    parser.add_argument("--channel-output", type=Path, default=DEFAULT_CHANNEL_OUTPUT)
    parser.add_argument("--window-days", type=int, default=14)
    parser.add_argument("--model", choices=("last_touch", "linear"), default="last_touch")
    args = parser.parse_args()

    placement_result, channel_result, attributed = calculate_romi(
        args.placements,
        args.touches,
        args.purchases,
        args.window_days,
        args.model,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.channel_output.parent.mkdir(parents=True, exist_ok=True)
    placement_output = placement_result.rename(
        columns={"revenue": "attributed_revenue"}
    )[["placement_id", "channel", "cost", "attributed_revenue", "romi"]]
    placement_output.to_csv(args.output, index=False, encoding="utf-8-sig")
    channel_result.to_csv(args.channel_output, index=False, encoding="utf-8-sig")
    print(f"Processed {attributed['order_id'].nunique()} purchases with {args.model} attribution")
    print(f"Saved: {args.output}")
    print(f"Saved: {args.channel_output}")
    print(placement_output.to_string(index=False))


if __name__ == "__main__":
    main()
