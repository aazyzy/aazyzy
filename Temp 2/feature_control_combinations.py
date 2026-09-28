from __future__ import annotations

import argparse
import itertools
import math
import re
import time
from collections import OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import pandas as pd
import xlsxwriter

# =============================================================================
# CONFIGURATION: update these two paths, or pass --source and --output-dir.
# =============================================================================
SOURCE_FILE_PATH = r"C:\Users\h321kgg\OneDrive - Banque Nationale du Canada\NBIN Product Team - Product Activation\User Data Analysis\CX Prod User Packages JSON\User Package Capability Controls.xlsx"
OUTPUT_DIRECTORY = r"C:\Users\h321kgg\OneDrive - Banque Nationale du Canada\NBIN Product Team - Product Activation\User Data Analysis\CX Prod User Packages JSON"

# Optional. Leave as None for the complete output. Set to a small integer such
# as 1000 only when testing layout and logic.
TEST_ROW_LIMIT: Optional[int] = None

SOURCE_SHEET_NAME = "Feature_Controls"
OUTPUT_FILE_PREFIX = "Feature_Control_Combinations"
DATE_FORMAT = "%Y%m%d"  # Example: Feature_Control_Combinations_20260817.xlsx

FEATURE_COLUMN = "Features"
CONTROL_COLUMNS = ["View", "Manage", "Control", "Process"]
LIMITATION_COLUMN = "Limitations"

MANDATORY_TEXT = "available in all packages"
CLIENT_MANAGEMENT_TEXT = "only available under client user management"
DEPENDENCY_PREFIX = "cannot be assigned without"

EXCEL_MAX_ROWS = 1_048_576
DATA_ROWS_PER_COMBO_SHEET = EXCEL_MAX_ROWS - 1  # one row reserved for headers

# Terminal progress update frequency while writing combinations.
PROGRESS_EVERY_ROWS = 100_000


# =============================================================================
# Terminal progress reporting
# =============================================================================
def log(message: str) -> None:
    """Print an immediate, timestamped terminal update."""
    stamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{stamp}] {message}", flush=True)


def format_elapsed(seconds: float) -> str:
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


# =============================================================================
# Input cleaning and validation
# =============================================================================
def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\u00a0", " ")).strip()


def normalized(value: str) -> str:
    return clean_text(value).casefold()


def is_yes(value) -> bool:
    return normalized(value) == "yes"


def read_source(source_path: Path) -> pd.DataFrame:
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    sheet = SOURCE_SHEET_NAME
    try:
        df = pd.read_excel(source_path, sheet_name=sheet, engine="openpyxl")
    except ValueError:
        # If the configured name is unavailable, use the first worksheet.
        df = pd.read_excel(source_path, sheet_name=0, engine="openpyxl")

    df.columns = [clean_text(c) for c in df.columns]
    required = [FEATURE_COLUMN, *CONTROL_COLUMNS, LIMITATION_COLUMN]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(
            "The source is missing required column(s): " + ", ".join(missing)
        )

    df = df[required].copy()
    for col in required:
        df[col] = df[col].map(clean_text)

    df = df[df[FEATURE_COLUMN] != ""].reset_index(drop=True)

    duplicated = df[FEATURE_COLUMN].map(normalized).duplicated(keep=False)
    if duplicated.any():
        names = sorted(df.loc[duplicated, FEATURE_COLUMN].unique())
        raise ValueError("Feature names must be unique. Duplicates: " + ", ".join(names))

    invalid_controls = []
    for col in CONTROL_COLUMNS:
        bad = ~df[col].map(normalized).isin({"yes", "no"})
        if bad.any():
            vals = sorted(df.loc[bad, col].unique())
            invalid_controls.append(f"{col}: {vals}")
    if invalid_controls:
        raise ValueError(
            "Control cells must contain Yes or No. Invalid values: "
            + "; ".join(invalid_controls)
        )

    no_controls = ~df[CONTROL_COLUMNS].apply(lambda row: any(is_yes(v) for v in row), axis=1)
    if no_controls.any():
        names = ", ".join(df.loc[no_controls, FEATURE_COLUMN])
        raise ValueError(f"Every feature must have at least one Yes control: {names}")

    return df


