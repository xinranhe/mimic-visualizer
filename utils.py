import pandas as pd
from db_connections import get_mysql_connection, get_mongo_connection


def get_admissions(subject_id):
    """Return admissions with times and ICU stay information sorted by time."""
    conn = get_mysql_connection()
    if conn is None:
        return pd.DataFrame()

    query = f"""
    SELECT a.hadm_id,
           a.admittime,
           a.dischtime,
           CASE WHEN i.hadm_id IS NOT NULL THEN 1 ELSE 0 END AS has_icu
    FROM admissions a
    LEFT JOIN (
        SELECT DISTINCT hadm_id
        FROM icustays
        WHERE subject_id = {subject_id}
    ) i ON a.hadm_id = i.hadm_id
    WHERE a.subject_id = {subject_id}
    ORDER BY a.admittime ASC
    """

    admissions_df = pd.read_sql(query, conn)
    return admissions_df


def get_patient_info(subject_id):
    """Retrieves basic patient information including anchor year."""
    conn = get_mysql_connection()
    if conn is not None:
        query = (
            f"SELECT gender, anchor_age, anchor_year, dod "
            f"FROM patients WHERE subject_id = {subject_id}"
        )
        return pd.read_sql(query, conn).iloc[0]
    return None


def get_admission_info(subject_id, hadm_id):
    """Gathers details about a specific hospital admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT admittime, dischtime, insurance, language,
               marital_status, race
        FROM admissions
        WHERE subject_id = {subject_id} AND hadm_id = {hadm_id}
        """
        return pd.read_sql(query, conn).iloc[0]
    return None


def get_admission_services(subject_id, hadm_id):
    """Returns a comma separated list of services for the admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT DISTINCT curr_service
        FROM services
        WHERE subject_id = {subject_id} AND hadm_id = {hadm_id}
        """
        df = pd.read_sql(query, conn)
        if df.empty:
            return ""
        return ",".join(df["curr_service"].dropna().tolist())
    return ""


def get_icu_info(subject_id, hadm_id):
    """Fetches ICU entry and exit times for an admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT stay_id, intime, outtime
        FROM icustays
        WHERE subject_id = {subject_id} AND hadm_id = {hadm_id}
        ORDER BY intime ASC
        """
        return pd.read_sql(query, conn)
    return pd.DataFrame()


def get_icd_diagnoses(subject_id, hadm_id):
    """Retrieves ICD diagnosis descriptions for a given admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT di.icd_code, di.icd_version, d.long_title
        FROM diagnoses_icd di
        JOIN d_icd_diagnoses d ON di.icd_code = d.icd_code AND di.icd_version = d.icd_version
        WHERE di.subject_id = {subject_id} AND di.hadm_id = {hadm_id}
        """
        df = pd.read_sql(query, conn)
        # Create a combined column for display with format [V9] 123.45 or [V10] A12.3
        if not df.empty:
            df["icd"] = "[V" + df["icd_version"].astype(str) + "] " + df["icd_code"]
            # Reorder columns to put combined column first
            df = df[["icd", "long_title"]]
        return df
    return pd.DataFrame()


def get_icd_procedures(subject_id, hadm_id):
    """Fetches ICD procedure descriptions for a given admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT pi.icd_code, pi.icd_version, p.long_title
        FROM procedures_icd pi
        JOIN d_icd_procedures p ON pi.icd_code = p.icd_code AND pi.icd_version = p.icd_version
        WHERE pi.subject_id = {subject_id} AND pi.hadm_id = {hadm_id}
        """
        df = pd.read_sql(query, conn)
        # Create a combined column for display with format [V9] 123.45 or [V10] A12.3
        if not df.empty:
            df["icd"] = "[V" + df["icd_version"].astype(str) + "] " + df["icd_code"]
            # Reorder columns to put combined column first
            df = df[["icd", "long_title"]]
        return df
    return pd.DataFrame()


