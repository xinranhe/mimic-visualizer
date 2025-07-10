import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from utils import (
    get_admissions,
    get_patient_info,
    get_admission_info,
    get_icu_info,
    get_icd_diagnoses,
    get_icd_procedures,
    get_item_types,
    get_event_data,
    get_discharge_notes,
)

st.set_page_config(layout="wide", page_title="MIMIC-IV Patient Explorer")

st.title("MIMIC-IV Patient Explorer 🩺")

# --- Initialize session state ---
if "selected_items" not in st.session_state:
    st.session_state.selected_items = []
if "page_number" not in st.session_state:
    st.session_state.page_number = 0
if "sort_by" not in st.session_state:
    st.session_state.sort_by = "label"
if "sort_ascending" not in st.session_state:
    st.session_state.sort_ascending = True


# --- Helper Functions for App Logic ---
def add_item_to_selection(item):
    item_identifier = (item["itemid"], item["source_table"])
    if not any(
        (i["itemid"], i["source_table"]) == item_identifier
        for i in st.session_state.selected_items
    ):
        st.session_state.selected_items.append(item)


def remove_item_from_selection(item_to_remove):
    item_identifier = (item_to_remove["itemid"], item_to_remove["source_table"])
    st.session_state.selected_items = [
        item
        for item in st.session_state.selected_items
        if (item["itemid"], item["source_table"]) != item_identifier
    ]


def reset_page_and_sort():
    st.session_state.page_number = 0
    st.session_state.sort_by = "label"
    st.session_state.sort_ascending = True


def handle_sort(column_name):
    if st.session_state.sort_by == column_name:
        st.session_state.sort_ascending = not st.session_state.sort_ascending
    else:
        st.session_state.sort_by = column_name
        st.session_state.sort_ascending = True
    st.session_state.page_number = 0