# =============================================================================
# Business-rule model
# =============================================================================
def selected_control_options(row: Mapping[str, str]) -> List[str]:
    """Return all valid non-blank selected control combinations for a feature."""
    available = [c for c in CONTROL_COLUMNS if is_yes(row[c])]

    if "View" in available:
        extras = [c for c in available if c != "View"]
        options = []
        for size in range(0, len(extras) + 1):
            for subset in itertools.combinations(extras, size):
                options.append(" + ".join(["View", *subset]))
        return options

    options = []
    for size in range(1, len(available) + 1):
        for subset in itertools.combinations(available, size):
            options.append(" + ".join(subset))
    return options


def classify_limitation(value: str) -> str:
    n = normalized(value)
    if n == MANDATORY_TEXT:
        return "MANDATORY"
    if n == CLIENT_MANAGEMENT_TEXT:
        return "CLIENT_USER_MANAGEMENT"
    if n.startswith(DEPENDENCY_PREFIX):
        return "DEPENDENT"
    if n == "":
        return "REGULAR"
    raise ValueError(f"Unrecognized limitation value: {value!r}")


def dependency_target(value: str) -> str:
    text = clean_text(value)
    match = re.match(
        r"^cannot\s+be\s+assigned\s+without\s+(.+)$", text, flags=re.IGNORECASE
    )
    if not match:
        raise ValueError(f"Invalid dependency limitation: {value!r}")
    return clean_text(match.group(1))


def resolve_feature_name(reference: str, feature_names: Sequence[str]) -> str:
    """Resolve exact names first, then a unique colon-suffix such as Paper Upload."""
    ref = normalized(reference)
    exact = [name for name in feature_names if normalized(name) == ref]
    if len(exact) == 1:
        return exact[0]

    suffix = [
        name
        for name in feature_names
        if normalized(name).endswith(": " + ref)
    ]
    if len(suffix) == 1:
        return suffix[0]

    candidates = exact or suffix
    if not candidates:
        raise ValueError(
            f"Dependency target {reference!r} does not match any feature."
        )
    raise ValueError(
        f"Dependency target {reference!r} is ambiguous: {', '.join(candidates)}"
    )


def build_model(df: pd.DataFrame):
    features = df[FEATURE_COLUMN].tolist()
    rows_by_feature = {
        row[FEATURE_COLUMN]: row.to_dict() for _, row in df.iterrows()
    }
    options = {
        feature: selected_control_options(rows_by_feature[feature])
        for feature in features
    }
    classes = {
        feature: classify_limitation(rows_by_feature[feature][LIMITATION_COLUMN])
        for feature in features
    }

    children_by_parent: Dict[str, List[str]] = defaultdict(list)
    parent_by_child: Dict[str, str] = {}
    for feature in features:
        if classes[feature] == "DEPENDENT":
            ref = dependency_target(rows_by_feature[feature][LIMITATION_COLUMN])
            parent = resolve_feature_name(ref, features)
            if parent == feature:
                raise ValueError(f"Feature {feature!r} cannot depend on itself.")
            parent_by_child[feature] = parent
            children_by_parent[parent].append(feature)

    # The supplied design uses one-level dependency families. Reject nested
    # dependencies to avoid silently generating incorrect combinations.
    nested = [p for p in children_by_parent if p in parent_by_child]
    if nested:
        raise ValueError(
            "Nested dependencies are not supported by this script: "
            + ", ".join(nested)
        )

    # Client-management features must remain isolated and cannot participate
    # in regular dependency families.
    invalid_client_dependencies = [
        f for f in features
        if classes[f] == "CLIENT_USER_MANAGEMENT"
        and (f in parent_by_child or f in children_by_parent)
    ]
    if invalid_client_dependencies:
        raise ValueError(
            "Client User Management features cannot be dependency-family members: "
            + ", ".join(invalid_client_dependencies)
        )

    return features, rows_by_feature, options, classes, children_by_parent, parent_by_child