def get_item_types(subject_id, hadm_id):
    """Lists all possible item types from ICU tables, lab events, and prescriptions for an admission."""
    conn = get_mysql_connection()
    if conn is not None:
        # 1. Get ICU items from event tables
        icu_query = f"""
        SELECT 'chartevents' as source_table, itemid, COUNT(*) as data_count FROM chartevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'outputevents' as source_table, itemid, COUNT(*) as data_count FROM outputevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'datetimeevents' as source_table, itemid, COUNT(*) as data_count FROM datetimeevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'ingredientevents' as source_table, itemid, COUNT(*) as data_count FROM ingredientevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'inputevents' as source_table, itemid, COUNT(*) as data_count FROM inputevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'procedureevents' as source_table, itemid, COUNT(*) as data_count FROM procedureevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        """
        icu_item_ids = pd.read_sql(icu_query, conn)

        # Join with d_items to get labels
        if not icu_item_ids.empty:
            d_items_query = "SELECT itemid, label, abbreviation, category FROM d_items"
            d_items = pd.read_sql(d_items_query, conn)
            icu_items = pd.merge(icu_item_ids, d_items, on="itemid")
        else:
            icu_items = pd.DataFrame()

        # 2. Get lab items from labevents
        lab_query = f"""
        SELECT 'labevents' as source_table, itemid, COUNT(*) as data_count
        FROM labevents 
        WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} 
        GROUP BY itemid
        """
        lab_item_ids = pd.read_sql(lab_query, conn)

        # Join with d_labitems to get labels
        if not lab_item_ids.empty:
            d_labitems_query = "SELECT itemid, label, fluid, category FROM d_labitems"
            d_labitems = pd.read_sql(d_labitems_query, conn)

            # Rename fluid to abbreviation to align with d_items schema
            d_labitems = d_labitems.rename(columns={"fluid": "abbreviation"})

            lab_items = pd.merge(lab_item_ids, d_labitems, on="itemid")
        else:
            lab_items = pd.DataFrame()

        # 3. Get prescription items
        # For prescriptions, we'll use drug as item identifier and route as category
        prescriptions_query = f"""
        SELECT 'prescriptions' as source_table, 
               drug, route, 
               COUNT(*) as data_count
        FROM prescriptions 
        WHERE subject_id = {subject_id} AND hadm_id = {hadm_id}
        GROUP BY drug, route
        """
        prescriptions_df = pd.read_sql(prescriptions_query, conn)

        if not prescriptions_df.empty:
            # Create a synthetic itemid for prescriptions by hashing the drug+route combo
            # This allows us to uniquely identify each drug+route combination
            # Convert to string hashes and then to positive integers to avoid conflicts with real itemids
            prescriptions_df["itemid"] = prescriptions_df.apply(
                lambda row: abs(
                    hash(f"prescription_{row['drug']}_{row['route'] or 'NA'}") % (10**9)
                ),
                axis=1,
            )

            # Format the prescription items to match the schema of other items
            prescriptions_df["label"] = prescriptions_df["drug"]
            prescriptions_df["category"] = prescriptions_df["route"].fillna(
                "Unspecified"
            )
            prescriptions_df["abbreviation"] = ""
            # Rename count to data_count for consistency
            prescriptions_df.rename(columns={"count": "data_count"}, inplace=True)

            # Select only relevant columns
            prescription_items = prescriptions_df[
                [
                    "source_table",
                    "itemid",
                    "label",
                    "abbreviation",
                    "category",
                    "data_count",
                ]
            ]
        else:
            prescription_items = pd.DataFrame()

        # Combine all items
        all_items = pd.concat(
            [icu_items, lab_items, prescription_items], ignore_index=True
        )
        return all_items
    return pd.DataFrame()


