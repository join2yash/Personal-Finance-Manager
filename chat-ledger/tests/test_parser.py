import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.parser import parse_message


def test_simple_expense():
    p = parse_message("500 grocery")
    assert p.amount == 500.0
    assert p.category == "Food"
    assert p.direction == "expense"


def test_comma_amount():
    p = parse_message("paid rent 15,000")
    assert p.amount == 15000.0
    assert p.category == "Rent"
    assert p.direction == "expense"


def test_income_keyword():
    p = parse_message("received 2000 from client")
    assert p.amount == 2000.0
    assert p.direction == "income"


def test_salary():
    p = parse_message("salary 45000")
    assert p.amount == 45000.0
    assert p.category == "Salary"
    assert p.direction == "income"


def test_unknown_category_defaults_to_misc():
    p = parse_message("200 driver tip")
    assert p.amount == 200.0
    assert p.category == "Misc Expense"
    assert p.direction == "expense"


def test_no_amount_returns_none():
    assert parse_message("hello there") is None


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"PASS: {t.__name__}")
    print(f"\n{passed}/{len(tests)} tests passed")
