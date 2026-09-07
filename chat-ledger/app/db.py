"""
Database access layer.

Design rule from the build plan (§7): ALL access goes through functions here,
and every ledger-scoped function requires a user_id. Never write ad-hoc raw
queries elsewhere in the app - that's how cross-user data leaks happen.
"""

import os
import psycopg2
import psycopg2.extras
from contextlib import contextmanager

from app.parser import DEFAULT_ACCOUNTS

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/chatledger")


@contextmanager
def get_conn():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Identity resolution ─────────────────────────────────────────────────────

def get_user_id_by_platform(platform: str, platform_id: str) -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT user_id FROM user_identities WHERE platform = %s AND platform_id = %s",
            (platform, platform_id),
        )
        row = cur.fetchone()
        return row[0] if row else None


def create_user_with_identity(platform: str, platform_id: str, name: str | None = None) -> int:
    """Creates a new canonical user + identity link + seeds default accounts."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO users (name) VALUES (%s) RETURNING id", (name,))
        user_id = cur.fetchone()[0]

        cur.execute(
            "INSERT INTO user_identities (user_id, platform, platform_id) VALUES (%s, %s, %s)",
            (user_id, platform, platform_id),
        )

        for account_name, account_type in DEFAULT_ACCOUNTS:
            cur.execute(
                "INSERT INTO accounts (user_id, name, type) VALUES (%s, %s, %s)",
                (user_id, account_name, account_type),
            )

    return user_id


def get_or_create_user(platform: str, platform_id: str) -> int:
    user_id = get_user_id_by_platform(platform, platform_id)
    if user_id is not None:
        return user_id
    return create_user_with_identity(platform, platform_id)


# ── Accounts ─────────────────────────────────────────────────────────────────

def get_or_create_account(user_id: int, name: str, account_type: str) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM accounts WHERE user_id = %s AND name = %s",
            (user_id, name),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            "INSERT INTO accounts (user_id, name, type) VALUES (%s, %s, %s) RETURNING id",
            (user_id, name, account_type),
        )
        return cur.fetchone()[0]


def get_balance(user_id: int, account_name: str) -> float:
    """Balance = sum(dr) - sum(cr) for asset/expense; sum(cr) - sum(dr) for income/liability."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.type, COALESCE(SUM(el.dr_amt), 0), COALESCE(SUM(el.cr_amt), 0)
            FROM accounts a
            LEFT JOIN entry_lines el ON el.account_id = a.id AND el.user_id = a.user_id
            WHERE a.user_id = %s AND a.name = %s
            GROUP BY a.type
            """,
            (user_id, account_name),
        )
        row = cur.fetchone()
        if not row:
            return 0.0
        acc_type, dr_total, cr_total = row
        if acc_type in ("asset", "expense"):
            return float(dr_total) - float(cr_total)
        return float(cr_total) - float(dr_total)


# ── Journal entries ──────────────────────────────────────────────────────────

def create_journal_entry(
    user_id: int,
    narration: str,
    raw_message: str,
    source_platform: str,
    lines: list[tuple[int, float, float]],  # (account_id, dr_amt, cr_amt)
) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO journal_entries (user_id, narration, raw_message, source_platform)
            VALUES (%s, %s, %s, %s) RETURNING id
            """,
            (user_id, narration, raw_message, source_platform),
        )
        entry_id = cur.fetchone()[0]

        for account_id, dr_amt, cr_amt in lines:
            cur.execute(
                """
                INSERT INTO entry_lines (user_id, entry_id, account_id, dr_amt, cr_amt)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (user_id, entry_id, account_id, dr_amt, cr_amt),
            )

    return entry_id


def get_last_entry_id(user_id: int) -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM journal_entries WHERE user_id = %s ORDER BY entry_date DESC LIMIT 1",
            (user_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def delete_entry(user_id: int, entry_id: int) -> None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "DELETE FROM entry_lines WHERE user_id = %s AND entry_id = %s", (user_id, entry_id)
        )
        cur.execute(
            "DELETE FROM journal_entries WHERE user_id = %s AND id = %s", (user_id, entry_id)
        )
