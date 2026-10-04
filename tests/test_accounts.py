"""Konten, Passwörter, gespeicherte Entwürfe, Support-Anfragen und Testphase."""

import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

import logic


def set_created_at(database, user_id, created_at):
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE users SET created_at = ? WHERE id = ?", (created_at, user_id))


class TestPasswords:
    def test_hash_is_salted_and_never_plaintext(self):
        first = logic.hash_password("geheimes-passwort")
        second = logic.hash_password("geheimes-passwort")
        assert first != second
        assert "geheimes-passwort" not in first
        salt, digest = first.split(":")
        assert len(bytes.fromhex(salt)) == 16 and len(bytes.fromhex(digest)) == 64

    def test_matching_and_wrong_password(self):
        stored = logic.hash_password("richtig-123")
        assert logic.password_matches("richtig-123", stored)
        assert not logic.password_matches("falsch-123", stored)

    @pytest.mark.parametrize("stored", ["", "kein-trenner", "zz:zz", None])
    def test_malformed_hash_is_rejected_without_error(self, stored):
        assert logic.password_matches("egal", stored) is False


class TestRegistrationAndLogin:
    def test_register_normalizes_email_and_allows_login(self):
        logic.register_user("  Kunde@Example.COM ", "sicheres-passwort")
        user = logic.authenticate_user("kunde@example.com", "sicheres-passwort")
        assert user is not None and user[1] == "kunde@example.com"
        assert logic.authenticate_user("KUNDE@example.com ", "sicheres-passwort") == user

    @pytest.mark.parametrize("email", ["", "ohne-at", "a@b", "leer @example.com"])
    def test_invalid_email_is_rejected(self, email):
        with pytest.raises(ValueError, match="E-Mail"):
            logic.register_user(email, "sicheres-passwort")

    def test_short_password_is_rejected(self):
        with pytest.raises(ValueError, match="8 Zeichen"):
            logic.register_user("kunde@example.com", "kurz")

    def test_duplicate_account_is_rejected(self):
        logic.register_user("kunde@example.com", "sicheres-passwort")
        with pytest.raises(ValueError, match="existiert bereits"):
            logic.register_user("KUNDE@example.com", "anderes-passwort")

    def test_wrong_password_and_unknown_user(self):
        logic.register_user("kunde@example.com", "sicheres-passwort")
        assert logic.authenticate_user("kunde@example.com", "falsches-passwort") is None
        assert logic.authenticate_user("niemand@example.com", "sicheres-passwort") is None


class TestSavedWebsites:
    def test_save_list_load_and_delete_own_website(self, user_id, session):
        logic.save_website(user_id, "  ", "<html>1</html>", "firma.de", "site-1")
        logic.save_website(user_id, "Zweite", "<html>2</html>", "", session.analytics_site_id)
        websites = logic.get_websites(user_id)
        assert [name for _, name, _ in websites] == ["Zweite", "Meine Website"]
        newest_id = websites[0][0]
        assert logic.load_website(user_id, newest_id) == ("Zweite", "<html>2</html>", "", session.analytics_site_id)
        logic.delete_saved_website(user_id, newest_id)
        assert [name for _, name, _ in logic.get_websites(user_id)] == ["Meine Website"]

    def test_other_users_cannot_read_or_delete(self, user_id):
        logic.register_user("fremd@example.com", "sicheres-passwort")
        stranger = logic.authenticate_user("fremd@example.com", "sicheres-passwort")[0]
        logic.save_website(user_id, "Privat", "<html></html>", "", "site-1")
        website_id = logic.get_websites(user_id)[0][0]
        assert logic.load_website(stranger, website_id) is None
        logic.delete_saved_website(stranger, website_id)
        assert logic.load_website(user_id, website_id) is not None


class TestSupportRequests:
    def test_user_sees_own_requests_and_admin_sees_all(self, user_id):
        logic.register_user("zweiter@example.com", "sicheres-passwort")
        other = logic.authenticate_user("zweiter@example.com", "sicheres-passwort")[0]
        logic.save_support_request(user_id, "Fehler", "Vorschau", "  Betreff ", " Text ", " Schritte ")
        logic.save_support_request(other, "Frage", "Konto", "Andere", "Text", "")
        own = logic.get_support_requests(user_id)
        assert len(own) == 1 and own[0][3:6] == ("Betreff", "Text", "Schritte")
        inbox = logic.get_support_requests()
        assert {row[1] for row in inbox} == {"kunde@example.com", "zweiter@example.com"}


class TestTrialAndPremium:
    def test_new_user_has_active_trial(self, user_id):
        status = logic.get_user_status(user_id)
        assert status["trial_active"] and not status["subscribed"]
        assert 23 <= status["trial_remaining_hours"] <= 24
        assert status["balance"] == 5.0
        assert logic.has_generation_access(user_id)

    def test_expired_trial_blocks_generation(self, user_id, database):
        set_created_at(database, user_id, (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat())
        status = logic.get_user_status(user_id)
        assert not status["trial_active"] and status["trial_remaining_hours"] == 0
        assert not logic.has_generation_access(user_id)

    def test_premium_always_has_access(self, user_id, database):
        set_created_at(database, user_id, "2000-01-01T00:00:00+00:00")
        logic.activate_premium(user_id)
        assert logic.get_user_status(user_id)["subscribed"]
        assert logic.has_generation_access(user_id)

    def test_unknown_user_and_broken_date(self, user_id, database):
        assert logic.get_user_status(999)["trial_active"] is False
        assert logic.has_generation_access(999) is False
        set_created_at(database, user_id, "kein-datum")
        assert logic.get_user_status(user_id)["trial_active"] is False
        assert logic.has_generation_access(user_id) is False


class TestDatabaseSetup:
    def test_initialization_is_idempotent(self, database):
        logic.initialize_database()
        logic.initialize_database()
        with sqlite3.connect(database) as connection:
            tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"users", "websites", "support_requests"} <= tables

    def test_migrates_old_schema(self, monkeypatch, tmp_path):
        old_database = tmp_path / "alt.db"
        with sqlite3.connect(old_database) as connection:
            connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, token_balance REAL DEFAULT 5.00, is_subscribed INTEGER DEFAULT 0)")
            connection.execute("INSERT INTO users (email, password_hash) VALUES ('alt@example.com', 'x')")
            connection.execute("CREATE TABLE websites (id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, site_name TEXT NOT NULL, html_content TEXT NOT NULL, domain TEXT)")
        monkeypatch.setattr(logic, "DATABASE_PATH", old_database)
        logic.initialize_database()
        with sqlite3.connect(old_database) as connection:
            assert connection.execute("SELECT created_at FROM users").fetchone()[0]
            columns = {row[1] for row in connection.execute("PRAGMA table_info(websites)")}
        assert "analytics_site_id" in columns