def get_event_data(subject_id, hadm_id, item_id, source_table, start_time, end_time):
    """Fetches event data for a specific item within a given time range."""
    conn = get_mysql_connection()
    if conn is None:
        return pd.DataFrame()

    # Assign the time column based on the source table name
    if source_table in ["inputevents", "procedureevents", "ingredientevents"]:
        time_col = "starttime"
    elif source_table == "labevents":
        time_col = "charttime"
    elif source_table == "prescriptions":
        time_col = "starttime"  # Prescriptions use starttime
    else:  # Covers chartevents, outputevents, datetimeevents
        time_col = "charttime"

    # For standard tables with itemid (ICU items and lab items)
    if source_table not in ["prescriptions"]:
        query = f"""
        SELECT *
        FROM {source_table}
        WHERE subject_id = {subject_id}
          AND hadm_id = {hadm_id}
          AND itemid = {item_id}
          AND {time_col} BETWEEN '{start_time}' AND '{end_time}'
        """

        # For labevents, convert valuenum to value if available for consistent visualization
        result_df = pd.read_sql(query, conn)

        if source_table == "labevents" and not result_df.empty:
            # If valuenum is available, use it as the primary value for visualization
            # But preserve original value in value_text field for reference
            if "valuenum" in result_df.columns:
                result_df["value_text"] = result_df[
                    "value"
                ]  # Store original text value
                # Replace value with valuenum where available
                mask = result_df["valuenum"].notna()
                result_df.loc[mask, "value"] = result_df.loc[mask, "valuenum"].astype(
                    str
                )

                # Add a column for units if it exists
                if "valueuom" in result_df.columns:
                    result_df["unit"] = result_df["valueuom"]

        return result_df

    # Handle prescriptions - we need to find the specific drug and route from the hashed itemid
    elif source_table == "prescriptions":
        # First, we need to get the drug and route info from our items table
        # Since we hashed the itemid from drug+route, we'll find the original item data
        # from the get_item_types function to get the original drug and route
        items_query = f"""
        SELECT drug, route, drug as label
        FROM prescriptions 
        WHERE subject_id = {subject_id} 
        AND hadm_id = {hadm_id}
        GROUP BY drug, route
        """

        all_prescription_items = pd.read_sql(items_query, conn)

        # Calculate the same hash we used in get_item_types
        all_prescription_items["calculated_itemid"] = all_prescription_items.apply(
            lambda row: abs(
                hash(f"prescription_{row['drug']}_{row['route'] or 'NA'}") % (10**9)
            ),
            axis=1,
        )

        # Find the matching drug and route based on the item_id
        matching_items = all_prescription_items[
            all_prescription_items["calculated_itemid"] == item_id
        ]

        if matching_items.empty:
            return pd.DataFrame()

        # Get the actual drug and route for this itemid
        drug = matching_items.iloc[0]["drug"]
        route = matching_items.iloc[0]["route"]

        # Now get all prescriptions matching this drug+route combination
        prescriptions_query = f"""
        SELECT 
            subject_id, hadm_id, drug, starttime, stoptime, 
            route, dose_val_rx, dose_unit_rx, prod_strength
        FROM prescriptions
        WHERE subject_id = {subject_id}
          AND hadm_id = {hadm_id}
          AND drug = '{drug.replace("'", "''")}'
          {"AND route = '" + route.replace("'", "''") + "'" if pd.notna(route) else "AND route IS NULL"}
          AND starttime BETWEEN '{start_time}' AND '{end_time}'
        ORDER BY starttime
        """

        prescriptions_df = pd.read_sql(prescriptions_query, conn)

        # Add consistent columns for visualization
        if not prescriptions_df.empty:
            # Add a value column for dose information
            prescriptions_df["value"] = prescriptions_df.apply(
                lambda row: (
                    f"{row['dose_val_rx']} {row['dose_unit_rx']}"
                    if pd.notna(row["dose_val_rx"])
                    else "Unknown dose"
                ),
                axis=1,
            )

            # Add itemid column
            prescriptions_df["itemid"] = item_id

        return prescriptions_df

    return pd.DataFrame()


def get_discharge_notes(subject_id, hadm_id):
    """Fetches discharge notes for a given admission from MongoDB."""
    db = get_mongo_connection()
    if db is not None:
        notes_cursor = db.discharge.find(
            {"subject_id": subject_id, "hadm_id": hadm_id}, {"_id": 0}
        )
        return list(notes_cursor)
    return []
