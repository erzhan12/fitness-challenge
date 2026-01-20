#!/usr/bin/env python
"""
Script to update exercise_logs user_id from 1 to 2.
Run this on the production server.

Usage:
    python scripts/update_exercise_logs_user.py
"""

import sqlite3
import os

# Adjust this path for your production environment
DB_PATH = os.environ.get('DB_PATH', 'data/fitness.db')


def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        print("Set DB_PATH environment variable to the correct path")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Check current state
    cursor.execute("SELECT COUNT(*) FROM core_exerciselog WHERE user_id = 1")
    count_before = cursor.fetchone()[0]
    print(f"Records with user_id = 1: {count_before}")

    if count_before == 0:
        print("No records to update. Exiting.")
        conn.close()
        return

    # Perform update
    cursor.execute("UPDATE core_exerciselog SET user_id = 2 WHERE user_id = 1")
    rows_affected = cursor.rowcount
    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM core_exerciselog WHERE user_id = 2")
    count_after = cursor.fetchone()[0]

    print(f"Updated {rows_affected} records")
    print(f"Records with user_id = 2 now: {count_after}")

    conn.close()
    print("Done!")


if __name__ == '__main__':
    main()
