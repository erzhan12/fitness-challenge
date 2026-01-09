#!/usr/bin/env python3
"""Migrate data from Supabase to Django ORM (SQLite).

Usage:
    uv run python scripts/migrate_data.py

Options:
    uv run python scripts/migrate_data.py --batch-size 2000
    uv run python scripts/migrate_data.py --skip-logs
    uv run python scripts/migrate_data.py --no-verify

Prerequisites:
    - `.env` contains `SUPABASE_URL` and `SUPABASE_KEY`
    - Django migrations applied (`uv run python manage.py migrate`)
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "python-dotenv is required to load `.env` (dependency: python-dotenv)."
        ) from exc

    load_dotenv(PROJECT_ROOT / ".env")


def _parse_date(value: Any) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise TypeError(f"Unsupported date value: {value!r}")


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"Unsupported datetime value: {value!r}")


@dataclass(frozen=True)
class Counts:
    supabase: int
    django: int


def _get_supabase_client():
    try:
        from supabase import create_client
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "supabase client is required (dependency: supabase)."
        ) from exc

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError(
            "Missing SUPABASE_URL/SUPABASE_KEY. Add them to `.env` or export them."
        )

    return create_client(url, key)


def _setup_django() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.core.settings")
    try:
        import django
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Django is required for ORM migration (dependency: django).") from exc

    django.setup()


def _supabase_count(sb, table_name: str) -> int:
    try:
        res = sb.table(table_name).select("id", count="exact").execute()
        if getattr(res, "count", None) is not None:
            return int(res.count)
        return len(res.data or [])
    except TypeError:
        res = sb.table(table_name).select("id").execute()
        return len(res.data or [])


def migrate_exercise_types(sb) -> int:
    from django.db import transaction
    from src.core.models import ExerciseType

    res = sb.table("exercise_types").select("*").order("id").execute()
    rows = res.data or []

    with transaction.atomic():
        for row in rows:
            ExerciseType.objects.update_or_create(
                id=row["id"],
                defaults={
                    "name": row["name"],
                    "display_name": row["display_name"],
                    "emoji": row["emoji"],
                    "unit": row.get("unit") or "reps",
                    "aliases": row.get("aliases") or [],
                    "is_active": row.get("is_active", True),
                },
            )

    return len(rows)


def migrate_challenges(sb) -> int:
    from django.db import transaction
    from src.core.models import ExerciseChallenge

    res = sb.table("exercise_challenges").select("*").order("id").execute()
    rows = res.data or []

    with transaction.atomic():
        for row in rows:
            ExerciseChallenge.objects.update_or_create(
                id=row["id"],
                defaults={
                    "exercise_type_id": row["exercise_type_id"],
                    "challenge_name": row.get("challenge_name") or "",
                    "start_date": _parse_date(row["start_date"]),
                    "end_date": _parse_date(row["end_date"]),
                    "target_total": row["target_total"],
                    "daily_target": row.get("daily_target"),
                    "is_active": row.get("is_active", True),
                    "is_default": row.get("is_default", False),
                },
            )

    return len(rows)


def migrate_logs(sb, *, batch_size: int = 1000) -> int:
    from django.db import transaction
    from src.core.models import ExerciseLog

    total = 0
    offset = 0

    while True:
        res = (
            sb.table("exercise_logs")
            .select("*")
            .order("id")
            .range(offset, offset + batch_size - 1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            break

        with transaction.atomic():
            for row in rows:
                ExerciseLog.objects.update_or_create(
                    id=row["id"],
                    defaults={
                        "exercise_type_id": row["exercise_type_id"],
                        "challenge_id": row.get("challenge_id"),
                        "date": _parse_date(row["date"]),
                        "timestamp": _parse_datetime(row["timestamp"]),
                        "count": row["count"],
                        "cumulative_total": row.get("cumulative_total"),
                        "day_number": row.get("day_number"),
                        "status": row.get("status"),
                        "raw_message": row.get("raw_message"),
                        "duration_seconds": row.get("duration_seconds"),
                        "notes": row.get("notes"),
                    },
                )

        total += len(rows)
        offset += batch_size
        if len(rows) < batch_size:
            break

        if total % (batch_size * 5) == 0:
            print(f"  ... migrated {total} logs so far")

    return total


def migrate_user_stats(sb) -> int:
    from django.db import transaction
    from src.core.models import UserStats

    res = sb.table("user_stats").select("*").order("id").execute()
    rows = res.data or []

    with transaction.atomic():
        for row in rows:
            UserStats.objects.update_or_create(
                id=row["id"],
                defaults={
                    "exercise_type_id": row["exercise_type_id"],
                    "all_time_total": row.get("all_time_total", 0),
                    "best_daily_count": row.get("best_daily_count", 0),
                    "current_streak": row.get("current_streak", 0),
                    "longest_streak": row.get("longest_streak", 0),
                    "last_logged_date": _parse_date(row.get("last_logged_date")),
                },
            )

    return len(rows)


def verify_counts(sb) -> dict[str, Counts]:
    from src.core.models import ExerciseType, ExerciseChallenge, ExerciseLog, UserStats

    tables: list[tuple[str, Any]] = [
        ("exercise_types", ExerciseType),
        ("exercise_challenges", ExerciseChallenge),
        ("exercise_logs", ExerciseLog),
        ("user_stats", UserStats),
    ]

    results: dict[str, Counts] = {}
    for table_name, model in tables:
        results[table_name] = Counts(
            supabase=_supabase_count(sb, table_name),
            django=model.objects.count(),
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=1000)
    parser.add_argument("--skip-logs", action="store_true")
    parser.add_argument("--no-verify", action="store_true")
    args = parser.parse_args()

    _load_env()
    _setup_django()

    sb = _get_supabase_client()

    print("Starting migration from Supabase to Django ORM (SQLite)...")
    print(f"SQLite database: {PROJECT_ROOT / 'data' / 'db.sqlite3'}")
    print()

    print("Migrating exercise_types...")
    types_count = migrate_exercise_types(sb)
    print(f"  Migrated {types_count} exercise types")

    print("Migrating exercise_challenges...")
    challenges_count = migrate_challenges(sb)
    print(f"  Migrated {challenges_count} challenges")

    if args.skip_logs:
        print("Skipping exercise_logs (requested).")
        logs_count = 0
    else:
        print("Migrating exercise_logs...")
        logs_count = migrate_logs(sb, batch_size=args.batch_size)
        print(f"  Migrated {logs_count} logs")

    print("Migrating user_stats...")
    stats_count = migrate_user_stats(sb)
    print(f"  Migrated {stats_count} user stats")

    if not args.no_verify:
        print("\nVerifying record counts:")
        results = verify_counts(sb)
        all_match = True
        for table, counts in results.items():
            status = "OK" if counts.supabase == counts.django else "MISMATCH"
            if status != "OK":
                all_match = False
            print(
                f"  {table}: Supabase={counts.supabase}, SQLite={counts.django} [{status}]"
            )

        if all_match:
            print("\nMigration complete! All record counts match.")
        else:
            print("\nMigration complete with warnings. Please verify data manually.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

