from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import storage
from src.auth import bootstrap_admin


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bootstrap a FigureLearning cloud-mode admin and invite code.")
    parser.add_argument("--email", default="admin@figurelearning.local", help="Admin email.")
    parser.add_argument("--username", default="admin", help="Admin username.")
    parser.add_argument("--password", default="", help="Admin password. A random one is generated when omitted.")
    parser.add_argument("--invite-role", default="member", choices=["member", "admin"], help="Role granted by the invite code.")
    parser.add_argument("--invite-max-uses", type=int, default=5, help="Maximum invite uses.")
    parser.add_argument("--invite-days", type=int, default=14, help="Invite validity in days. Use 0 for no expiry.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    password = args.password or secrets.token_urlsafe(12)
    storage.init_storage()
    with storage.connect() as conn:
        result = bootstrap_admin(
            conn,
            email=args.email,
            username=args.username,
            password=password,
            invite_role=args.invite_role,
            invite_max_uses=args.invite_max_uses,
            invite_days=args.invite_days,
        )

    print("Cloud auth bootstrap complete.")
    print(f"Admin email: {result['admin']['email']}")
    print(f"Admin username: {result['admin']['username']}")
    print(f"Admin password: {password}")
    print(f"Invite code: {result['invitation']['code']}")
    print(f"Invite role: {result['invitation']['role']}")
    print(f"Invite max uses: {result['invitation']['maxUses']}")
    print(f"Invite expires at: {result['invitation']['expiresAt'] or 'never'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
