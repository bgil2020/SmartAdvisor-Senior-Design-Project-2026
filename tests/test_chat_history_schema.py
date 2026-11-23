from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20261123_chat_history.sql"


def test_chat_history_is_user_scoped_and_bounded():
    sql = MIGRATION.read_text(encoding="utf-8").casefold()
    assert "enable row level security" in sql
    assert sql.count("auth.uid() = user_id") >= 4
    assert "interval '30 days'" in sql
    assert "offset 10" in sql
    assert ">= 50" in sql
    assert "between 1 and 4000" in sql
    assert "where expires_at <= now()" in sql
    assert "session_evidence|signature|raw_syllabus|raw_source|prompt|api_key" in sql
    assert "on delete cascade" in sql


def test_chat_history_schema_does_not_store_source_evidence_or_secrets():
    sql = MIGRATION.read_text(encoding="utf-8").casefold()
    for forbidden_column in ("session_evidence", "signature", "raw_syllabus", "api_key", "prompt"):
        assert not re.search(rf"\b{forbidden_column}\s+(?:text|jsonb|varchar)", sql)
