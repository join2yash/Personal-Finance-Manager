"""
Phase 1 parser: regex + keyword dictionary (no AI dependency, per build plan §4/§5).

Turns free text like "500 grocery" or "received 2000 from client" into a
structured ParsedMessage the rest of the app can post as a balanced entry.
"""

import re
from dataclasses import dataclass

# Default chart of accounts seeded for every new user.
DEFAULT_ACCOUNTS = [
    ("Cash", "asset"),
    ("Bank", "asset"),
    ("Food", "expense"),
    ("Transport", "expense"),
    ("Rent", "expense"),
    ("Shopping", "expense"),
    ("Utilities", "expense"),
    ("Misc Expense", "expense"),
    ("Salary", "income"),
    ("Other Income", "income"),
]

# Keyword -> account name. Extend this over time (Phase 2: make it learnable).
KEYWORD_MAP = {
    "grocery": "Food", "groceries": "Food", "food": "Food", "lunch": "Food",
    "dinner": "Food", "breakfast": "Food", "zomato": "Food", "swiggy": "Food",
    "restaurant": "Food", "milk": "Food", "snacks": "Food",

    "uber": "Transport", "ola": "Transport", "cab": "Transport", "taxi": "Transport",
    "bus": "Transport", "metro": "Transport", "fuel": "Transport", "petrol": "Transport",
    "diesel": "Transport",

    "rent": "Rent",

    "amazon": "Shopping", "flipkart": "Shopping", "shopping": "Shopping",
    "clothes": "Shopping",

    "electricity": "Utilities", "wifi": "Utilities", "internet": "Utilities",
    "recharge": "Utilities", "bill": "Utilities", "water bill": "Utilities",

    "salary": "Salary",
    "refund": "Other Income", "received": "Other Income", "bonus": "Other Income",
}

# Presence of any of these words flips the entry to "income" direction.
INCOME_KEYWORDS = {"received", "got", "salary", "income", "refund", "credited", "bonus"}

# Matches an amount: 500, 1,200.50, 1200
AMOUNT_RE = re.compile(r"(\d[\d,]*\.?\d*)")


@dataclass
class ParsedMessage:
    amount: float
    category: str          # account name on the non-cash side
    direction: str          # "expense" or "income"
    narration: str          # cleaned-up description
    raw_message: str


def parse_message(text: str) -> ParsedMessage | None:
    """Returns None if no amount could be found (i.e. not a loggable entry)."""
    match = AMOUNT_RE.search(text)
    if not match:
        return None

    amount = float(match.group(1).replace(",", ""))
    remainder = text[:match.start()] + text[match.end():]
    words = re.findall(r"[a-zA-Z]+", remainder.lower())

    category = "Misc Expense"
    for word in words:
        if word in KEYWORD_MAP:
            category = KEYWORD_MAP[word]
            break

    direction = "income" if any(w in INCOME_KEYWORDS for w in words) else "expense"
    # If keyword matched an income-type account, force direction to income
    if category in ("Salary", "Other Income"):
        direction = "income"

    narration = remainder.strip() or category

    return ParsedMessage(
        amount=amount,
        category=category,
        direction=direction,
        narration=narration,
        raw_message=text,
    )
