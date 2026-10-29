from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from entra_auth import AuthenticatedUser, get_current_user


def test_internal_error_is_not_disclosed():
    def fake_user():
        return AuthenticatedUser(
            user_id="security-test-user",
            groups=("employees",),
            tenant_id="b9f3e6d3-fa51-4e7c-8c00-0fc7b7e67622",
        )

    app.dependency_overrides[get_current_user] = fake_user

    try:
        with patch(
            "api.answer_question",
            side_effect=RuntimeError(
                "SECRET_INTERNAL_DATABASE_CONNECTION_STRING"
            ),
        ):
            with TestClient(
                app,
                raise_server_exceptions=False,
            ) as client:
                response = client.post(
                    "/query",
                    json={"question": "Test error handling"},
                )

        assert response.status_code == 500, (
            f"Expected 500, received {response.status_code}"
        )

        assert (
            "SECRET_INTERNAL_DATABASE_CONNECTION_STRING"
            not in response.text
        ), "SECURITY FAILURE: Internal error leaked"

        print("PASS: Internal exception details not disclosed")

    finally:
        app.dependency_overrides.clear()
def test_authorization_error_is_not_disclosed():
    def fake_user():
        return AuthenticatedUser(
            user_id="security-test-user",
            groups=("employees",),
            tenant_id="b9f3e6d3-fa51-4e7c-8c00-0fc7b7e67622",
        )

    app.dependency_overrides[get_current_user] = fake_user

    try:
        with patch(
            "api.answer_question",
            side_effect=PermissionError(
                "Sensitive internal authorization details"
            ),
        ):
            with TestClient(app) as client:
                response = client.post(
                    "/query",
                    json={"question": "Test authorization"},
                )

        assert response.status_code == 403
        assert response.json() == {"detail": "Access denied"}

        print("PASS: Authorization error safely returned as HTTP 403")

    finally:
        app.dependency_overrides.clear()

if __name__ == "__main__":
    test_internal_error_is_not_disclosed()
    test_authorization_error_is_not_disclosed()

    print("\nAll API error-handling tests passed.")