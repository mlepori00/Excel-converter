"""Admin CLI for managing application users.

There is no public sign-up; accounts are created here by an operator.

Usage (PYTHONPATH=src):
    python -m offerten_converter.admin create-user --email a@b.ch --name "Anna"
    python -m offerten_converter.admin list-users
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy.exc import IntegrityError

from offerten_converter.application.auth import AuthService
from offerten_converter.infrastructure.db.engine import SessionLocal, init_db
from offerten_converter.infrastructure.security import BcryptPasswordHasher
from offerten_converter.infrastructure.sql_user_repo import SqlUserRepository


def _create_user(args: argparse.Namespace) -> int:
    password = args.password or getpass.getpass("Passwort: ")
    if not password:
        print("Abbruch: leeres Passwort.", file=sys.stderr)
        return 1

    init_db()
    session = SessionLocal()
    try:
        service = AuthService(SqlUserRepository(session), BcryptPasswordHasher())
        try:
            user = service.create_user(args.email, args.name, password)
        except IntegrityError:
            session.rollback()
            print(f"Fehler: E-Mail '{args.email}' existiert bereits.", file=sys.stderr)
            return 1
        print(f"Benutzer angelegt: #{user.id}  {user.email}  ({user.name})")
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
            print(f"#{u.id}  {u.email}  ({u.name})  [{status}]")
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
        help="Password (omit to be prompted securely)",
    )
    p_create.set_defaults(func=_create_user)

    p_list = sub.add_parser("list-users", help="List all users")
    p_list.set_defaults(func=_list_users)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
