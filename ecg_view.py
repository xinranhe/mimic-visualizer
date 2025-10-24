from pathlib import Path
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import streamlit as st
import wfdb


def _set_query_param_value(parameter_name: str, parameter_value: Optional[str]) -> None:
    """Update a URL query parameter using the safest available API."""
    query_params = getattr(st, "query_params", None)
    if query_params is not None:
        if parameter_value:
            query_params[parameter_name] = parameter_value
        elif parameter_name in query_params:
            del query_params[parameter_name]
        return

    parameters = st.experimental_get_query_params()
    if parameter_value:
        parameters[parameter_name] = parameter_value
    else:
        parameters.pop(parameter_name, None)
    st.experimental_set_query_params(**parameters)


def _parse_record_locator(record_locator: str) -> Tuple[str, str]:
    """Validate and split locator of the form ecg/pXXXXXXXX/sZZZZZZZZ."""
    normalized_locator = record_locator.strip("/")
    locator_parts = normalized_locator.split("/")

    if len(locator_parts) != 3 or locator_parts[0].lower() != "ecg":
        raise ValueError("Locator must follow the format ecg/pXXXXXXXX/sZZZZZZZZ.")

    subject_segment, study_segment = locator_parts[1], locator_parts[2]
    if not subject_segment.startswith("p") or not study_segment.startswith("s"):
        raise ValueError("Locator segments must start with 'p' and 's' respectively.")

    subject_identifier = subject_segment[1:]
    study_identifier = study_segment[1:]

    if len(subject_identifier) < 4 or not subject_identifier.isdigit():
        raise ValueError("Subject identifier must be numeric and at least four digits.")
    if not study_identifier.isdigit():
        raise ValueError("Study identifier must be numeric.")

    return subject_identifier, study_identifier


def _resolve_record_path(
    base_directory: Path, subject_identifier: str, study_identifier: str
) -> Path:
    """Build the filesystem path to the WFDB record, excluding file suffix."""
    subject_prefix = subject_identifier[:4]
    record_directory = (
        base_directory
        / "files"
        / f"p{subject_prefix}"
        / f"p{subject_identifier}"
        / f"s{study_identifier}"
    )
    return record_directory / study_identifier


def _load_record(record_path: Path) -> wfdb.Record:
    """Read the WFDB record from disk."""
    return wfdb.rdrecord(str(record_path))


def _plot_record(record: wfdb.Record, study_identifier: str) -> None:
    """Create and display a WFDB plot in Streamlit."""
    figure = None
    try:
        plot_output = wfdb.plot_wfdb(
            record=record,
            figsize=(24, 18),
            title=f"Study {study_identifier} ECG Waveform",
            ecg_grids="all",
            return_fig=True,
        )
    except TypeError:
        wfdb.plot_wfdb(
            record=record,
            figsize=(24, 18),
            title=f"Study {study_identifier} ECG Waveform",
            ecg_grids="all",
        )
        figure = plt.gcf()
    else:
        if isinstance(plot_output, tuple):
            figure = plot_output[0]
        else:
            figure = plot_output

    if figure is None:
        figure = plt.gcf()

    st.pyplot(figure)
    plt.close(figure)


def render_ecg_page(
    base_directory: Optional[Path],
    request_path: str,
) -> None:
    """Render the ECG waveform page within the main Streamlit app."""
    st.title("ECG Waveform Viewer")

    if base_directory is None:
        st.error(
            "ECG base folder not provided. Use --ecg-base-folder when starting the app."
        )
        return

    normalized_request = request_path.strip("/")
    default_locator = normalized_request if normalized_request else ""
    if default_locator.lower() == "ecg":
        default_locator = ""

    locator_input = st.text_input(
        "ECG record locator",
        value=default_locator,
        placeholder="ecg/p10001725/s41420867",
        help="Provide the record path in the format ecg/pXXXXXXXX/sZZZZZZZZ.",
    )

    if locator_input != default_locator:
        _set_query_param_value("path", locator_input or None)

    if not locator_input:
        st.info("Enter an ECG record locator to render the waveform.")
        return

    try:
        subject_identifier, study_identifier = _parse_record_locator(locator_input)
    except ValueError as locator_error:
        st.error(str(locator_error))
        return

    record_path = _resolve_record_path(
        base_directory, subject_identifier, study_identifier
    )
    dat_file = record_path.with_suffix(".dat")
    header_file = record_path.with_suffix(".hea")

    if not dat_file.exists() or not header_file.exists():
        st.error("ECG not found.")
        return

    try:
        with st.spinner("Loading ECG waveform..."):
            record = _load_record(record_path)
            _plot_record(record, study_identifier)
    except FileNotFoundError:
        st.error("ECG not found.")
        return
    except Exception as error:  # pragma: no cover
        st.error(f"Unable to read ECG record: {error}")
        return
