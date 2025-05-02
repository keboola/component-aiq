import logging
from datetime import datetime
from typing import Dict, List, Literal

import pytz
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from keboola.component.exceptions import UserException
from dateparser import parse as parse_natural_date


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

    @model_validator(mode="before")
    @classmethod
    def correct_invalid_combinations(cls, values: Dict) -> Dict:
        has_auto = values.get("contact_loyalty_points", False)
        has_manual = values.get("contact_loyalty_points_custom_ids", False)

        if has_auto and has_manual:
            logging.warning(
                "Both 'contact_loyalty_points' and 'contact_loyalty_points_custom_ids' were set to True. "
                "Defaulting to 'contact_loyalty_points_custom_ids = False'."
            )
            values["contact_loyalty_points_custom_ids"] = False

        return values

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
    date_from: str = Field(default="1 month ago")  # natural language or "last"
    date_to: str = Field(default="now")

    def _parse_natural_date(self, input_str: str) -> datetime:
        date_obj = parse_natural_date(input_str, settings={"TIMEZONE": "UTC"})
        if date_obj is None:
            raise UserException(f"Invalid date string: '{input_str}'")
        return date_obj.replace(tzinfo=pytz.UTC)

    def resolved_date_from(self, state: Dict[str, str]) -> datetime:
        input_value = self.date_from.strip().lower()

        if input_value in {"last", "lastrun", "last_run", "last run"}:
            last_run = state.get("last_successful_run")
            if not last_run:
                raise UserException(
                    "You used 'last run' as date_from, but no previous run state was found."
                )
            return self._parse_natural_date(last_run)

        return self._parse_natural_date(input_value)

    def resolved_date_to(self) -> datetime:
        return self._parse_natural_date(self.date_to.strip().lower())

    def date_range_unix(self, state: Dict[str, str]) -> tuple[int, int]:
        """
        Returns the (from, to) timestamps as UNIX ints in UTC.
        Also performs validation: from <= to
        """
        from_dt = self.resolved_date_from(state)
        to_dt = self.resolved_date_to()

        if from_dt > to_dt:
            raise UserException("date_from cannot be after date_to.")

        return int(from_dt.timestamp()), int(to_dt.timestamp())


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
