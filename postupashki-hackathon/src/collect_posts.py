"""
Сборщик публичной истории Telegram-канала через веб-превью t.me/s/<channel>.

Данные РЕАЛЬНЫЕ: это то, что видит любой человек без подписки и без авторизации.
Ни Telethon, ни API-ключей, ни админского доступа не требуется — как и разрешено
условием кейса (только легально доступные публичные источники).

Запуск:
    python src/collect_posts.py
    python src/collect_posts.py --channel postypashki_old --since 2026-08-01 --until 2026-09-11

Результат: data/posts.csv — по строке на пост.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://t.me/s/{channel}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
PAGE_PAUSE = 0.7        # вежливая пауза между страницами
MAX_PAGES = 200         # предохранитель от бесконечного цикла


# --------------------------------------------------------------------------
# парсинг
# --------------------------------------------------------------------------

def parse_views(raw: str | None) -> int | None:
    """'23.1K' -> 23100, '968' -> 968, None -> None"""
    if not raw:
        return None
    raw = raw.strip().replace(",", "")
    m = re.match(r"^([\d.]+)\s*([KMkm]?)$", raw)
    if not m:
        return None
    value, suffix = float(m.group(1)), m.group(2).upper()
    return int(value * {"": 1, "K": 1_000, "M": 1_000_000}[suffix])


def parse_page(html: str) -> list[dict]:
    """Достаёт посты со страницы веб-превью."""
    soup = BeautifulSoup(html, "html.parser")
    posts = []

    for node in soup.select("div.tgme_widget_message"):
        data_post = node.get("data-post", "")            # 'channel/1234'
        if "/" not in data_post:
            continue
        channel, _, post_id = data_post.partition("/")
        if not post_id.isdigit():
            continue

        time_tag = node.select_one("a.tgme_widget_message_date time")
        dt = time_tag.get("datetime") if time_tag else None

        text_node = node.select_one("div.tgme_widget_message_text")
        text = text_node.get_text("\n", strip=True) if text_node else ""

        views_node = node.select_one("span.tgme_widget_message_views")
        views = parse_views(views_node.get_text() if views_node else None)

        # репост чужого поста: у него есть подпись с исходным автором
        fwd = node.select_one("a.tgme_widget_message_forwarded_from_name")

        posts.append({
            "channel": channel,
            "post_id": int(post_id),
            "url": f"https://t.me/{channel}/{post_id}",
            "datetime": dt,
            "views": views,
            "is_forward": bool(fwd),
            "forward_from": fwd.get_text(strip=True) if fwd else "",
            "text": text,
        })

    return sorted(posts, key=lambda p: p["post_id"])


# --------------------------------------------------------------------------
# классификация — правила, а не нейросеть
# --------------------------------------------------------------------------

RULES = [
    ("DISCOUNT", [r"скидк", r"промокод", r"-\s?\d{2}\s?%", r"\d{2}\s?%\s*на", r"акци"]),
    ("LAUNCH",   [r"открываем набор", r"стартуе", r"запуск", r"新", r"новый курс", r"старт курса"]),
    ("SALE",     [r"купит", r"оплат", r"осталось мест", r"набор на", r"наши курсы", r"записать"]),
    ("NATIVE",   [r"\berid\b", r"реклама\b", r"партнёр", r"партнер"]),
]


def classify(text: str) -> str:
    """Первое сработавшее правило выигрывает, поэтому порядок RULES важен."""
    low = text.lower()
    for label, patterns in RULES:
        if any(re.search(p, low) for p in patterns):
            return label
    return "CONTENT"


# --------------------------------------------------------------------------
# обход страниц
# --------------------------------------------------------------------------

def collect(channel: str, since: datetime, until: datetime,
            session: requests.Session | None = None) -> list[dict]:
    session = session or requests.Session()
    url = BASE.format(channel=channel)
    collected: dict[int, dict] = {}
    before: int | None = None

    for page in range(MAX_PAGES):
        params = {"before": before} if before else {}
        resp = session.get(url, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()

        posts = parse_page(resp.text)
        if not posts:
            print("пустая страница — останавливаюсь", file=sys.stderr)
            break

        for p in posts:
            if not p["datetime"]:
                continue
            dt = datetime.fromisoformat(p["datetime"].replace("Z", "+00:00"))
            p["dt"] = dt
            if since <= dt <= until:
                collected[p["post_id"]] = p

        oldest = min(p["post_id"] for p in posts)
        oldest_dt = min(
            datetime.fromisoformat(p["datetime"].replace("Z", "+00:00"))
            for p in posts if p["datetime"]
        )
        print(f"страница {page + 1}: посты {oldest}–{max(p['post_id'] for p in posts)}, "
              f"самый старый {oldest_dt:%Y-%m-%d}, собрано {len(collected)}", file=sys.stderr)

        # ушли раньше нужного периода — дальше листать незачем
        if oldest_dt < since:
            break
        if before is not None and oldest >= before:
            print("пагинация не двигается — останавливаюсь", file=sys.stderr)
            break

        before = oldest
        time.sleep(PAGE_PAUSE)

    return [collected[k] for k in sorted(collected)]


# --------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="postypashki_old")
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--until", default="2026-09-11")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    since = datetime.fromisoformat(args.since).replace(tzinfo=timezone.utc)
    until = datetime.fromisoformat(args.until).replace(tzinfo=timezone.utc)

    root = Path(__file__).resolve().parent.parent
    out = Path(args.out) if args.out else root / "data" / "posts.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    posts = collect(args.channel, since, until)
    if not posts:
        print("ничего не собрано — проверь имя канала и период", file=sys.stderr)
        return

    for p in posts:
        p["post_type"] = classify(p["text"])
        p["date"] = p["dt"].date().isoformat()
        p["text"] = p["text"].replace("\n", " ")[:1000]
        p.pop("dt")

    fields = ["channel", "post_id", "url", "date", "datetime", "views",
              "post_type", "is_forward", "forward_from", "text"]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(posts)

    print(f"\nсобрано постов: {len(posts)} → {out}")
    counts: dict[str, int] = {}
    for p in posts:
        counts[p["post_type"]] = counts.get(p["post_type"], 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:10s} {v}")


if __name__ == "__main__":
    main()