def feature_component(feature: str, options: Mapping[str, List[str]], optional: bool):
    states = ([None] if optional else []) + options[feature]
    return [{feature: state} for state in states]


def dependency_component(
    parent: str,
    children: Sequence[str],
    options: Mapping[str, List[str]],
    parent_is_mandatory: bool,
) -> List[Dict[str, Optional[str]]]:
    component: List[Dict[str, Optional[str]]] = []

    if not parent_is_mandatory:
        absent = {parent: None}
        absent.update({child: None for child in children})
        component.append(absent)

    for parent_value in options[parent]:
        child_states = [
            [None, *options[child]]
            for child in children
        ]
        for selected_children in itertools.product(*child_states):
            state: Dict[str, Optional[str]] = {parent: parent_value}
            state.update(dict(zip(children, selected_children)))
            component.append(state)

    return component


def build_regular_components(
    features: Sequence[str],
    options: Mapping[str, List[str]],
    classes: Mapping[str, str],
    children_by_parent: Mapping[str, List[str]],
    parent_by_child: Mapping[str, str],
) -> List[List[Dict[str, Optional[str]]]]:
    components: List[List[Dict[str, Optional[str]]]] = []
    consumed = set()

    # Preserve source-file feature order for deterministic IDs.
    for feature in features:
        if classes[feature] == "CLIENT_USER_MANAGEMENT" or feature in consumed:
            continue

        if feature in parent_by_child:
            # A dependent child is generated with its parent.
            continue

        if feature in children_by_parent:
            children = children_by_parent[feature]
            if any(classes[c] == "CLIENT_USER_MANAGEMENT" for c in children):
                raise ValueError("Regular dependency families cannot contain client-only features.")
            components.append(
                dependency_component(
                    feature,
                    children,
                    options,
                    parent_is_mandatory=(classes[feature] == "MANDATORY"),
                )
            )
            consumed.add(feature)
            consumed.update(children)
            continue

        if classes[feature] == "DEPENDENT":
            continue

        components.append(
            feature_component(
                feature,
                options,
                optional=(classes[feature] != "MANDATORY"),
            )
        )
        consumed.add(feature)

    return components


def build_client_components(
    features: Sequence[str],
    options: Mapping[str, List[str]],
    classes: Mapping[str, str],
) -> List[List[Dict[str, Optional[str]]]]:
    client_features = [
        feature for feature in features
        if classes[feature] == "CLIENT_USER_MANAGEMENT"
    ]
    # Group them together: every client-management feature is selected.
    return [feature_component(feature, options, optional=False) for feature in client_features]


def component_product_count(components) -> int:
    return math.prod(len(component) for component in components) if components else 0


def iter_component_rows(
    components: Sequence[Sequence[Dict[str, Optional[str]]]],
) -> Iterator[Dict[str, Optional[str]]]:
    if not components:
        return
    for selected_states in itertools.product(*components):
        row: Dict[str, Optional[str]] = {}
        for state in selected_states:
            row.update(state)
        yield row


# =============================================================================
# Excel output
# =============================================================================
def add_combination_sheet(workbook, number: int, headers: Sequence[str]):
    ws = workbook.add_worksheet(f"Combo {number}")
    header_format = workbook.get_format_properties if False else None
    return ws


