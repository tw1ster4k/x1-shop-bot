"""
Опциональный LLM-адаптер (OpenAI-compatible API).

Подключение (например, GPT-4o-mini, DeepSeek, локальная LLM):
    export OPENAI_BASE_URL=https://api.openai.com/v1
    export OPENAI_API_KEY=sk-...
    export ASSISTANT_MODEL=gpt-4o-mini

Если переменные не заданы — используется детерминированный движок из bot.py.

Защита от галлюцинаций:
1. LLM видит ТОЛЬКО текст базы знаний (никакого доступа к интернету и внешним данным).
2. Системный промпт запрещает факты вне базы (см. knowledge_base/system_prompt.md).
3. Пост-фильтр (post_guard): если ответ LLM касается запрещенной темы
   (скидки, статус заказа) или содержит «выдуманные» сущности вроде трек-номера,
   он заменяется безопасным детерминированным ответом.
"""
from __future__ import annotations

import os
import re

from . import bot

SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "system_prompt.md")
KB_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "knowledge_base.md")

# Темы, где LLM традиционно галлюцинирует — жесткий пост-фильтр
_FORBIDDEN = [
    (re.compile(r"скидк|промокод|уступ", re.I), "discount"),
    (re.compile(r"заказ\s*(№|номер|N|#)\s*\d+|статус.*заказ|трек-?номер\s*[:№]?\s*\w+", re.I), "order_status"),
]


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def post_guard(user_text: str, llm_answer: str) -> str | None:
    """Возвращает безопасный ответ, если ответ LLM нарушает регламент."""
    intent = bot.detect_intent(user_text)
    for rx, forbidden_intent in _FORBIDDEN:
        if forbidden_intent == intent and rx.search(llm_answer):
            return bot.reply(user_text)
    return None


def ask(user_text: str) -> str:
    """Ответ пользователю: LLM, если настроен, иначе детерминированный движок."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return bot.reply(user_text)

    from openai import OpenAI  # pip install openai

    client = OpenAI(api_key=api_key, base_url=os.getenv("OPENAI_BASE_URL"))
    system = _read(SYSTEM_PROMPT_PATH) + "\n\n## База знаний\n" + _read(KB_PATH)
    resp = client.chat.completions.create(
        model=os.getenv("ASSISTANT_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_text},
        ],
        temperature=0,
    )
    answer = resp.choices[0].message.content.strip()
    safe = post_guard(user_text, answer)
    return safe if safe else answer
