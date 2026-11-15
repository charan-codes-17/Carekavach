import json
from unittest.mock import MagicMock, patch

import pytest

from app.repositories.firestore import FirestoreRepository


def test_firestore_without_credentials_json_uses_adc() -> None:
    """When FIREBASE_CREDENTIALS_JSON is empty, fall back to default AsyncClient."""
    mock_client = MagicMock()
    with patch("google.cloud.firestore.AsyncClient", return_value=mock_client) as mock_async_client:
        repo = FirestoreRepository(project_id="my-gcp-project", credentials_json="")
        client = repo._get_client()

        assert client == mock_client
        mock_async_client.assert_called_once_with(project="my-gcp-project")


def test_firestore_with_valid_credentials_json() -> None:
    """When FIREBASE_CREDENTIALS_JSON is valid JSON, construct credentials and client."""
    cred_dict = {
        "type": "service_account",
        "project_id": "service-account-proj",
        "private_key_id": "key123",
        "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgk...\n",
        "client_email": "sa@service-account-proj.iam.gserviceaccount.com",
    }
    raw_json = json.dumps(cred_dict)

    mock_client = MagicMock()
    mock_creds = MagicMock()

    with (
        patch("google.cloud.firestore.AsyncClient", return_value=mock_client) as mock_async_client,
        patch(
            "google.oauth2.service_account.Credentials.from_service_account_info",
            return_value=mock_creds,
        ) as mock_from_info,
    ):
        repo = FirestoreRepository(project_id="fallback-proj", credentials_json=raw_json)
        client = repo._get_client()

        assert client == mock_client
        mock_from_info.assert_called_once_with(cred_dict)
        mock_async_client.assert_called_once_with(
            project="service-account-proj", credentials=mock_creds
        )


def test_firestore_invalid_json_raises_clean_error_without_secret() -> None:
    """Invalid JSON must raise a ValueError without echoing the secret content."""
    super_secret = "ULTRA_SENSITIVE_SECRET_TOKEN_9999"
    bad_json = f'{{"private_key": "{super_secret}", INVALID_SYNTAX'

    repo = FirestoreRepository(project_id="test-proj", credentials_json=bad_json)

    with pytest.raises(ValueError) as exc_info:
        repo._get_client()

    error_message = str(exc_info.value)
    assert "Failed to parse FIREBASE_CREDENTIALS_JSON as valid JSON" in error_message
    assert super_secret not in error_message


def test_firestore_non_dict_json_raises_clean_error() -> None:
    """JSON that is not a dictionary/object must raise a clear ValueError."""
    non_dict_json = "[1, 2, 3, 4]"
    repo = FirestoreRepository(project_id="test-proj", credentials_json=non_dict_json)

    with pytest.raises(ValueError) as exc_info:
        repo._get_client()

    assert "must be a JSON object" in str(exc_info.value)


def test_firestore_service_account_construction_failure_hides_secret() -> None:
    """Failure inside from_service_account_info must not expose secret in exception."""
    super_secret = "KEY_NEVER_TO_BE_LOGGED_OR_LEAKED"
    cred_dict = {"project_id": "proj", "private_key": super_secret}
    raw_json = json.dumps(cred_dict)

    with patch(
        "google.oauth2.service_account.Credentials.from_service_account_info",
        side_effect=Exception(f"internal parser exploded with {super_secret}"),
    ):
        repo = FirestoreRepository(project_id="test-proj", credentials_json=raw_json)

        with pytest.raises(ValueError) as exc_info:
            repo._get_client()

        error_message = str(exc_info.value)
        assert "Failed to construct credentials from FIREBASE_CREDENTIALS_JSON" in error_message
        assert super_secret not in error_message
