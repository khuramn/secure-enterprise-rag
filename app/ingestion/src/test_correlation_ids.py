import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from entra_auth import AuthenticatedUser, get_current_user


client = TestClient(app, raise_server_exceptions=False)


def valid_request_id(response):
    value = response.headers.get("X-Request-ID")
    assert value, "Missing X-Request-ID header"
    assert str(uuid.UUID(value)) == value
    return value


def test_success():
    user = AuthenticatedUser(
        user_id="security-test-user",
        tenant_id="00000000-0000-0000-0000-000000000000",
        groups=("employees",),
    )

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        with patch(
            "api.answer_question",
            return_value="Authorized answer",
        ) as mock_answer:
            response = client.post(
                "/query",
                json={"question": "What is the policy?"},
            )

        assert response.status_code == 200, response.text
        request_id = valid_request_id(response)

        assert (
            mock_answer.call_args.kwargs["request_id"]
            == request_id
        )

        print("PASS: Successful request correlation")
    finally:
        app.dependency_overrides.clear()


def test_authorization_failure():
    user = AuthenticatedUser(
        user_id="security-test-user",
        tenant_id="00000000-0000-0000-0000-000000000000",
        groups=("employees",),
    )

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        with patch(
            "api.answer_question",
            side_effect=PermissionError("Sensitive details"),
        ):
            response = client.post(
                "/query",
                json={"question": "Restricted information"},
            )

        assert response.status_code == 403
        valid_request_id(response)
        assert response.json()["detail"] == "Access denied"

        print("PASS: Authorization failure correlation")
    finally:
        app.dependency_overrides.clear()


def test_server_error():
    user = AuthenticatedUser(
        user_id="security-test-user",
        tenant_id="00000000-0000-0000-0000-000000000000",
        groups=("employees",),
    )

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        with patch(
            "api.answer_question",
            side_effect=RuntimeError("SECRET_INTERNAL_VALUE"),
        ):
            response = client.post(
                "/query",
                json={"question": "Test error"},
            )

        assert response.status_code == 500
        valid_request_id(response)
        assert "SECRET_INTERNAL_VALUE" not in response.text

        print("PASS: Server error correlation")
    finally:
        app.dependency_overrides.clear()


def test_unauthenticated():
    response = client.post(
        "/query",
        json={"question": "Test unauthenticated request"},
    )

    assert response.status_code == 401
    valid_request_id(response)

    print("PASS: Unauthenticated request correlation")


if __name__ == "__main__":
    test_success()
    test_authorization_failure()
    test_server_error()
    test_unauthenticated()

    print("\nAll correlation ID tests passed.")
