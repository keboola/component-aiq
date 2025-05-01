import csv
import logging
from typing import Generator


def write_output_table_if_data(self, name: str, records: Generator[dict, None, None], primary_key: list[str], incremental: bool) -> bool:
    """
    Writes output CSV and manifest if records are present.
    Returns True if any data was written.
    """
    try:
        first_record = next(records)
    except StopIteration:
        logging.info(f"No data found for '{name}'. Skipping output file.")
        return False

    table_def = self.create_out_table_definition(
        f"{name}.csv",
        primary_key=primary_key,
        incremental=incremental
    )

    with open(table_def.full_path, mode="wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(first_record.keys()))
        writer.writeheader()
        writer.writerow(first_record)

        for record in records:
            writer.writerow(record)

    logging.info(f"Dataset '{name}' downloaded. Writing manifest...")
    self.write_manifest(table_def)
    return True