# --- Main App ---
subject_id_input = st.text_input(
    "Enter subject_id:", "11360891", on_change=reset_page_and_sort
)
if subject_id_input:
    try:
        subject_id = int(subject_id_input)
        hadm_ids = get_admissions(subject_id)
        if hadm_ids:
            selected_hadm_id = st.selectbox(
                "Select Admission ID (hadm_id):",
                hadm_ids,
                on_change=lambda: [
                    reset_page_and_sort(),
                    st.session_state.update(selected_items=[]),
                ],
            )

            if selected_hadm_id:
                # --- PATIENT AND ADMISSION DETAILS ---
                st.header("Patient and Admission Details")
                patient_info = get_patient_info(subject_id)
                admission_info = get_admission_info(subject_id, selected_hadm_id)
                icu_info = get_icu_info(subject_id, selected_hadm_id)

                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**Gender:** {patient_info['gender']}")
                    st.write(f"**Age:** {patient_info['anchor_age']}")
                    if pd.notna(patient_info["dod"]):
                        st.write(f"**Date of Death:** {patient_info['dod']}")
                with col2:
                    st.write(f"**Admission Time:** {admission_info['admittime']}")
                    st.write(f"**Discharge Time:** {admission_info['dischtime']}")
                    if not icu_info.empty:
                        st.write(f"**ICU Entry Time:** {icu_info['intime'].min()}")
                        st.write(f"**ICU Exit Time:** {icu_info['outtime'].max()}")

                # --- ICD INFORMATION ---
                st.header("ICD Information")
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Diagnoses")
                    st.dataframe(get_icd_diagnoses(subject_id, selected_hadm_id))
                with col2:
                    st.subheader("Procedures")
                    st.dataframe(get_icd_procedures(subject_id, selected_hadm_id))

                # --- DISCHARGE NOTES ---
                st.header("Discharge Notes 📝")
                discharge_notes = get_discharge_notes(subject_id, selected_hadm_id)
                if discharge_notes:
                    for note in discharge_notes:
                        note_label = f"Type: {note.get('note_type', 'N/A')} | Sequence: {note.get('note_seq', 'N/A')} | Chart Time: {note.get('charttime', 'N/A')}"
                        with st.expander(note_label):
                            st.text(note.get("text", "Note text not available."))
                else:
                    st.info("No discharge notes found for this admission.")

                # --- Item Table with Pagination and Sorting ---
                st.header("Available ICU Data Items")
                item_types = get_item_types(subject_id, selected_hadm_id)
                if not item_types.empty:
                    filter_cols = st.columns(3)
                    with filter_cols[0]:
                        filter_text = (
                            st.text_input(
                                "Filter items by name:",
                                on_change=lambda: st.session_state.update(page_number=0),
                            ).lower()
                        )
                    with filter_cols[1]:
                        category_options = ["All"] + sorted(
                            item_types["category"].dropna().unique().tolist()
                        )
                        selected_category = st.selectbox(
                            "Filter by Category:",
                            category_options,
                            on_change=lambda: st.session_state.update(page_number=0),
                        )
                    with filter_cols[2]:
                        source_options = ["All"] + sorted(
                            item_types["source_table"].dropna().unique().tolist()
                        )
                        selected_source = st.selectbox(
                            "Filter by Source Table:",
                            source_options,
                            on_change=lambda: st.session_state.update(page_number=0),
                        )

                    filtered_items = item_types
                    if filter_text:
                        filtered_items = filtered_items[
                            filtered_items["label"].str.lower().str.contains(filter_text)
                        ]
                    if selected_category != "All":
                        filtered_items = filtered_items[
                            filtered_items["category"] == selected_category
                        ]
                    if selected_source != "All":
                        filtered_items = filtered_items[
                            filtered_items["source_table"] == selected_source
                        ]

                    sorted_items = filtered_items.sort_values(
                        by=st.session_state.sort_by,
                        ascending=st.session_state.sort_ascending,
                    ).reset_index(drop=True)

                    PAGE_SIZE = 15
                    page_number = st.session_state.page_number
                    start_index = page_number * PAGE_SIZE
                    end_index = min(start_index + PAGE_SIZE, len(sorted_items))
                    total_pages = (len(sorted_items) + PAGE_SIZE - 1) // PAGE_SIZE
                    items_to_display_on_page = sorted_items.iloc[start_index:end_index]

                    # --- CHANGES START HERE ---
                    sort_icon = "🔼" if st.session_state.sort_ascending else "🔽"
                    # Add a new column for Category
                    header_cols = st.columns((3, 2, 2, 1))

                    with header_cols[0]:
                        header_cols[0].button(
                            f"Item Name {sort_icon if st.session_state.sort_by == 'label' else ''}",
                            on_click=handle_sort,
                            args=("label",),
                        )
                    with header_cols[1]:
                        header_cols[1].button(
                            f"Source Table {sort_icon if st.session_state.sort_by == 'source_table' else ''}",
                            on_click=handle_sort,
                            args=("source_table",),
                        )
                    # Add the Category sort button
                    with header_cols[2]:
                        header_cols[2].button(
                            f"Category {sort_icon if st.session_state.sort_by == 'category' else ''}",
                            on_click=handle_sort,
                            args=("category",),
                        )
                    header_cols[3].markdown("**Action**")
                    st.markdown("---")

                    # Display the category for each item
                    for index, row in items_to_display_on_page.iterrows():
                        col1, col2, col3, col4 = st.columns((3, 2, 2, 1))
                        col1.write(row["label"])
                        col2.write(row["source_table"])
                        col3.write(row["category"])  # Display the category
                        if col4.button(
                            "Add", key=f"add_{row['itemid']}_{row['source_table']}"
                        ):
                            add_item_to_selection(row.to_dict())
                            st.rerun()
                    # --- CHANGES END HERE ---

                    st.markdown("---")

                    p_cols = st.columns([2, 1, 2])
                    if p_cols[0].button("⬅️ Previous", disabled=(page_number == 0)):
                        st.session_state.page_number -= 1
                        st.rerun()
                    p_cols[1].write(f"Page {page_number + 1} of {total_pages}")
                    if p_cols[2].button(
                        "Next ➡️", disabled=(page_number >= total_pages - 1)
                    ):
                        st.session_state.page_number += 1
                        st.rerun()

                # --- Visualization Widget ---
                st.header("Visualize Items Over Time")
                admission_start = pd.to_datetime(admission_info["admittime"])
                admission_end = pd.to_datetime(admission_info["dischtime"])

                start_time, end_time = st.slider(
                    "Select time range to visualize:",
                    min_value=admission_start.to_pydatetime(),
                    max_value=admission_end.to_pydatetime(),
                    value=(
                        admission_start.to_pydatetime(),
                        admission_end.to_pydatetime(),
                    ),
                    format="MM/DD/YYYY - hh:mm a",
                )

                if st.session_state.selected_items:
                    st.write("---")
                    for item in list(st.session_state.selected_items):
                        item_key_part = f"{item['itemid']}_{item['source_table']}"
                        col1, col2 = st.columns([4, 1])
                        with col1:
                            st.subheader(
                                f"Visualization for: {item['label']} ({item['source_table']})"
                            )
                        if col2.button("Remove", key=f"remove_{item_key_part}"):
                            remove_item_from_selection(item)
                            st.rerun()

                        event_data = get_event_data(
                            subject_id,
                            selected_hadm_id,
                            item["itemid"],
                            item["source_table"],
                            start_time,
                            end_time,
                        )

                        if not event_data.empty:
                            fig = go.Figure()
                            source_table = item["source_table"]
                            time_col = (
                                "charttime"
                                if source_table in ["chartevents", "datetimeevents"]
                                else "starttime"
                            )
                            event_data[time_col] = pd.to_datetime(event_data[time_col])
                            event_data = event_data.sort_values(by=time_col)

                            if source_table in ["chartevents", "outputevents"]:
                                event_data["value_numeric"] = pd.to_numeric(
                                    event_data["value"], errors="coerce"
                                )
                                if event_data["value_numeric"].notna().any():
                                    fig = px.line(
                                        event_data.dropna(subset=["value_numeric"]),
                                        x=time_col,
                                        y="value_numeric",
                                        title=f"Line Plot for {item['label']}",
                                        markers=True,
                                    )
                                else:
                                    fig = px.scatter(
                                        event_data,
                                        x=time_col,
                                        y="value",
                                        title=f"Scatter Plot for {item['label']}",
                                        hover_data=event_data.columns,
                                    )
                            elif source_table == "datetimeevents":
                                fig = px.scatter(
                                    event_data,
                                    x=time_col,
                                    y=["value"] * len(event_data),
                                    title=f"Events for {item['label']}",
                                    hover_data=event_data.columns,
                                )
                            elif source_table in [
                                "ingredientevents",
                                "inputevents",
                                "procedureevents",
                            ]:
                                event_data["endtime"] = pd.to_datetime(
                                    event_data["endtime"]
                                )
                                for _, row in event_data.iterrows():
                                    fig.add_trace(
                                        go.Scatter(
                                            x=[row["starttime"], row["endtime"]],
                                            y=[item["label"], item["label"]],
                                            mode="lines",
                                            line=dict(width=10),
                                            hoverinfo="text",
                                            text=f"Item: {item['label']}<br>Start: {row['starttime']}<br>End: {row['endtime']}<br>Amount: {row.get('amount', 'N/A')}",
                                        )
                                    )
                                fig.update_layout(title=f"Timeline for {item['label']}")

                            fig.update_xaxes(range=[start_time, end_time])
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning(
                                f"No data available for '{item['label']}' in the selected time range."
                            )
                        st.write("---")

    except ValueError:
        st.error("Please enter a valid numerical subject ID.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
