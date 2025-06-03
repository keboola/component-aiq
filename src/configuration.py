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
    contact_list: bool = Field(
        default=False,
        description="Contact List (PIIs)"
    )
    contact_details: bool = Field(
        default=False,
        description="Contact Details (PIIs)"
    )
    contact_details_custom_ids: bool = Field(
        default=False,
        description="Contact Details by Custom IDs (PIIs)"
    )
    contact_adjustments: bool = Field(
        default=False,
        description="Contact adjustments"
    )
    contact_loyalty_points: bool = Field(
        default=False,
        description="Contact loyalty points"
    )
    contact_loyalty_points_custom_ids: bool = Field(
        default=False,
        description="Contact loyalty points by Custom IDs"
    )
    audiences: bool = Field(
        default=False,
        description="Audiences"
    )
    discounts: bool = Field(
        default=False,
        description="Discounts"
    )
    stores: bool = Field(
        default=False,
        description="Stores"
    )
    campaigns: bool = Field(
        default=False,
        description="Campaigns"
    )
    campaign_stats: bool = Field(
        default=False,
        description="Campaign Stats"
    )
    campaign_stats_custom_ids: bool = Field(
        default=False,
        description="Campaign Stats by Custom IDs"
    )
    brand_products: bool = Field(
        default=False,
        description="Brand products"
    )

    custom_contact_details_ids: List[str] = Field(default=[])
    custom_contact_loyalty_points_ids: List[str] = Field(default=[])
    custom_campaign_stats_ids: List[str] = Field(default=[])

    @model_validator(mode="before")
    @classmethod
    def correct_invalid_combinations(cls, values: Dict) -> Dict:
        if values.get("contact_loyalty_points") and values.get("contact_loyalty_points_custom_ids"):
            logging.warning(
                "Both 'contact_loyalty_points' and 'contact_loyalty_points_custom_ids' were set to True. "
                "Defaulting to 'contact_loyalty_points_custom_ids = False'."
            )
            values["contact_loyalty_points_custom_ids"] = False

        if values.get("contact_details"):
            values["contact_list"] = True
            values["custom_contact_details_ids"] = []
        if values.get("contact_details_custom_ids"):
            values["contact_details"] = False

        if values.get("campaign_stats"):
            values["campaigns"] = True
            values["custom_campaign_stats_ids"] = []
        if values.get("campaign_stats_custom_ids"):
            values["campaign_stats"] = False

        return values

    @model_validator(mode="after")
    def validate_dependencies(cls, model):
        if not model.contact_loyalty_points_custom_ids and model.custom_contact_loyalty_points_ids:
            raise ValueError(
                "Field 'custom_contact_loyalty_points_ids' must be empty when "
                "'contact_loyalty_points_custom_ids' is False."
            )
        if not model.contact_details_custom_ids and model.custom_contact_details_ids:
            raise ValueError(
                "Field 'custom_contact_details_ids' must be empty when "
                "'contact_details_custom_ids' is False."
            )
        if not model.campaign_stats_custom_ids and model.custom_campaign_stats_ids:
            raise ValueError(
                "Field 'custom_campaign_stats_ids' must be empty when "
                "'campaign_stats_custom_ids' is False."
            )

        if model.contact_details_custom_ids and model.contact_details:
            raise ValueError(
                "Cannot enable both 'contact_details' and 'contact_details_custom_ids'."
            )
        if model.campaign_stats_custom_ids and model.campaign_stats:
            raise ValueError(
                "Cannot enable both 'campaign_stats' and 'campaign_stats_custom_ids'."
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
