"""
CLI script for creating an admin user.

Usage:
    # Interactive mode
    python -m app.db.create_admin

    # Non-interactive mode
    python -m app.db.create_admin --email admin@example.com --password secret123 --name "John Doe" --role admin
"""

import argparse
import asyncio
import getpass
import sys

import bcrypt
import structlog
from sqlalchemy import select

from app.db.session import async_session_factory
from app.logging_config import setup_logging
from app.models.user import AdminUser, UserRole

setup_logging()
logger = structlog.get_logger(__name__)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an admin user")
    parser.add_argument("--email", help="User email")
    parser.add_argument("--password", help="User password (omit to prompt securely)")
    parser.add_argument("--name", help="Full name")
    parser.add_argument(
        "--role",
        choices=["admin", "manager"],
        default="admin",
        help="User role (default: admin)",
    )
    return parser.parse_args()


def prompt_input(args: argparse.Namespace) -> tuple[str, str, str, UserRole]:
    email = args.email or input("Email: ").strip()
    if not email:
        print("Error: email is required", file=sys.stderr)
        sys.exit(1)

    if args.password:
        password = args.password
    else:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Error: passwords do not match", file=sys.stderr)
            sys.exit(1)

    if not password:
        print("Error: password is required", file=sys.stderr)
        sys.exit(1)

    full_name = args.name or input("Full name: ").strip() or email.split("@")[0]
    role = UserRole(args.role)

    return email, password, full_name, role


async def create_admin(email: str, password: str, full_name: str, role: UserRole) -> None:
    async with async_session_factory() as session:
        async with session.begin():
            result = await session.execute(
                select(AdminUser).where(AdminUser.email == email)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                print(f"Error: user '{email}' already exists", file=sys.stderr)
                sys.exit(1)

            user = AdminUser(
                email=email,
                password_hash=hash_password(password),
                full_name=full_name,
                role=role,
                is_active=True,
            )
            session.add(user)

    print(f"Created {role.value} user: {email} ({full_name})")


async def main() -> None:
    args = parse_args()
    email, password, full_name, role = prompt_input(args)
    await create_admin(email, password, full_name, role)


if __name__ == "__main__":
    asyncio.run(main())
