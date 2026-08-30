import os
import sys

sys.path.insert(0, "backend")

from app.services import ai_client, db_manager


def test_gemini_not_configured_returns_none_gracefully():
    # No GEMINI_API_KEY set in the test environment -- every AI helper
    # must return None (never raise) so callers can fall back cleanly.
    assert ai_client.is_gemini_configured() is False
    assert ai_client.gemini_forecast_explanation("Test PHC", "Paracetamol", [1, 2, 3], 10, 2.0, 5.0) is None
    assert ai_client.gemini_redistribution_reasoning("A", "B", "Paracetamol", 10, 5.0, 3.0) is None
    assert ai_client.gemini_district_briefing("Test PHC", "Nashik", 50.0, 1, ["Paracetamol"]) is None


def test_db_manager_round_trips_state(tmp_path):
    db_path = str(tmp_path / "test.db")
    old_path = db_manager.DATABASE_PATH
    db_manager.DATABASE_PATH = db_path
    try:
        db_manager.init_db()
        assert db_manager.load_state() is None
        phcs = [{"id": "phc-test", "name": "Test PHC", "inventory": []}]
        assert db_manager.save_state("2026-01-01", 3, phcs) is True
        restored = db_manager.load_state()
        assert restored is not None
        day, tick, restored_phcs = restored
        assert day == "2026-01-01"
        assert tick == 3
        assert restored_phcs[0]["id"] == "phc-test"
    finally:
        db_manager.DATABASE_PATH = old_path


def test_db_manager_load_state_missing_file_returns_none(tmp_path):
    db_path = str(tmp_path / "does_not_exist.db")
    old_path = db_manager.DATABASE_PATH
    db_manager.DATABASE_PATH = db_path
    try:
        # No init_db() called -- table doesn't exist yet, must not raise.
        assert db_manager.load_state() is None
    finally:
        db_manager.DATABASE_PATH = old_path
