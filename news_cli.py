#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News CLI (Python + NewsAPI)

Коротко:
- Консольный скрипт ищет новости по ключевому слову через NewsAPI (endpoint /v2/everything).
- Ключ читается из файла .env (переменная API_NEWS).
- По умолчанию выводит до 5 статей на русском за последние 7 дней.
- Есть обработка ошибок сети и API, форматированный вывод и опции CLI.

Зачем:
- Учебный проект: показать базовые практики интеграции внешнего API, работы с .env, 
  обработки ошибок, аргументов командной строки и форматирования вывода.

Как использовать:
- Активируйте виртуальное окружение, установите зависимости, создайте .env с API_NEWS, затем:
  python news_cli.py --q "финансы" --n 5
"""

from __future__ import annotations

import os
import sys
import argparse
import json
import textwrap
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

import requests
from dotenv import load_dotenv

# Базовый URL для поиска по ключевому слову
NEWS_API_URL = "https://newsapi.org/v2/everything"


def load_api_key() -> str:
    """
    Загружает API-ключ из файла .env (переменная API_NEWS).
    Используем python-dotenv, чтобы не хранить секреты в коде/репозитории.

    Возвращает:
        str: значение ключа API_NEWS

    Исключения:
        RuntimeError: если ключ не найден
    """
    # Загружаем переменные окружения из .env (файл в корне проекта)
    load_dotenv()
    api_key = os.getenv("API_NEWS")

    if not api_key:
        raise RuntimeError(
            "Не найден API-ключ. Убедитесь, что в файле .env есть строка:\n"
            "API_NEWS=ваш_ключ\n"
            "и что вы запускаете скрипт из корня проекта."
        )
    return api_key


def fetch_news(
    query: str,
    api_key: str,
    *,
    page_size: int = 5,
    language: str = "ru",
    days: int = 7,
) -> Dict[str, Any]:
    """
    Выполняет запрос к NewsAPI (endpoint /v2/everything) по ключевой фразе.

    Параметры:
        query (str): ключевое слово/тема для поиска
        api_key (str): ключ NewsAPI
        page_size (int): сколько статей запросить (max 5 по ТЗ)
        language (str): язык статей (по умолчанию 'ru')
        days (int): глубина поиска в днях (по умолчанию 7)

    Возвращает:
        dict: JSON-ответ от NewsAPI (с ключами status, totalResults, articles, ...)

    Исключения:
        RuntimeError: при любых сетевых/HTTP/логических ошибках
    """
    # Важно: используем timezone-aware время (UTC), чтобы не ловить предупреждения линтера
    # и корректно работать с датами.
    from_date = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()

    params = {
        "q": query,                  # поисковая фраза
        "language": language,        # язык результатов (ru|en|...)
        "sortBy": "publishedAt",     # сортировка по дате публикации
        "from": from_date,           # не старше указанной даты
        "pageSize": page_size,       # сколько статей вернуть
        "apiKey": api_key,           # ключ NewsAPI (в заголовок тут не требуется)
    }

    try:
        resp = requests.get(NEWS_API_URL, params=params, timeout=20)
        resp.raise_for_status()  # выбросит HTTPError, если код ответа не 2xx
        data = resp.json()
    except requests.exceptions.Timeout:
        raise RuntimeError("Превышено время ожидания ответа от NewsAPI.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ошибка сети: не удалось подключиться к NewsAPI.")
    except requests.exceptions.HTTPError as e:
        # Пытаемся извлечь сообщение об ошибке от NewsAPI, если оно есть в JSON
        try:
            err = resp.json()
            msg = err.get("message") or str(e)
        except Exception:
            msg = str(e)
        raise RuntimeError(f"HTTP ошибка: {msg}")

    # Ответ NewsAPI должен иметь статус "ok"
    if data.get("status") != "ok":
        msg = data.get("message", "Неизвестная ошибка от NewsAPI.")
        raise RuntimeError(f"Ответ со статусом '{data.get('status')}': {msg}")

    return data


def human_datetime(iso_str: str) -> str:
    """
    Преобразует ISO-строку времени (из NewsAPI) в человекочитаемый формат 
    в локальной таймзоне пользователя.

    Пример входа: '2025-08-20T09:15:00Z'
    Пример выхода: '20.08.2025 12:15' (зависит от TZ системы)

    Возвращает исходную строку, если парсинг не удался.
    """
    if not iso_str:
        return ""
    try:
        # NewsAPI возвращает время в UTC с суффиксом 'Z'
        aware_utc = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        # Перевод в локальную таймзону пользователя
        local_dt = aware_utc.astimezone()
        return local_dt.strftime("%d.%m.%Y %H:%M")
    except Exception:
        return iso_str  # на всякий случай не падаем, а выводим как есть


def format_article(article: Dict[str, Any]) -> str:
    """
    Форматирует одну статью для консольного вывода: заголовок, описание, ссылка, дата.

    Возвращает:
        str: многострочная строка готовая к печати.
    """
    title = article.get("title") or "(без заголовка)"
    desc = article.get("description") or "(без описания)"
    url = article.get("url") or ""
    published_at = human_datetime(article.get("publishedAt") or "")

    # Переносим описание по 100 символов, чтобы в терминале не было «простыней»
    wrapped_title = textwrap.fill(title, width=100)
    wrapped_desc = textwrap.fill(desc, width=100)

    return (
        f"— {wrapped_title}\n"
        f"{wrapped_desc}\n"
        f"Ссылка: {url}\n"
        f"Опубликовано: {published_at}\n"
    )


def build_arg_parser() -> argparse.ArgumentParser:
    """
    Создаёт и настраивает парсер аргументов командной строки.

    Возвращает:
        argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Поиск новостей по теме через NewsAPI (/v2/everything).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--q", "--query",
        dest="query",
        help="Ключевое слово/тема (если не указать — будет интерактивный ввод).",
    )
    parser.add_argument(
        "--n", "--limit",
        dest="limit",
        type=int,
        default=5,
        help="Сколько новостей показать (1–5).",
    )
    parser.add_argument(
        "--lang",
        dest="language",
        default="ru",
        help="Язык новостей (ru, en, ...).",
    )
    parser.add_argument(
        "--days",
        dest="days",
        type=int,
        default=7,
        help="Искать новости не старше N дней.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Вывести результат в формате JSON (для интеграций/обработки).",
    )
    return parser


