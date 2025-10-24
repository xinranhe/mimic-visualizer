import time
from typing import Any, List

import pandas as pd
from pandas import Timestamp
from pymongo import MongoClient
from tqdm import tqdm


def load_ecg_to_mongo(
    csv_file_path: str,
    mongo_uri: str = "mongodb://localhost:27017/",
    db_name: str = "mimiciv_ecg",
    collection_name: str = "machine_measurement",
    chunk_size: int = 2000,
) -> None:
    """
    Load ECG metadata from a CSV file into a MongoDB collection with a progress bar.

    Args:
        csv_file_path: Path to the source CSV file.
        mongo_uri: MongoDB connection string.
        db_name: Database name, defaults to 'ecg'.
        collection_name: Collection name, defaults to 'ecg'.
        chunk_size: Number of rows to process per chunk.
    """

    def _to_optional_int(value: Any) -> Any:
        if pd.isna(value):
            return None
        return int(value)

    def _to_optional_datetime(value: Any) -> Any:
        if isinstance(value, Timestamp):
            return value.to_pydatetime()
        if pd.isna(value):
            return None
        return value

    def _format_metric(value: Any) -> str:
        if pd.isna(value):
            return "None"
        return str(value)

    try:
        client = MongoClient(mongo_uri)
        database = client[db_name]
        collection = database[collection_name]

        collection.drop()
        print(f"Existing collection '{collection_name}' dropped.")
        print(f"Starting to load data from {csv_file_path} into MongoDB...")

        csv_iterator = pd.read_csv(
            csv_file_path,
            chunksize=chunk_size,
            iterator=True,
            dtype={
                "subject_id": "Int64",
                "study_id": "Int64",
                "cart_id": "string",
                "bandwidth": "string",
                "filtering": "string",
                "rr_interval": "float64",
                "p_onset": "float64",
                "p_end": "float64",
                "qrs_onset": "float64",
                "qrs_end": "float64",
                "t_end": "float64",
                "p_axis": "float64",
                "qrs_axis": "float64",
                "t_axis": "float64",
            },
            parse_dates=["ecg_time"],
            keep_default_na=True,
        )

        with tqdm(desc="Uploading to MongoDB", unit=" rows") as progress_bar:
            for chunk in csv_iterator:
                report_columns: List[str] = [
                    column
                    for column in chunk.columns
                    if column.lower().startswith("report_")
                ]

                documents = []
                for _, row in chunk.iterrows():
                    report_values = []
                    for report_column in report_columns:
                        report_value = row.get(report_column)
                        if pd.isna(report_value):
                            continue
                        value_as_string = str(report_value).strip()
                        if value_as_string:
                            report_values.append(value_as_string)

                    metrics_description = ", ".join(
                        [
                            f"rr_interval:{_format_metric(row.get('rr_interval'))}",
                            f"p_axis:{_format_metric(row.get('p_axis'))}",
                            f"qrs_axis:{_format_metric(row.get('qrs_axis'))}",
                            f"t_axis:{_format_metric(row.get('t_axis'))}",
                        ]
                    )

                    if report_values:
                        text_content = ", ".join(report_values + [metrics_description])
                    else:
                        text_content = metrics_description

                    document = {
                        "subject_id": _to_optional_int(row.get("subject_id")),
                        "study_id": _to_optional_int(row.get("study_id")),
                        "ecg_time": _to_optional_datetime(row.get("ecg_time")),
                        "text": text_content,
                    }
                    documents.append(document)

                if documents:
                    collection.insert_many(documents)
                    progress_bar.update(len(documents))
                    time.sleep(0.5)

        print("\nData loading complete!")
        print(f"Total documents inserted: {collection.count_documents({})}")
    except FileNotFoundError:
        print(f"Error: The file '{csv_file_path}' was not found.")
    except Exception as error:
        print(f"An error occurred: {error}")
    finally:
        if "client" in locals():
            client.close()


if __name__ == "__main__":
    CSV_PATH = "./machine_measurements.csv"
    load_ecg_to_mongo(CSV_PATH)
