"""Pydantic models for visitor endpoints."""

from __future__ import annotations

from fastapi import Form
from pydantic import BaseModel


class VisitorRegisterForm(BaseModel):
    """Form data for the visitor register endpoint."""

    name: str
    phone: str = ""
    host: str = ""
    purpose: str = ""
    visitor_type: str = ""

    @classmethod
    def as_form(
        cls,
        name: str = Form(...),
        phone: str = Form(""),
        host: str = Form(""),
        purpose: str = Form(""),
        visitor_type: str = Form(""),
    ) -> "VisitorRegisterForm":
        return cls(
            name=name,
            phone=phone,
            host=host,
            purpose=purpose,
            visitor_type=visitor_type,
        )
