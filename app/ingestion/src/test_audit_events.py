import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from api import app
from entra_auth import AuthenticatedUser, get_current_user


client = TestClient(app, raise_server_exceptions=False)


def test_server_failure_audit():
    user = AuthenticatedUser(
        user_id="security-test-user",
        tenant_id="00000000-0000-0000-0000-000000000000",
        groups=("employees",),
    )

    app.dependency_overrides[get_current_user] = lambda: user

    try:
        with patch("api.audit_event") as mock_audit:
            with patch(
                "api.answer_question",
                side_effect=RuntimeError(
                    "SECRET_INTERNAL_DATABASE_PASSWORD"
                ),
            ):
                response = client.post(
                    "/query",
                    json={"question": "Test server failure"},
                )

        assert response.status_code == 500
        assert "SECRET_INTERNAL_DATABASE_PASSWORD" not in response.text

        request_id = response.headers["X-Request-ID"]
        uuid.UUID(request_id)

        failure_events = [
            call
            for call in mock_audit.call_args_list
            if call.args[0] == "api.request.failed"
        ]

        assert len(failure_events) == 1, (
            f"Expected one failure event, got {len(failure_events)}"
        )

        event = failure_events[0]

        assert event.args[1] == request_id
        assert event.args[3] == "error"
        assert event.kwargs["reason"] == "server_error"
        assert "SECRET_INTERNAL_DATABASE_PASSWORD" not in str(event)

        print("PASS: Server failure logged once without sensitive details")

    finally:
        app.dependency_overrides.clear()


def test_authentication_failure_audit():
    app.dependency_overrides.clear()

    with patch("api.audit_event") as mock_audit:
        response = client.post(
            "/query",
            json={"question": "Unauthenticated request"},
        )

    assert response.status_code == 401

    request_id = response.headers["X-Request-ID"]
    uuid.UUID(request_id)

    auth_events = [
        call
        for call in mock_audit.call_args_list
        if call.args[0] == "api.authentication.denied"
    ]

    assert len(auth_events) == 1

    event = auth_events[0]

    assert event.args[1] == request_id
    assert event.args[2] == "anonymous"
    assert event.args[3] == "denied"
    assert event.kwargs["reason"] == "authentication_failed"

    print("PASS: Authentication failure logged with correlation ID")


if __name__ == "__main__":
    test_server_failure_audit()
    test_authentication_failure_audit()

    print("\nAll audit-event security tests passed.")
