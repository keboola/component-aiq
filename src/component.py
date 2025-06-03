"""
AIQ Extractor Component main class.
"""
from datetime import datetime, UTC
import logging
from pathlib import Path

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

from configuration import Configuration
from api_client import APIClient
from utils import (
    write_output_table_if_data,
    extract_contact_ids_from_contact_list_csv,
    extract_campaign_ids_from_campaign_list_csv,
    extract_contact_ids_from_contact_adjustments_csv
)


class Component(ComponentBase):
    def __init__(self):
        super().__init__()

    def run(self):
        run_time = datetime.now(UTC)
        run_time_str = run_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        config = Configuration(**self.configuration.parameters)
        state = self.get_state_file()
        api_client = APIClient(config, state)
        new_state = {}

        if config.endpoints.contact_list:
            logging.info("Fetching contact list...")
            write_output_table_if_data(
                self,
                name="contact_list",
                records=api_client.get_contact_list(),
                primary_key=["contactID"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.contact_details:
            contact_ids = extract_contact_ids_from_contact_list_csv(
                Path(self.configuration.data_dir) / "out" / "tables" / "contact_list.csv"
            )
            logging.info("Fetching contact details list...")

            write_output_table_if_data(
                self,
                name="contact_details",
                records=api_client.get_contact_details_by_custom_ids(contact_ids),
                primary_key=["contactID"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.contact_details_custom_ids:
            contact_ids = config.endpoints.custom_contact_details_ids
            logging.info(f"Syncing contact details with {len(contact_ids)} custom contact IDs...")

            write_output_table_if_data(
                self,
                name="contact_details",
                records=api_client.get_contact_details_by_custom_ids(contact_ids),
                primary_key=["contactID"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.contact_adjustments:
            logging.info("Fetching contact adjustments...")
            write_output_table_if_data(
                self,
                name="contact_adjustments",
                records=api_client.get_contact_adjustments(),
                primary_key=["cntID"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.contact_loyalty_points:
            contact_ids = extract_contact_ids_from_contact_adjustments_csv(
                Path(self.configuration.data_dir) / "out" / "tables" / "contact_adjustments.csv"
            )

            write_output_table_if_data(
                self,
                name="contact_loyalty_points",
                records=api_client.get_loyalty_points_for_contacts(contact_ids),
                primary_key=["contactID"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.contact_loyalty_points_custom_ids:
            contact_ids = config.endpoints.custom_contact_loyalty_points_ids

            logging.info(f"Syncing loyalty points for {len(contact_ids)} custom contact IDs...")

            write_output_table_if_data(
                self,
                name="contact_loyalty_points",
                records=api_client.get_loyalty_points_for_contacts(contact_ids),
                primary_key=["contactID"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.audiences:
            logging.info("Fetching audiences...")

            write_output_table_if_data(
                self,
                name="audiences",
                records=api_client.get_audiences(),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.discounts:
            logging.info("Fetching discount data...")
            write_output_table_if_data(
                self,
                name="discounts",
                records=api_client.get_discounts(),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.stores:
            logging.info("Fetching store data...")
            write_output_table_if_data(
                self,
                name="stores",
                records=api_client.get_stores(),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.campaigns:
            logging.info("Fetching campaigns...")
            write_output_table_if_data(
                self,
                name="campaigns",
                records=api_client.get_campaigns(),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.campaign_stats:
            campaign_ids = extract_campaign_ids_from_campaign_list_csv(
                Path(self.configuration.data_dir) / "out" / "tables" / "campaigns.csv"
            )
            logging.info("Fetching campaign stats...")

            write_output_table_if_data(
                self,
                name="campaign_stats",
                records=api_client.get_campaign_stats_by_ids(campaign_ids),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.campaign_stats_custom_ids:
            campaign_ids = config.endpoints.custom_campaign_stats_ids
            logging.info(f"Syncing campaign stats with {len(campaign_ids)} custom campaign IDs...")

            write_output_table_if_data(
                self,
                name="campaign_stats",
                records=api_client.get_campaign_stats_by_ids(campaign_ids),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        if config.endpoints.brand_products:
            logging.info("Fetching brand products...")
            write_output_table_if_data(
                self,
                name="brand_products",
                records=api_client.get_brand_products(),
                primary_key=["id"],
                incremental=(config.sync_options.sync_mode == "incremental_sync")
            )

        new_state["last_successful_run"] = run_time_str
        logging.info("Saving component state...")
        self.write_state_file(new_state)
        logging.info("Data processing completed!")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
