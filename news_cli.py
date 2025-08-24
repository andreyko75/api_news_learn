#!/usr/bin/env python3
import os
import sys
import argparse
import textwrap
from datetime import datetime, timedelta
from typing import Optional, List, Dict

import requests
from dotenv import load_dotenv

NEWS_API_URL = "https://newsapi.org/v2/everything"

def load_api_key() -> str:
    load_dotenv()  # загрузит .env из корня проекта
    api_key = os.getenv("API_NEWS")
    if not api_key:
        raise RuntimeError(
            "Не найден API-ключ. Убедитесь, что в файле .env есть строка: API_NEWS=... "
            "и что вы запускаете скрипт из корня проекта."
        )
    return api_key

def fetch_news(query: str, api_key: str, page_size: int = 5) -> Dict:
    # Ограничим период последними 7 днями, чтобы результаты были актуальнее
    from_date = (datetime.utcnow() - timedelta(days=7)).date().isoformat()
    params = {
        "q": query,
        "pageSize": page_size,
        "language": "ru",          # можно убрать, если нужны новости на всех языках
        "sortBy": "publishedAt",
        "from": from_date,
        "apiKey": api_key,
    }
    try:
        resp = requests.get(NEWS_API_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.Timeout:
        raise RuntimeError("Превышено время ожидания ответа от News API.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ошибка сети: не удалось подключиться к News API.")
    except requests.exceptions.HTTPError as e:
        # Попробуем извлечь сообщение об ошибке от NewsAPI, если оно есть
        try:
            err = resp.json()
            msg = err.get("message") or str(e)
        except Exception:
            msg = str(e)
        raise RuntimeError(f"HTTP ошибка: {msg}")

    # Ответ формата {"status": "ok"|"error", ...}
    status = data.get("status")
    if status != "ok":
        msg = data.get("message", "Неизвестная ошибка от News API.")
        raise RuntimeError(f"Ответ со статусом '{status}': {msg}")

    return data

def format_article(a: Dict) -> str:
    title = a.get("title") or "(без заголовка)"
    desc = a.get("description") or "(без описания)"
    url = a.get("url") or ""
    published_at = a.get("publishedAt") or ""
    # Аккуратно завернём описание
    wrapped_desc = textwrap.fill(desc, width=100)
    return f"""— {title}
{wrapped_desc}
Ссылка: {url}
Опубликовано: {published_at}
"""

def main():
    parser = argparse.ArgumentParser(
        description="Поиск новостей по теме через News API (everything endpoint)."
    )
    parser.add_argument("--q", "--query", dest="query", help="Ключевое слово/тема (если не указать — спросит).")
    parser.add_argument("--n", "--limit", dest="limit", type=int, default=5, help="Сколько новостей показать (1–5).")
    args = parser.parse_args()

    try:
        api_key = load_api_key()
    except RuntimeError as e:
        print(f"[Ошибка] {e}", file=sys.stderr)
        sys.exit(1)

    query = args.query
    if not query:
        try:
            query = input("Введите тему для поиска новостей: ").strip()
        except EOFError:
            print("[Ошибка] Не удалось прочитать ввод.", file=sys.stderr)
            sys.exit(1)

    if not query:
        print("[Подсказка] Пустой запрос. Введите, например: технологии, финансы, климат.")
        sys.exit(0)

    limit = max(1, min(args.limit, 5))

    print(f"\nИщу новости по теме: “{query}” (до {limit} шт.)\n")

    try:
        data = fetch_news(query=query, api_key=api_key, page_size=limit)
    except RuntimeError as e:
        print(f"[Ошибка] {e}", file=sys.stderr)
        sys.exit(1)

    articles: Optional[List[Dict]] = data.get("articles") or []
    if not articles:
        print("Ничего не найдено по этой теме за последние 7 дней.")
        sys.exit(0)

    for idx, a in enumerate(articles, start=1):
        print(f"{idx}. {format_article(a)}")

    print("Готово.")

if __name__ == "__main__":
    main()
