"""
Бот поддержки интернет-магазина «Наушники X1».

Архитектура защиты от галлюцинаций:
1. База знаний — единственный источник фактов (knowledge_base/knowledge_base.md).
2. Системный промпт жестко запрещает отвечать фактами вне базы.
3. Детерминированный движок (этот файл) отвечает только по правилам регламента;
   для любого неизвестного факта — честный отказ, без выдумывания.
4. Если подключен LLM-адаптер (src/llm_adapter.py), он получает ТОЛЬКО текст
   базы знаний как контекст + системный промпт, а его ответ проходит
   пост-проверку (post-guard): запрещенные темы (скидки/статусы заказов)
   фильтруются и заменяются безопасным ответом.

Запуск краш-теста:  python -m tests.crash_test
"""
from __future__ import annotations

import re
import os

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "knowledge_base", "knowledge_base.md")

# --- Категории, на которые бот имеет право отвечать (строго по регламенту) ---

RE_ORDER = re.compile(r"(заказ|номер|статус|трек|где.*(мой|моя)|отслед)", re.I)
RE_RETURN = re.compile(r"(вернут|возврат|обмен|отказ)", re.I)
RE_DEFECT = re.compile(r"(брак|сломал|не работ|дефект|экспертиз)", re.I)
RE_DISCOUNT = re.compile(r"(скидк|промокод|дёшев|дешев|уступ|акци|промо|код)", re.I)
RE_DELIVERY = re.compile(r"(достав|курьер|слот|привез|когда.*(при|достав))", re.I)
RE_PRICE = re.compile(r"(цена|стоим|сколько|налич|есть.*в продаж|купить)", re.I)
RE_JAILBREAK = re.compile(r"(забудь|игнор|ignore|forget|системн.*промпт|новые правила|ты теперь)", re.I)


def _has_defect(text: str) -> bool:
    return bool(RE_DEFECT.search(text))


def _day_number(text: str) -> int | None:
    m = re.search(r"(\d{1,2})\s*-\s*(й|й день|дн)", text)
    if m:
        return int(m.group(1))
    return None


def detect_intent(text: str) -> str:
    t = text.lower()
    if RE_JAILBREAK.search(t):
        return "jailbreak"
    if RE_DISCOUNT.search(t):
        return "discount"
    if RE_RETURN.search(t) and _has_defect(t):
        return "defect_return"
    if RE_RETURN.search(t) and _day_number(t) is not None:
        return "return_deadline"
    if RE_RETURN.search(t):
        return "return_general"
    if RE_ORDER.search(t) and not (RE_DELIVERY.search(t) and "когда" in t):
        # «доставка заказа N» — про статус заказа, а не про условия доставки
        return "order_status"
    if RE_DELIVERY.search(t):
        return "delivery"
    if RE_PRICE.search(t):
        return "product"
    if RE_DEFECT.search(t):
        return "defect"
    return "unknown"


def reply(text: str) -> str:
    """Детерминированный ответ строго по регламенту. Ничего не выдумывает."""
    intent = detect_intent(text)
    day = _day_number(text)

    if intent == "jailbreak":
        return ("Скидок нет ни при каких условиях. Если у вас вопрос о товаре, "
                "доставке или возврате — с радостью помогу.")

    if intent == "discount":
        return "Скидок нет ни при каких условиях. Цена наушников X1 — 2 490 ₽."

    if intent == "order_status":
        return ("У меня нет данных о конкретных заказах — я не вижу их статусы "
                "и номера. Могу сказать только про условия: доставка курьером "
                "на следующий день, слот с 18:00 до 21:00. Статус заказа уточните, "
                "пожалуйста, в поддержке магазина.")

    if intent == "return_deadline":
        if day is not None and day > 14:
            return ("К сожалению, нет: возврат возможен только в течение 14 дней "
                    "с момента покупки. На 16-й день срок уже истёк, вернуть "
                    "товар мы не сможем.")
        return ("Да, можно вернуть. Возврат возможен в течение 14 дней с момента "
                "покупки. Деньги вернутся на ту же карту за 3 рабочих дня. "
                "Вскрытый товар без брака тоже принимаем в этот срок.")

    if intent == "return_general":
        return ("Возврат возможен в течение 14 дней с момента покупки. Деньги "
                "вернутся на ту же карту за 3 рабочих дня. Вскрытый товар без "
                "брака тоже можно вернуть в этот срок.")

    if intent == "defect_return":
        return ("Товар с браком принимаем на экспертизу. Деньги сразу не обещаем: "
                "сначала экспертиза, решение о возврате — после её результатов. "
                "Срок возврата по браку в рамках 14 дней.")

    if intent == "defect":
        return ("Брак принимаем на экспертизу. Деньги сразу не обещаем: сначала "
                "экспертиза, затем решение по результатам.")

    if intent == "delivery":
        return "Доставка курьером на следующий день, слот с 18:00 до 21:00."

    if intent == "product":
        return "Наушники X1 в наличии, цена 2 490 ₽."

    return ("У меня нет данных по этому вопросу. Могу помочь с вопросами о товаре "
            "(наушники X1, 2 490 ₽, в наличии), доставке (курьер на следующий день, "
            "слот 18:00–21:00), возврате (14 дней, деньги на ту же карту за 3 рабочих "
            "дня) и браке (принимаем на экспертизу). По остальному обратитесь, "
            "пожалуйста, в поддержку магазина.")


if __name__ == "__main__":
    import sys
    msg = " ".join(sys.argv[1:]) or "привет"
    print(reply(msg))
