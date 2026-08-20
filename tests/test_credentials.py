import os

import pytest

from file_cleaner.credentials import CredentialError, get_api_key


class MissingKeychain:
    returncode = 1
    stdout = ""


@pytest.fixture(autouse=True)
def no_keychain(monkeypatch):
    monkeypatch.setattr(
        "file_cleaner.credentials.subprocess.run", lambda *args, **kwargs: MissingKeychain()
    )


def test_legacy_env_requires_private_permissions(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=secret-value\n")
    os.chmod(path, 0o644)

    with pytest.raises(CredentialError) as error:
        get_api_key(legacy_env=path)

    assert "chmod 600" in str(error.value)
    assert "secret-value" not in str(error.value)


def test_private_legacy_env_is_read_without_exposing_value(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    path = tmp_path / ".env"
    path.write_text("OPENAI_API_KEY=secret-value\n")
    os.chmod(path, 0o600)

    value, source = get_api_key(legacy_env=path)

    assert value == "secret-value"
    assert "secret-value" not in source