def main() -> None:
    """
    Точка входа:
    - Читает аргументы
    - Загружает API-ключ
    - Запрашивает у пользователя тему (если не передана аргументом)
    - Делает запрос к NewsAPI
    - Выводит до N статей (красиво или как JSON)
    """
    parser = build_arg_parser()
    args = parser.parse_args()

    # 1) Загружаем API-ключ
    try:
        api_key = load_api_key()
    except RuntimeError as e:
        print(f"[Ошибка] {e}", file=sys.stderr)
        sys.exit(1)

    # 2) Получаем запрос (или спрашиваем у пользователя)
    query: Optional[str] = args.query
    if not query:
        try:
            query = input("Введите тему для поиска новостей: ").strip()
        except EOFError:
            print("[Ошибка] Не удалось прочитать ввод.", file=sys.stderr)
            sys.exit(1)

    if not query:
        print("[Подсказка] Пустой запрос. Примеры: технологии, финансы, климат.")
        sys.exit(0)

    # 3) Нормируем предел (по ТЗ — не больше 5)
    limit = max(1, min(args.limit, 5))

    # 4) Сообщаем пользователю, что делаем
    print(f"\nИщу новости по теме: “{query}” (до {limit} шт., язык: {args.language}, последние {args.days} дн.)\n")

    # 5) Делаем запрос
    try:
        data = fetch_news(
            query=query,
            api_key=api_key,
            page_size=limit,
            language=args.language,
            days=args.days,
        )
    except RuntimeError as e:
        print(f"[Ошибка] {e}", file=sys.stderr)
        sys.exit(1)

    articles: List[Dict[str, Any]] = data.get("articles") or []

    if not articles:
        print("Ничего не найдено по этой теме в выбранном интервале.")
        sys.exit(0)

    # 6) Если требуется JSON — отдаём как есть (но с ensure_ascii=False)
    if args.as_json:
        print(json.dumps(articles, ensure_ascii=False, indent=2))
        sys.exit(0)

    # 7) Иначе — красивый текстовый вывод
    for idx, article in enumerate(articles, start=1):
        print(f"{idx}. {format_article(article)}")

    print("Готово.")


if __name__ == "__main__":
    main()
#ТестКоммит