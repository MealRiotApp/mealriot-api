import uuid


def make_jwt_payload(email: str, supabase_id: str | None = None) -> dict:
    """Helper to build a fake Supabase JWT payload for tests."""
    return {
        "sub": supabase_id or str(uuid.uuid4()),
        "email": email,
        "user_metadata": {"full_name": "Test User", "avatar_url": None},
    }

# DB fixtures (db, client) will be added in Task 2 once database.py exists
