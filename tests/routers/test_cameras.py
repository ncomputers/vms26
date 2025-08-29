import json
import sys
import types

import pytest
from pydantic import BaseModel, ValidationError, model_validator

# Stub heavy dependencies before importing the module under test
sys.modules.setdefault("cv2", types.SimpleNamespace())

from routers.cameras import _validation_response
from schemas.camera import CameraCreate


def test_validation_response_empty_loc() -> None:
    """The validation helper should handle empty locations."""

    class Dummy(BaseModel):
        @model_validator(mode="after")
        def check(cls, v):
            raise ValueError("bad")

    with pytest.raises(ValidationError) as exc:
        Dummy.model_validate({})

    response = _validation_response(exc.value)
    assert response.status_code == 422
    assert json.loads(response.body) == {
        "errors": [{"field": "__root__", "message": "Value error, bad"}]
    }


def test_camera_create_name_unique_uses_context() -> None:
    """Existing camera names in the context should trigger a validation error."""

    cams = [{"name": "Cam1", "site_id": 1, "archived": False}]
    cfg = {"site_id": 1}

    with pytest.raises(ValidationError):
        CameraCreate.model_validate(
            {"name": "Cam1", "url": "rtsp://example"},
            context={"cams": cams, "cfg": cfg},
        )
