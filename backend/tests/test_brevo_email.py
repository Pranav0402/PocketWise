import json
import urllib.error

import pytest

from app import main as main_module


class FakeResponse:
    status = 201

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_password_reset_email_uses_brevo_api(monkeypatch):
    monkeypatch.setattr(main_module.settings, "brevo_api_key", "test-api-key")
    monkeypatch.setattr(main_module.settings, "brevo_sender_email", "verified@example.com")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)
    main_module.send_password_reset_email("student@example.com", "123456")

    request, timeout = requests[0]
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.method == "POST"
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["api-key"] == "test-api-key"
    payload = json.loads(request.data)
    assert payload["sender"] == {"email": "verified@example.com", "name": "PocketWise"}
    assert payload["to"] == [{"email": "student@example.com"}]
    assert payload["subject"] == "Your PocketWise password reset code"
    assert "123456" in payload["textContent"]
    assert timeout == 10


def test_password_reset_email_hides_provider_error_details(monkeypatch):
    monkeypatch.setattr(main_module.settings, "brevo_api_key", "test-api-key")
    monkeypatch.setattr(main_module.settings, "brevo_sender_email", "verified@example.com")

    def fake_urlopen(*args, **kwargs):
        raise urllib.error.HTTPError(
            "https://api.brevo.com/v3/smtp/email",
            401,
            "provider detail",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(main_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RuntimeError, match="^Transactional email delivery failed$") as error:
        main_module.send_password_reset_email("student@example.com", "123456")

    message = str(error.value)
    assert "test-api-key" not in message
    assert "student@example.com" not in message
    assert "123456" not in message
    assert "provider detail" not in message


def test_password_reset_email_requires_brevo_configuration(monkeypatch):
    monkeypatch.setattr(main_module.settings, "brevo_api_key", "")
    monkeypatch.setattr(main_module.settings, "brevo_sender_email", "verified@example.com")

    with pytest.raises(RuntimeError, match="^Transactional email delivery is not configured$"):
        main_module.send_password_reset_email("student@example.com", "123456")
