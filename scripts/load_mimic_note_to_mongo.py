import pandas as pd
from pymongo import MongoClient
import time
from tqdm import tqdm

def load_discharge_notes_to_mongo(csv_file_path, mongo_uri="mongodb://localhost:27017/", db_name="mimiciv_note", collection_name="discharge", chunk_size=2000):
    """
    Loads discharge notes from a CSV file into a MongoDB collection with a progress bar.
    This version robustly handles multi-line CSVs and missing date values.

    Args:
        csv_file_path (str): The path to the discharge.csv file.
        mongo_uri (str): The MongoDB connection string.
        db_name (str): The name of the database.
        collection_name (str): The name of the collection.
        chunk_size (int): The number of rows to process in each chunk.
    """
    try:
        # Establish a connection to MongoDB
        client = MongoClient(mongo_uri)
        db = client[db_name]
        collection = db[collection_name]
        
        # Optional: Drop the collection if it already exists to avoid duplicates
        collection.drop()
        print(f"Existing collection '{collection_name}' dropped.")

        print(f"Starting to load data from {csv_file_path} into MongoDB...")

        # Create an iterator to read the CSV in chunks
        csv_iterator = pd.read_csv(
            csv_file_path,
            chunksize=chunk_size,
            iterator=True,
            dtype={
                'note_id': 'string',
                'subject_id': 'Int64',
                'hadm_id': 'Int64',
                'note_type': 'string',
                'note_seq': 'Int64',
                'text': 'string'
            },
            parse_dates=['charttime', 'storetime']
        )
        
        with tqdm(desc="Uploading to MongoDB", unit=" rows") as pbar:
            for chunk in csv_iterator:
                
                # --- FIX V2: More robustly handle NaT values ---
                # This explicitly converts NaT to None by first changing the column's
                # data type to 'object', which can hold mixed types.
                for col in ['charttime', 'storetime']:
                    chunk[col] = chunk[col].astype(object).where(chunk[col].notna(), None)
                
                # Convert the chunk to a list of dictionaries (documents)
                records = chunk.to_dict('records')
                
                # Perform a bulk insert
                collection.insert_many(records)
                
                # Update the progress bar by the number of rows in the chunk
                pbar.update(len(records))

                time.sleep(0.5) # <--- 2. Add a half-second pause

        print("\nData loading complete!")
        print(f"Total documents inserted: {collection.count_documents({})}")

    except FileNotFoundError:
        print(f"Error: The file '{csv_file_path}' was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if 'client' in locals():
            client.close()

if __name__ == '__main__':
    # --- Configuration ---
    # Update this path to the location of your discharge.csv file
    CSV_PATH = './discharge.csv'
    
    # --- Run the Script ---
    load_discharge_notes_to_mongo(CSV_PATH)