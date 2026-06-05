from src.shared.errors import ApiError, error_payload
from src.shared.responses import error_response, success_payload, success_response


def test_success_payload_uses_stable_shape():
    payload = success_payload(data={"id": 1}, meta={"page": 1})

    assert payload == {
        "data": {"id": 1},
        "meta": {"page": 1},
    }


def test_success_payload_defaults_to_empty_objects():
    payload = success_payload()

    assert payload == {
        "data": {},
        "meta": {},
    }


def test_error_payload_uses_stable_shape_without_optional_details():
    error = ApiError(code="NOT_FOUND", message="Resource not found", status_code=404)

    assert error_payload(error) == {
        "error": {
            "code": "NOT_FOUND",
            "message": "Resource not found",
        }
    }


def test_error_payload_includes_details_when_present():
    error = ApiError(
        code="VALIDATION_ERROR",
        message="Invalid input",
        status_code=422,
        details={"field": "name"},
    )

    assert error_payload(error) == {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Invalid input",
            "details": {"field": "name"},
        }
    }


def test_response_helpers_preserve_status_codes():
    created = success_response(data={"id": 1}, status_code=201)
    failed = error_response(ApiError(code="CONFLICT", message="Already exists", status_code=409))

    assert created.status_code == 201
    assert failed.status_code == 409
