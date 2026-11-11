"""Creates (or promotes) an administrator account. Works in production; no default password exists.
    cd backend && ADMIN_EMAIL=you@company.in python ../scripts/create_admin.py     # prompts for the password
"""
import getpass, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.security import hash_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.enums import UserRoleType  # noqa: E402
from app.models.user import User, UserRole  # noqa: E402

email = (os.environ.get("ADMIN_EMAIL") or input("Admin email: ")).strip().lower()
with SessionLocal() as db:
    user = db.query(User).filter(User.email == email).first()
    if not user:
        pw = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("New password (min 12 chars): ")
        if len(pw) < 12:
            raise SystemExit("Password must be at least 12 characters.")
        user = User(email=email, hashed_password=hash_password(pw), full_name=input("Full name: ").strip() or "Administrator", is_active=True, is_verified=True)
        db.add(user); db.flush()
    if not any(r.role_name == UserRoleType.ADMIN.value for r in user.roles):
        db.add(UserRole(user_id=user.id, role_name=UserRoleType.ADMIN.value))
    db.commit()
    print(f"{email} is now an administrator.")
