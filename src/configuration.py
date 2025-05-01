import logging
from typing import Dict, List, Literal

import pytz
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from keboola.component.exceptions import UserException
from dateparser import parse as parse_natural_date

API_BASE_URL = "https://lab.alpineiq.com/api"

class Authorization(BaseModel):
    api_key: str = Field(alias="#api_key")
    user_id: str

    @field_validator("api_key", "user_id")
    def must_not_be_empty(cls, value: str, info) -> str:
        if not value.strip():
            raise ValueError(f"Field '{info.field_name}' cannot be empty")
        return value

class Endpoints(BaseModel):
    contact_adjustments: bool = Field(
        default=False,
        description="Contact adjustments"
    ),
    contact_loyalty_points: bool = Field(
        default=False,
        description="Contact loyalty points"
    ),
    contact_loyalty_points_custom_ids: bool = Field(
        default=False,
        description="Contact loyalty points by custom ids"
    ),
    audiences: bool = Field(
        default=False,
        description="Audiences"
    ),
    discounts: bool = Field(
        default=False,
        description="Discounts"
    ),
    stores: bool = Field(
        default=False,
        description="Stores"
    ),
    campaigns: bool = Field(
        default=False,
        description="Campaigns"
    ),
    custom_contact_loyalty_points_ids: List[str] = Field(default=[])

    @model_validator(mode='after')
    def validate_dependencies(cls, model):
        if not model.contact_loyalty_points_custom_ids and model.custom_contact_loyalty_points_ids:
            raise ValueError(
                "Field 'custom_contact_loyalty_points_ids' must be empty when "
                "'contact_loyalty_points_custom_ids' is False."
            )
        return model

    @property
    def as_dict(self) -> Dict[str, bool]:
        return self.model_dump()

class SyncOptions(BaseModel):
    sync_mode: Literal["full_sync", "incremental_sync"] = Field(default="full_sync")
    date_from: str = Field(default="1 hour")
    date_to: str = Field(default="now")

    @staticmethod
    def _resolve_datetime(date_str: str, state: Dict[str, str], fallback: str) -> str:
        date_str = (date_str or fallback).strip().lower()

        if date_str in {"last", "lastrun", "last run", "last_run"}:
            last_run = state.get("last_successful_run")
            if not last_run:
                raise UserException("No previous run timestamp found in state, but 'last run' was selected.")
            return last_run

        date_obj = parse_natural_date(date_str, settings={"TIMEZONE": "UTC"})
        if date_obj is None:
            raise UserException(f"Invalid date string: '{date_str}'")

        date_obj = date_obj.replace(tzinfo=pytz.UTC)
        return date_obj.strftime("%Y-%m-%dT%H:%M:%SZ")

    def resolved_date_from(self, state: Dict[str, str], fallback: str = "1 hour") -> str:
        return self._resolve_datetime(self.date_from, state, fallback)

    def resolved_date_to(self, state: Dict[str, str], fallback: str = "now") -> str:
        return self._resolve_datetime(self.date_to, state, fallback)

    def resolved_date_range_unix(self, state: Dict[str, str]) -> Dict[str, int]:
        """Returns date_from and date_to as UNIX timestamps in UTC."""
        from_str = self.resolved_date_from(state)
        to_str = self.resolved_date_to(state)

        from_dt = parse_natural_date(from_str, settings={"TIMEZONE": "UTC"}).replace(tzinfo=pytz.UTC)
        to_dt = parse_natural_date(to_str, settings={"TIMEZONE": "UTC"}).replace(tzinfo=pytz.UTC)

        return {
            "date_from_unix": int(from_dt.timestamp()),
            "date_to_unix": int(to_dt.timestamp()),
        }

class Configuration(BaseModel):
    authorization: Authorization
    endpoints: Endpoints
    sync_options: SyncOptions
    debug: bool = False

    def __init__(self, **data):
        try:
            super().__init__(**data)
        except ValidationError as e:
            error_messages = [f"{err['loc'][0]}: {err['msg']}" for err in e.errors()]
            raise UserException(f"Validation Error: {', '.join(error_messages)}")

        if self.debug:
            logging.debug("Component will run in Debug mode")
