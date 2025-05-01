"""
AIQ Extractor Component main class.

"""
import csv
from datetime import datetime, UTC
import logging

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

from configuration import Configuration
from api_client import APIClient
from src.utils import write_output_table_if_data


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

        if config.endpoints.contact_adjustments:
            logging.info("Fetching contact adjustments...")
            write_output_table_if_data(
                self,
                name="contact_adjustments",
                records=api_client.get_contact_adjustments(),
                primary_key=["cntID"],
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
