"""Generate deterministic synthetic inputs for the ROMI calculator."""

from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SRC_DIR = ROOT / "src"
DEMO_PURCHASE_COUNT = 500
TOUCHED_USER_SHARE = 0.35
SECOND_TOUCH_SHARE = 0.15


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    channels = ["@study_a", "@study_b", "@study_c", "@study_d", "@study_e"]
    costs = [40000, 55000, 70000, 35000, 60000, 65000, 45000, 58000, 72000, 0]
    placements = []
    for index, cost in enumerate(costs, start=1):
        placements.append(
            {
                "placement_id": f"p{index:03d}",
                "channel": channels[(index - 1) % len(channels)],
                "publication_time": "2026-07-01 12:00:00",
                "cost": cost,
                "creative_id": f"cr_{(index - 1) % 3 + 1:02d}",
                "creative_type": "native",
            }
        )

    base_path = DATA_DIR / "base.xlsx"
    base = pd.read_excel(base_path) if base_path.exists() else None
    purchases = []
    touches = []
    if base is not None and len(base.columns) >= 4:
        source_purchases = base.iloc[:DEMO_PURCHASE_COUNT, :4].copy()
        source_purchases.columns = ["user_id", "amount", "courses", "purchase_time"]
    else:
        start = datetime(2026, 9, 1, 10, 0)
        source_purchases = pd.DataFrame(
            [
                {
                    "user_id": f"u{index:03d}",
                    "amount": [7900, 9900, 12900, 15900][index % 4],
                    "courses": f"course_{index % 6 + 1:02d}",
                    "purchase_time": start + timedelta(hours=index * 5),
                }
                for index in range(1, DEMO_PURCHASE_COUNT + 1)
            ]
        )

    source_rows = source_purchases.to_dict("records")
    for index, source in enumerate(source_rows, start=1):
        user_id = str(source["user_id"])
        purchase_time = pd.Timestamp(source["purchase_time"]).to_pydatetime()
        purchases.append(
            {
                "order_id": f"o{index:03d}",
                "user_id": user_id,
                "amount": source["amount"],
                "courses": source["courses"],
                "purchase_time": purchase_time.strftime("%Y-%m-%d %H:%M:%S"),
                "is_repeat": "true" if index % 10 == 0 else "false",
            }
        )
    # Касание получает только часть пользователей, остальные остаются organic.
    rng = random.Random(42)
    first_purchase_by_user = {}
    for source in source_rows:
        user_id = str(source["user_id"])
        purchase_time = pd.Timestamp(source["purchase_time"]).to_pydatetime()
        first_purchase_by_user[user_id] = min(
            purchase_time, first_purchase_by_user.get(user_id, purchase_time)
        )

    users = sorted(first_purchase_by_user)
    touched_count = round(len(users) * TOUCHED_USER_SHARE)
    touched_users = set(rng.sample(users, touched_count))
    for user_index, user_id in enumerate(sorted(touched_users), start=1):
        purchase_time = first_purchase_by_user[user_id]
        first_touch = purchase_time - timedelta(days=rng.randint(2, 7))
        placement_number = (user_index % 9) + 1
        touches.append(
            {
                "touch_id": f"t{len(touches) + 1:03d}",
                "user_id": user_id,
                "placement_id": f"p{placement_number:03d}",
                "touch_time": first_touch.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        if rng.random() < SECOND_TOUCH_SHARE:
            second_touch = first_touch + timedelta(hours=rng.randint(6, 24))
            touches.append(
                {
                    "touch_id": f"t{len(touches) + 1:03d}",
                    "user_id": user_id,
                    "placement_id": f"p{(placement_number % 9) + 1:03d}",
                    "touch_time": second_touch.strftime("%Y-%m-%d %H:%M:%S"),
                }
            )

    write_csv(
        SRC_DIR / "placements.csv",
        [
            "placement_id",
            "channel",
            "publication_time",
            "cost",
            "creative_id",
            "creative_type",
        ],
        placements,
    )
    write_csv(
        SRC_DIR / "mock_touches.csv",
        ["touch_id", "user_id", "placement_id", "touch_time"],
        touches,
    )
    write_csv(
        DATA_DIR / "mock_purchases.csv",
        ["order_id", "user_id", "amount", "courses", "purchase_time", "is_repeat"],
        purchases,
    )
    print(
        f"Generated {len(placements)} placements, {len(purchases)} purchases, "
        f"{len(touches)} touches for {len(touched_users)} users"
    )


if __name__ == "__main__":
    main()
