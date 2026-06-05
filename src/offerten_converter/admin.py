"""Admin CLI for managing application users.

There is no public sign-up; accounts are created here by an operator.

Usage (PYTHONPATH=src):
    python -m offerten_converter.admin create-user --email a@b.ch --name "Anna"
    python -m offerten_converter.admin list-users
"""

from __future__ import annotations

import argparse
import secrets
import sys

from sqlalchemy.exc import IntegrityError

# Emit UTF-8 so German output does not crash on a Windows cp1252 console.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover - older/odd stdio
    pass

from offerten_converter.application.auth import AuthService
from offerten_converter.infrastructure.db.engine import SessionLocal, init_db
from offerten_converter.infrastructure.security import BcryptPasswordHasher
from offerten_converter.infrastructure.sql_user_repo import SqlUserRepository


def _create_user(args: argparse.Namespace) -> int:
    generated = False
    password = args.password
    if not password:
        # Operator did not pick one: generate a temporary password to hand over.
        password = secrets.token_urlsafe(9)
        generated = True

    # Accounts created for someone else get a temp password the user must change
    # on first login. --no-force-change skips this (e.g. your own account).
    must_change = not args.no_force_change

    init_db()
    session = SessionLocal()
    try:
        service = AuthService(SqlUserRepository(session), BcryptPasswordHasher())
        try:
            user = service.create_user(
                args.email, args.name, password, must_change_password=must_change
            )
        except IntegrityError:
            session.rollback()
            print(f"Fehler: E-Mail '{args.email}' existiert bereits.", file=sys.stderr)
            return 1
        print(f"Benutzer angelegt: #{user.id}  {user.email}  ({user.name})")
        if generated:
            print(f"  Temporäres Passwort: {password}")
        if must_change:
            print("  -> muss beim ersten Login geaendert werden.")
        return 0
    finally:
        session.close()


def _list_users(_args: argparse.Namespace) -> int:
    init_db()
    session = SessionLocal()
    try:
        users = SqlUserRepository(session).list_users()
        if not users:
            print("Keine Benutzer vorhanden.")
            return 0
        for u in users:
            status = "aktiv" if u.is_active else "inaktiv"
            pw = ", muss PW ändern" if u.must_change_password else ""
            print(f"#{u.id}  {u.email}  ({u.name})  [{status}{pw}]")
        return 0
    finally:
        session.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="offerten_converter.admin")
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create-user", help="Create a new user")
    p_create.add_argument("--email", required=True)
    p_create.add_argument("--name", required=True)
    p_create.add_argument(
        "--password",
        help="Password (omit to auto-generate a temporary one)",
    )
    p_create.add_argument(
        "--no-force-change",
        action="store_true",
        help="Do not require a password change on first login (e.g. your own account)",
    )
    p_create.set_defaults(func=_create_user)

    p_list = sub.add_parser("list-users", help="List all users")
    p_list.set_defaults(func=_list_users)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