def write_workbook(source_path: Path, output_dir: Path, test_limit: Optional[int]) -> Path:
    run_started = time.perf_counter()
    log("Starting feature-control combination generator.")
    log(f"Source file: {source_path}")
    log(f"Output directory: {output_dir}")
    log("Step 1/6: Reading and validating the source workbook...")
    df = read_source(source_path)
    log(f"Source validation complete. Features found: {len(df):,}.")
    log("Step 2/6: Building control options and dependency families...")
    (
        features,
        rows_by_feature,
        options,
        classes,
        children_by_parent,
        parent_by_child,
    ) = build_model(df)

    log("Business-rule model created successfully.")

    regular_components = build_regular_components(
        features, options, classes, children_by_parent, parent_by_child
    )
    client_components = build_client_components(features, options, classes)

    regular_count = component_product_count(regular_components)
    client_count = component_product_count(client_components)
    full_count = regular_count + client_count
    write_count = min(full_count, test_limit) if test_limit is not None else full_count
    expected_sheets = math.ceil(write_count / DATA_ROWS_PER_COMBO_SHEET) if write_count else 0
    log(
        "Combination counts calculated: "
        f"{regular_count:,} regular + {client_count:,} client-management "
        f"= {full_count:,} total."
    )
    if test_limit is not None and test_limit < full_count:
        log(f"TEST MODE is active. Only the first {write_count:,} rows will be written.")
    log(f"Expected combination worksheets for this run: {expected_sheets}.")

    log("Step 3/6: Preparing the output workbook...")
    output_dir.mkdir(parents=True, exist_ok=True)
    dated_name = f"{OUTPUT_FILE_PREFIX}_{datetime.now():{DATE_FORMAT}}.xlsx"
    output_path = output_dir / dated_name

    workbook = xlsxwriter.Workbook(
        output_path,
        {
            "constant_memory": True,
            "default_date_format": "yyyy-mm-dd",
            "nan_inf_to_errors": True,
        },
    )
    workbook.use_zip64()
    workbook.set_properties(
        {
            "title": "Feature Control Combinations",
            "subject": "Valid feature and control combinations with dependencies",
            "author": "Generated by Python",
            "comments": "Source data copied from the configured source workbook.",
        }
    )

    # Reusable formats
    title_fmt = workbook.add_format(
        {"bold": True, "font_size": 16, "font_color": "#FFFFFF", "bg_color": "#1F4E78"}
    )
    section_fmt = workbook.add_format(
        {"bold": True, "font_color": "#FFFFFF", "bg_color": "#4472C4"}
    )
    header_fmt = workbook.add_format(
        {
            "bold": True,
            "font_color": "#FFFFFF",
            "bg_color": "#1F4E78",
            "text_wrap": True,
            "valign": "vcenter",
            "border": 0,
        }
    )
    input_fmt = workbook.add_format({"font_color": "#008000"})
    static_fmt = workbook.add_format({"font_color": "#666666"})
    note_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
    caution_fmt = workbook.add_format({"bg_color": "#FCE4D6", "font_color": "#9C5700"})
    integer_fmt = workbook.add_format({"num_format": "0"})

    log(f"Output workbook: {output_path}")
    log("Step 4/6: Writing the Summary and Source worksheets...")

    # Summary first
    summary = workbook.add_worksheet("Summary")
    summary.hide_gridlines(2)
    summary.set_column("A:A", 31)
    summary.set_column("B:B", 90)
    summary.merge_range("A1:B1", "Feature Control Combinations", title_fmt)
    summary.write("A3", "Workbook Overview", section_fmt)
    overview = [
        ("Source file", str(source_path)),
        ("Output file", output_path.name),
        ("Generated date", datetime.now().strftime("%Y-%m-%d")),
        ("Regular combinations", regular_count),
        ("Client User Management combinations", client_count),
        ("Total combinations", full_count),
        ("Rows written in this run", write_count),
    ]
    r = 3
    for label, value in overview:
        summary.write(r, 0, label, static_fmt)
        summary.write(r, 1, value, integer_fmt if isinstance(value, int) else input_fmt)
        r += 1

    if test_limit is not None and test_limit < full_count:
        summary.write(r, 0, "TEST OUTPUT", caution_fmt)
        summary.write(
            r,
            1,
            f"Only the first {test_limit:,} combinations were written because TEST_ROW_LIMIT is set.",
            caution_fmt,
        )
        r += 2

    r += 1
    summary.write(r, 0, "Worksheet Map", section_fmt)
    r += 1
    summary.write_row(r, 0, ["WORKSHEET", "COMBINATION_ID RANGE"], header_fmt)
    r += 1
    sheet_count = math.ceil(write_count / DATA_ROWS_PER_COMBO_SHEET) if write_count else 0
    for i in range(1, sheet_count + 1):
        start_id = (i - 1) * DATA_ROWS_PER_COMBO_SHEET + 1
        end_id = min(i * DATA_ROWS_PER_COMBO_SHEET, write_count)
        summary.write(r, 0, f"Combo {i}")
        summary.write(r, 1, f"{start_id:,} to {end_id:,}")
        r += 1
    summary.write(r, 0, "Source")
    summary.write(r, 1, "Copy of the source feature-control table used for this run.")
    r += 2

    summary.write(r, 0, "Combination Rules", section_fmt)
    r += 1
    rules = [
        "Each row is one unique combination; COMBINATION_ID is consecutive across Combo tabs.",
        "If View and one or more additional controls are available for a feature, every selected non-View control combination must include View. View alone remains valid.",
        "If View is unavailable, all non-empty combinations of the available controls are valid.",
        "Features marked Available in all packages are included in every regular combination.",
        "Features marked Only available under client user management are grouped together and are not combined with mandatory or regular features.",
        "A dependent feature can be selected only when its required feature is selected. All valid control options of the required feature are used.",
        "A blank feature cell means that the feature is not included in that combination.",
    ]
    for rule in rules:
        summary.write(r, 0, "•", static_fmt)
        summary.write(r, 1, rule, note_fmt)
        r += 1

    r += 1
    summary.write(r, 0, "Dependency Families", section_fmt)
    r += 1
    summary.write_row(r, 0, ["REQUIRED FEATURE", "DEPENDENT FEATURES"], header_fmt)
    r += 1
    for parent in features:
        if parent in children_by_parent:
            summary.write(r, 0, parent)
            summary.write(r, 1, ", ".join(children_by_parent[parent]), note_fmt)
            r += 1

    r += 1
    summary.write(r, 0, "Feature-Control Reference", section_fmt)
    r += 1
    summary.write_row(
        r,
        0,
        ["FEATURE", "AVAILABLE CONTROLS / LIMITATION / VALID SELECTED OPTIONS"],
        header_fmt,
    )
    r += 1
    for feature in features:
        available = ", ".join(
            c for c in CONTROL_COLUMNS if is_yes(rows_by_feature[feature][c])
        )
        limitation = rows_by_feature[feature][LIMITATION_COLUMN] or "None"
        detail = (
            f"Available controls: {available}\n"
            f"Limitation: {limitation}\n"
            f"Valid selected options ({len(options[feature])}): "
            + "; ".join(options[feature])
        )
        summary.write(r, 0, feature)
        summary.write(r, 1, detail, note_fmt)
        r += 1
    summary.freeze_panes(1, 0)

    # Source tab: exact cleaned table used by the generator.
    source_ws = workbook.add_worksheet("Source")
    source_ws.hide_gridlines(2)
    source_ws.freeze_panes(1, 0)
    source_ws.set_row(0, 32)
    source_ws.write_row(0, 0, df.columns.tolist(), header_fmt)
    for row_num, values in enumerate(df.itertuples(index=False, name=None), start=1):
        source_ws.write_row(row_num, 0, values, input_fmt)
    source_ws.autofilter(0, 0, len(df), len(df.columns) - 1)
    source_ws.set_column(0, 0, 38)
    source_ws.set_column(1, 4, 11)
    source_ws.set_column(5, 5, 48)

    log("Summary and Source worksheets completed.")
    log("Step 5/6: Generating and writing combination rows...")

    # Combination tabs
    headers = ["COMBINATION_ID", *features]
    current_ws = None
    current_sheet_number = 0
    row_in_sheet = 0
    combination_id = 0

    def start_combo_sheet(number: int):
        log(f"Opening Combo {number} for combination rows.")
        ws = workbook.add_worksheet(f"Combo {number}")
        ws.hide_gridlines(2)
        ws.freeze_panes(1, 1)
        ws.set_row(0, 45)
        ws.write_row(0, 0, headers, header_fmt)
        ws.set_column(0, 0, 16)
        ws.set_column(1, len(headers) - 1, 25)
        return ws

    def write_generated_rows(row_iterator, category: str):
        nonlocal current_ws, current_sheet_number, row_in_sheet, combination_id
        category_label = (
            "regular combinations"
            if category == "REGULAR"
            else "Client User Management combinations"
        )
        category_start_id = combination_id + 1
        log(f"Now processing {category_label}...")
        for selected in row_iterator:
            if test_limit is not None and combination_id >= test_limit:
                return False
            if current_ws is None or row_in_sheet >= DATA_ROWS_PER_COMBO_SHEET:
                if current_ws is not None:
                    current_ws.autofilter(0, 0, row_in_sheet, len(headers) - 1)
                current_sheet_number += 1
                current_ws = start_combo_sheet(current_sheet_number)
                row_in_sheet = 0

            combination_id += 1
            row_values = [combination_id] + [selected.get(f) or "" for f in features]
            current_ws.write_row(row_in_sheet + 1, 0, row_values)
            row_in_sheet += 1

            if combination_id % PROGRESS_EVERY_ROWS == 0 or combination_id == write_count:
                elapsed = time.perf_counter() - run_started
                percent = (combination_id / write_count * 100) if write_count else 100.0
                rate = combination_id / elapsed if elapsed else 0
                log(
                    f"Progress: {combination_id:,}/{write_count:,} rows "
                    f"({percent:.1f}%) | Current sheet: Combo {current_sheet_number} "
                    f"| Sheet rows: {row_in_sheet:,} | Average rate: {rate:,.0f} rows/sec "
                    f"| Elapsed: {format_elapsed(elapsed)}"
                )

        category_rows = combination_id - category_start_id + 1
        log(f"Completed {category_label}. Rows written in this phase: {max(category_rows, 0):,}.")
        return True

    finished_regular = write_generated_rows(
        iter_component_rows(regular_components), "REGULAR"
    )
    if finished_regular:
        write_generated_rows(
            iter_component_rows(client_components), "CLIENT_USER_MANAGEMENT"
        )

    if current_ws is not None:
        current_ws.autofilter(0, 0, row_in_sheet, len(headers) - 1)

    log("Step 6/6: Finalizing and closing the Excel workbook...")
    workbook.close()
    log("Workbook file finalized successfully.")

    expected = write_count
    if combination_id != expected:
        raise RuntimeError(
            f"Validation failed: wrote {combination_id:,} rows; expected {expected:,}."
        )

    total_elapsed = time.perf_counter() - run_started
    log("Validation complete. Output row count matches the expected count.")
    log(f"Created: {output_path}")
    log(f"Regular combinations: {regular_count:,}")
    log(f"Client User Management combinations: {client_count:,}")
    log(f"Rows written: {combination_id:,}")
    log(f"Combo worksheets: {current_sheet_number}")
    log(f"Total elapsed: {format_elapsed(total_elapsed)}")
    return output_path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate all valid feature-control combinations in Excel."
    )
    parser.add_argument(
        "--source",
        default=SOURCE_FILE_PATH,
        help="Path to User Package Capability Controls.xlsx",
    )
    parser.add_argument(
        "--output-dir",
        default=OUTPUT_DIRECTORY,
        help="Directory in which to create the output workbook",
    )
    parser.add_argument(
        "--test-row-limit",
        type=int,
        default=TEST_ROW_LIMIT,
        help="Optional maximum output rows for a test run",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    write_workbook(
        Path(args.source).expanduser(),
        Path(args.output_dir).expanduser(),
        args.test_row_limit,
    )
