import json

from core.responses import FailureResponse, SuccessResponse


def _json(response):
    return json.loads(response.body)


def test_success_response_uses_three_field_contract():
    payload = _json(SuccessResponse(data={"value": 1}))
    assert payload == {
        "code": "000000",
        "message": payload["message"],
        "data": {"value": 1},
    }


def test_failure_response_uses_non_success_code():
    payload = _json(FailureResponse(message="failed"))
    assert payload == {"code": "999999", "message": "failed", "data": None}


def test_total_moves_inside_data_without_adding_top_level_fields():
    payload = _json(SuccessResponse(data=[{"id": 1}], total=3))
    assert payload == {
        "code": "000000",
        "message": payload["message"],
        "data": {"items": [{"id": 1}], "total": 3},
    }
