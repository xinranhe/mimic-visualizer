import pandas as pd
from db_connections import get_mysql_connection, get_mongo_connection


def get_admissions(subject_id):
    """Fetches all hospital admission IDs (hadm_id) for a given patient."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"SELECT hadm_id FROM admissions WHERE subject_id = {subject_id}"
        df = pd.read_sql(query, conn)
        return df["hadm_id"].tolist()
    return []


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
        SELECT intime, outtime
        FROM icustays
        WHERE subject_id = {subject_id} AND hadm_id = {hadm_id}
        """
        return pd.read_sql(query, conn)
    return pd.DataFrame()


def get_icd_diagnoses(subject_id, hadm_id):
    """Retrieves ICD diagnosis descriptions for a given admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT d.long_title
        FROM diagnoses_icd di
        JOIN d_icd_diagnoses d ON di.icd_code = d.icd_code AND di.icd_version = d.icd_version
        WHERE di.subject_id = {subject_id} AND di.hadm_id = {hadm_id}
        """
        return pd.read_sql(query, conn)
    return pd.DataFrame()


def get_icd_procedures(subject_id, hadm_id):
    """Fetches ICD procedure descriptions for a given admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT p.long_title
        FROM procedures_icd pi
        JOIN d_icd_procedures p ON pi.icd_code = p.icd_code AND pi.icd_version = p.icd_version
        WHERE pi.subject_id = {subject_id} AND pi.hadm_id = {hadm_id}
        """
        return pd.read_sql(query, conn)
    return pd.DataFrame()


def get_item_types(subject_id, hadm_id):
    """Lists all possible item types from ICU tables for an admission."""
    conn = get_mysql_connection()
    if conn is not None:
        query = f"""
        SELECT 'chartevents' as source_table, itemid FROM chartevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'outputevents' as source_table, itemid FROM outputevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'datetimeevents' as source_table, itemid FROM datetimeevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'ingredientevents' as source_table, itemid FROM ingredientevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'inputevents' as source_table, itemid FROM inputevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        UNION ALL
        SELECT 'procedureevents' as source_table, itemid FROM procedureevents WHERE subject_id = {subject_id} AND hadm_id = {hadm_id} GROUP BY itemid
        """
        item_ids = pd.read_sql(query, conn)
        if item_ids.empty:
            return pd.DataFrame()
        d_items_query = "SELECT itemid, label, abbreviation, category FROM d_items"
        d_items = pd.read_sql(d_items_query, conn)
        return pd.merge(item_ids, d_items, on="itemid")
    return pd.DataFrame()


def get_event_data(subject_id, hadm_id, item_id, source_table, start_time, end_time):
    """Fetches event data for a specific item within a given time range."""
    conn = get_mysql_connection()
    if conn is None:
        return pd.DataFrame()

    # --- THIS IS THE FIX ---
    # Correctly assign the time column based on the source table name
    if source_table in ["inputevents", "procedureevents", "ingredientevents"]:
        time_col = "starttime"
    else:  # Covers chartevents, outputevents, datetimeevents
        time_col = "charttime"

    query = f"""
    SELECT *
    FROM {source_table}
    WHERE subject_id = {subject_id}
      AND hadm_id = {hadm_id}
      AND itemid = {item_id}
      AND {time_col} BETWEEN '{start_time}' AND '{end_time}'
    """
    return pd.read_sql(query, conn)


def get_discharge_notes(subject_id, hadm_id):
    """Fetches discharge notes for a given admission from MongoDB."""
    db = get_mongo_connection()
    if db is not None:
        notes_cursor = db.discharge.find(
            {"subject_id": subject_id, "hadm_id": hadm_id}, {"_id": 0}
        )
        return list(notes_cursor)
    return []
