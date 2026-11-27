"""Build or verify the committed Harbor Veterinary Clinic extracts.

The CSVs under data/clean are the fixture the checks load. This script is the
source for those files. ``--check`` fails when the files drift from the builder.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
TAX_RATE = Decimal("0.08")

PATIENT_FIELDS = [
    "patient_id",
    "name",
    "species",
    "breed",
    "date_of_birth",
    "sex",
    "status",
    "owner_name",
    "created_at",
]
VISIT_FIELDS = [
    "visit_id",
    "patient_id",
    "visit_date",
    "reason",
    "veterinarian",
    "status",
    "weight_kg",
    "temperature_c",
]
LAB_FIELDS = [
    "result_id",
    "visit_id",
    "patient_id",
    "test_code",
    "result_value",
    "unit",
    "abnormal_flag",
    "collected_at",
]
INVOICE_FIELDS = [
    "invoice_id",
    "visit_id",
    "patient_id",
    "amount",
    "tax_amount",
    "currency",
    "status",
    "issued_at",
    "paid_at",
]


def patient(pid, name, species, breed, dob, sex, status, owner, created):
    return {
        "patient_id": pid,
        "name": name,
        "species": species,
        "breed": breed,
        "date_of_birth": dob,
        "sex": sex,
        "status": status,
        "owner_name": owner,
        "created_at": created,
    }


def visit(vid, pid, day, reason, vet, status, weight="", temp=""):
    return {
        "visit_id": vid,
        "patient_id": pid,
        "visit_date": day,
        "reason": reason,
        "veterinarian": vet,
        "status": status,
        "weight_kg": weight,
        "temperature_c": temp,
    }


def lab(rid, vid, test_code, value, unit, flag):
    return {
        "result_id": rid,
        "visit_id": vid,
        "test_code": test_code,
        "result_value": value,
        "unit": unit,
        "abnormal_flag": flag,
    }


PATIENTS = [
    patient(
        "PAT-001",
        "Milo",
        "dog",
        "Labrador Retriever",
        "2018-03-14",
        "M",
        "active",
        "Sam Okonkwo",
        "2023-01-10",
    ),
    patient(
        "PAT-002",
        "Luna",
        "cat",
        "Domestic Shorthair",
        "2020-07-02",
        "F",
        "active",
        "Priya Shah",
        "2023-01-12",
    ),
    patient(
        "PAT-003",
        "Coco",
        "dog",
        "Mixed Breed",
        "2015-11-30",
        "F",
        "active",
        "Elena Vasquez",
        "2023-01-15",
    ),
    patient(
        "PAT-004",
        "Kiwi",
        "bird",
        "Cockatiel",
        "2021-04-19",
        "U",
        "active",
        "Noah Kim",
        "2023-02-01",
    ),
    patient(
        "PAT-005",
        "Thumper",
        "rabbit",
        "Holland Lop",
        "2022-01-08",
        "M",
        "active",
        "Grace Liu",
        "2023-02-03",
    ),
    patient(
        "PAT-006",
        "Ziggy",
        "reptile",
        "Bearded Dragon",
        "2019-09-21",
        "M",
        "active",
        "Omar Farouk",
        "2023-02-11",
    ),
    patient(
        "PAT-007",
        "Bella",
        "dog",
        "Beagle",
        "2016-05-27",
        "F",
        "active",
        "Hannah Berg",
        "2023-02-18",
    ),
    patient(
        "PAT-008",
        "Oliver",
        "cat",
        "Maine Coon",
        "2017-12-05",
        "M",
        "active",
        "Chris Dalton",
        "2023-03-01",
    ),
    patient(
        "PAT-009",
        "Daisy",
        "dog",
        "Golden Retriever",
        "2019-06-16",
        "F",
        "active",
        "Maya Chen",
        "2023-03-04",
    ),
    patient(
        "PAT-010",
        "Nibbles",
        "rabbit",
        "Mini Rex",
        "2021-08-23",
        "F",
        "active",
        "Leo Martins",
        "2023-03-09",
    ),
    patient(
        "PAT-011",
        "Rocky",
        "dog",
        "German Shepherd",
        "2014-02-11",
        "M",
        "active",
        "Anita Desai",
        "2023-03-14",
    ),
    patient(
        "PAT-012",
        "Misty",
        "cat",
        "Siamese",
        "2018-10-01",
        "F",
        "inactive",
        "Paul Nguyen",
        "2023-03-20",
    ),
    patient(
        "PAT-013",
        "Pepper",
        "dog",
        "French Bulldog",
        "2020-02-29",
        "M",
        "active",
        "Sofia Rossi",
        "2023-04-02",
    ),
    patient(
        "PAT-014",
        "Hazel",
        "bird",
        "Budgerigar",
        "2022-05-12",
        "F",
        "active",
        "Ivan Petrov",
        "2023-04-08",
    ),
    patient(
        "PAT-015",
        "Sheldon",
        "reptile",
        "Leopard Gecko",
        "2020-11-03",
        "M",
        "active",
        "Dana Brooks",
        "2023-04-15",
    ),
    patient(
        "PAT-016",
        "Willow",
        "cat",
        "Domestic Longhair",
        "2013-07-19",
        "F",
        "deceased",
        "Ruth Adler",
        "2023-04-22",
    ),
    patient(
        "PAT-017",
        "Bear",
        "dog",
        "Bernese Mountain Dog",
        "2018-01-25",
        "M",
        "active",
        "Tom Becker",
        "2023-05-01",
    ),
    patient(
        "PAT-018", "Maple", "dog", "Corgi", "2021-09-14", "F", "active", "Yuki Tanaka", "2023-05-06"
    ),
    patient(
        "PAT-019",
        "Simon",
        "cat",
        "Russian Blue",
        "2019-03-30",
        "M",
        "active",
        "Fiona Walsh",
        "2023-05-12",
    ),
    patient(
        "PAT-020",
        "Hopper",
        "rabbit",
        "Lionhead",
        "2022-12-01",
        "M",
        "active",
        "Ben Carter",
        "2023-05-20",
    ),
    patient(
        "PAT-021",
        "Pip",
        "bird",
        "Green Cheek Conure",
        "2021-01-17",
        "U",
        "active",
        "Clara Sousa",
        "2023-06-02",
    ),
    patient(
        "PAT-022",
        "Ace",
        "dog",
        "Border Collie",
        "2017-08-08",
        "M",
        "active",
        "Malik Jordan",
        "2023-06-09",
    ),
    patient(
        "PAT-023", "Nala", "cat", "Bengal", "2020-06-25", "F", "active", "Helen Park", "2023-06-18"
    ),
    patient(
        "PAT-024",
        "Moose",
        "dog",
        "Great Dane",
        "2016-12-12",
        "M",
        "active",
        "Victor Alvarez",
        "2023-07-01",
    ),
]

VISITS = [
    visit(
        "VIS-001",
        "PAT-001",
        "2024-01-08",
        "Annual wellness",
        "Dr. Chen",
        "completed",
        "32.4",
        "38.6",
    ),
    visit(
        "VIS-002",
        "PAT-001",
        "2024-04-02",
        "Limping on right fore",
        "Dr. Alvarez",
        "completed",
        "31.8",
        "38.9",
    ),
    visit(
        "VIS-003",
        "PAT-002",
        "2024-01-15",
        "Dental cleaning",
        "Dr. Chen",
        "completed",
        "4.6",
        "38.4",
    ),
    visit("VIS-004", "PAT-002", "2024-05-20", "Vomiting", "Dr. Patel", "completed", "4.4", "39.2"),
    visit(
        "VIS-005",
        "PAT-003",
        "2023-11-02",
        "Vaccination",
        "Dr. Alvarez",
        "completed",
        "18.2",
        "38.5",
    ),
    visit(
        "VIS-006", "PAT-003", "2024-03-18", "Skin allergy", "Dr. Chen", "completed", "18.0", "38.7"
    ),
    visit(
        "VIS-007",
        "PAT-004",
        "2024-02-10",
        "Beak and wing trim",
        "Dr. Patel",
        "completed",
        "0.090",
        "41.2",
    ),
    visit(
        "VIS-008",
        "PAT-005",
        "2024-02-28",
        "GI stasis check",
        "Dr. Chen",
        "completed",
        "1.60",
        "39.0",
    ),
    visit(
        "VIS-009", "PAT-006", "2024-01-22", "Annual exam", "Dr. Alvarez", "completed", "0.450", ""
    ),
    visit(
        "VIS-010",
        "PAT-007",
        "2023-12-14",
        "Ear infection",
        "Dr. Patel",
        "completed",
        "10.8",
        "38.9",
    ),
    visit(
        "VIS-011", "PAT-007", "2024-05-02", "Recheck ears", "Dr. Patel", "completed", "11.1", "38.4"
    ),
    visit("VIS-012", "PAT-008", "2024-02-05", "Dental", "Dr. Chen", "completed", "7.6", "38.5"),
    visit(
        "VIS-013", "PAT-009", "2024-03-01", "Limping", "Dr. Alvarez", "completed", "29.4", "38.8"
    ),
    visit("VIS-014", "PAT-009", "2024-03-22", "Recheck limp", "Dr. Alvarez", "cancelled", "", ""),
    visit(
        "VIS-015", "PAT-010", "2024-04-11", "Nail trim", "Dr. Patel", "completed", "1.52", "38.6"
    ),
    visit("VIS-016", "PAT-011", "2023-10-19", "Hip pain", "Dr. Chen", "completed", "36.5", "38.7"),
    visit(
        "VIS-017", "PAT-011", "2024-04-25", "Hip recheck", "Dr. Chen", "completed", "35.9", "38.5"
    ),
    visit(
        "VIS-018", "PAT-012", "2023-09-08", "Wellness", "Dr. Alvarez", "completed", "4.1", "38.3"
    ),
    visit(
        "VIS-019",
        "PAT-013",
        "2024-01-30",
        "Breathing check",
        "Dr. Patel",
        "completed",
        "12.2",
        "38.9",
    ),
    visit("VIS-020", "PAT-014", "2024-03-09", "Wellness", "Dr. Chen", "completed", "0.034", "41.6"),
    visit(
        "VIS-021", "PAT-015", "2024-02-17", "Shed check", "Dr. Alvarez", "completed", "0.062", ""
    ),
    visit(
        "VIS-022", "PAT-016", "2023-08-03", "Inappetence", "Dr. Patel", "completed", "3.8", "37.9"
    ),
    visit(
        "VIS-023",
        "PAT-016",
        "2023-08-20",
        "Euthanasia consult",
        "Dr. Chen",
        "completed",
        "3.6",
        "37.6",
    ),
    visit(
        "VIS-024",
        "PAT-017",
        "2024-01-12",
        "Mass removal followup",
        "Dr. Alvarez",
        "completed",
        "44.2",
        "38.6",
    ),
    visit(
        "VIS-025", "PAT-018", "2024-04-08", "Vaccination", "Dr. Patel", "completed", "11.7", "38.7"
    ),
    visit(
        "VIS-026", "PAT-019", "2024-02-21", "Urinary signs", "Dr. Chen", "completed", "4.5", "39.0"
    ),
    visit("VIS-027", "PAT-019", "2024-05-28", "Urinalysis recheck", "Dr. Chen", "no_show", "", ""),
    visit("VIS-028", "PAT-020", "2024-03-15", "Dental", "Dr. Alvarez", "completed", "1.45", "38.8"),
    visit(
        "VIS-029",
        "PAT-021",
        "2024-04-18",
        "Feather pluck",
        "Dr. Patel",
        "completed",
        "0.066",
        "41.0",
    ),
    visit("VIS-030", "PAT-022", "2024-01-25", "Lameness", "Dr. Chen", "completed", "19.8", "38.5"),
    visit(
        "VIS-031",
        "PAT-022",
        "2024-05-06",
        "Recheck lameness",
        "Dr. Chen",
        "completed",
        "20.1",
        "38.4",
    ),
    visit("VIS-032", "PAT-023", "2024-03-27", "Vomiting", "Dr. Patel", "completed", "4.3", "39.3"),
    visit(
        "VIS-033",
        "PAT-024",
        "2023-12-02",
        "Bloat watch",
        "Dr. Alvarez",
        "completed",
        "68.0",
        "38.8",
    ),
    visit(
        "VIS-034", "PAT-024", "2024-06-01", "Wellness", "Dr. Alvarez", "completed", "67.2", "38.6"
    ),
    visit("VIS-035", "PAT-005", "2024-05-15", "Sneezing", "Dr. Patel", "cancelled", "", ""),
    visit("VIS-036", "PAT-008", "2024-06-10", "Annual wellness", "Dr. Chen", "scheduled", "", ""),
    visit(
        "VIS-037", "PAT-013", "2024-06-14", "Vaccine booster", "Dr. Alvarez", "scheduled", "", ""
    ),
    visit(
        "VIS-038", "PAT-018", "2024-02-02", "Deworming", "Dr. Patel", "completed", "11.4", "38.5"
    ),
    visit("VIS-039", "PAT-010", "2024-01-05", "Wellness", "Dr. Chen", "completed", "1.48", "38.7"),
    visit("VIS-040", "PAT-003", "2024-06-12", "Annual exam", "Dr. Chen", "no_show", "", ""),
]

LABS = [
    lab("LAB-001", "VIS-001", "CBC", "12.4", "10^9/L", "N"),
    lab("LAB-002", "VIS-001", "CHEM", "1.1", "mg/dL", "N"),
    lab("LAB-003", "VIS-001", "HW", "0.0", "index", "N"),
    lab("LAB-004", "VIS-002", "CBC", "16.8", "10^9/L", "H"),
    lab("LAB-005", "VIS-004", "CHEM", "1.8", "mg/dL", "H"),
    lab("LAB-006", "VIS-004", "CBC", "18.2", "10^9/L", "H"),
    lab("LAB-007", "VIS-006", "CBC", "11.0", "10^9/L", "N"),
    lab("LAB-008", "VIS-010", "CBC", "14.2", "10^9/L", "N"),
    lab("LAB-009", "VIS-011", "CBC", "9.8", "10^9/L", "N"),
    lab("LAB-010", "VIS-013", "CBC", "13.1", "10^9/L", "N"),
    lab("LAB-011", "VIS-016", "CHEM", "1.4", "mg/dL", "N"),
    lab("LAB-012", "VIS-017", "CHEM", "1.3", "mg/dL", "N"),
    lab("LAB-013", "VIS-019", "CBC", "15.5", "10^9/L", "H"),
    lab("LAB-014", "VIS-022", "CHEM", "2.4", "mg/dL", "H"),
    lab("LAB-015", "VIS-022", "CBC", "6.1", "10^9/L", "L"),
    lab("LAB-016", "VIS-024", "CBC", "10.2", "10^9/L", "N"),
    lab("LAB-017", "VIS-026", "UA", "1.025", "sg", "H"),
    lab("LAB-018", "VIS-026", "CHEM", "2.1", "mg/dL", "H"),
    lab("LAB-019", "VIS-030", "CBC", "12.0", "10^9/L", "N"),
    lab("LAB-020", "VIS-032", "CHEM", "1.6", "mg/dL", "H"),
    lab("LAB-021", "VIS-032", "CBC", "17.4", "10^9/L", "H"),
    lab("LAB-022", "VIS-033", "CHEM", "1.2", "mg/dL", "N"),
    lab("LAB-023", "VIS-005", "FECAL", "0.0", "eggs/g", "N"),
    lab("LAB-024", "VIS-008", "FECAL", "120.0", "eggs/g", "H"),
    lab("LAB-025", "VIS-012", "T4", "28.0", "nmol/L", "N"),
    lab("LAB-026", "VIS-018", "T4", "18.0", "nmol/L", "N"),
    lab("LAB-027", "VIS-034", "CBC", "11.5", "10^9/L", "N"),
    lab("LAB-028", "VIS-038", "FECAL", "0.0", "eggs/g", "N"),
]

# Invoice ids follow this list. INV-001 is VIS-001, INV-003 is VIS-003, INV-005 is VIS-005.
INVOICE_PLAN = [
    ("VIS-001", "185.00", "paid", 2),
    ("VIS-002", "95.00", "paid", 3),
    ("VIS-003", "240.00", "paid", 3),
    ("VIS-004", "75.00", "issued", None),
    ("VIS-005", "120.00", "paid", 2),
    ("VIS-006", "80.00", "paid", 2),
    ("VIS-007", "55.00", "paid", 2),
    ("VIS-008", "150.00", "paid", 2),
    ("VIS-009", "70.00", "paid", 2),
    ("VIS-010", "110.00", "paid", 2),
    ("VIS-011", "64.00", "paid", 4),
    ("VIS-012", "200.00", "paid", 3),
    ("VIS-013", "140.00", "paid", 3),
    ("VIS-015", "45.00", "paid", 2),
    ("VIS-016", "175.00", "paid", 3),
    ("VIS-017", "90.00", "paid", 3),
    ("VIS-018", "160.00", "paid", 3),
    ("VIS-019", "125.00", "paid", 3),
    ("VIS-020", "48.00", "paid", 3),
    ("VIS-021", "60.00", "paid", 2),
    ("VIS-022", "210.00", "paid", 3),
    ("VIS-023", "350.00", "paid", 0),
    ("VIS-024", "420.00", "paid", 4),
    ("VIS-025", "88.00", "paid", 2),
    ("VIS-026", "190.00", "paid", 3),
    ("VIS-028", "130.00", "paid", 3),
    ("VIS-029", "72.00", "paid", 2),
    ("VIS-030", "155.00", "paid", 3),
    ("VIS-031", "99.00", "issued", None),
    ("VIS-032", "145.00", "paid", 3),
    ("VIS-033", "275.00", "paid", 3),
    ("VIS-034", "180.00", "issued", None),
    ("VIS-038", "54.00", "paid", 3),
    ("VIS-039", "66.00", "paid", 3),
]


def build_extracts(catalog: dict) -> dict[str, str]:
    patients = [dict(row) for row in PATIENTS]
    visits = [dict(row) for row in VISITS]
    labs = _labs_with_patients(visits)
    invoices = _invoices(visits)
    _validate(catalog, patients, visits, labs, invoices)
    return {
        "patients.csv": _csv(PATIENT_FIELDS, patients),
        "visits.csv": _csv(VISIT_FIELDS, visits),
        "lab_results.csv": _csv(LAB_FIELDS, labs),
        "invoices.csv": _csv(INVOICE_FIELDS, invoices),
    }


def _labs_with_patients(visits: list[dict[str, str]]) -> list[dict[str, str]]:
    by_visit = {row["visit_id"]: row for row in visits}
    rows = []
    for item in LABS:
        visit_row = by_visit[item["visit_id"]]
        rows.append(
            {
                **item,
                "patient_id": visit_row["patient_id"],
                "collected_at": visit_row["visit_date"],
            }
        )
    return rows


def _invoices(visits: list[dict[str, str]]) -> list[dict[str, str]]:
    by_visit = {row["visit_id"]: row for row in visits}
    rows = []
    for index, (visit_id, amount, status, offset) in enumerate(INVOICE_PLAN, start=1):
        visit_row = by_visit[visit_id]
        issued = date.fromisoformat(visit_row["visit_date"])
        paid = ""
        if status == "paid":
            paid = (issued + timedelta(days=offset)).isoformat()
        rows.append(
            {
                "invoice_id": f"INV-{index:03d}",
                "visit_id": visit_id,
                "patient_id": visit_row["patient_id"],
                "amount": amount,
                "tax_amount": _tax(amount),
                "currency": "USD",
                "status": status,
                "issued_at": issued.isoformat(),
                "paid_at": paid,
            }
        )
    return rows


def _tax(amount: str) -> str:
    value = (Decimal(amount) * TAX_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{value:.2f}"


def _validate(catalog: dict, patients, visits, labs, invoices) -> None:
    problems: list[str] = []

    def check(condition: bool, message: str) -> None:
        if not condition:
            problems.append(message)

    as_of = date.fromisoformat(str(catalog["as_of_date"]))
    min_birth = date.fromisoformat(str(catalog["min_birth_date"]))
    bounds = {
        species: (Decimal(str(window["min"])), Decimal(str(window["max"])))
        for species, window in catalog["weight_kg_by_species"].items()
    }
    temp_min = Decimal(str(catalog["temperature_c"]["min"]))
    temp_max = Decimal(str(catalog["temperature_c"]["max"]))
    temp_required = set(catalog["temperature_c"]["required_for_species"])
    accepted = {item["id"]: set(item["values"]) for item in catalog["checks"]["accepted_values"]}
    minimums = {item["table"]: item["min_rows"] for item in catalog["checks"]["row_counts"]}
    patients_by_id = {row["patient_id"]: row for row in patients}
    visits_by_id = {row["visit_id"]: row for row in visits}

    check(len(patients_by_id) == len(patients), "duplicate patient_id")
    check(len(visits_by_id) == len(visits), "duplicate visit_id")
    check(
        [row["patient_id"] for row in patients] == [f"PAT-{i:03d}" for i in range(1, 25)],
        "patient ids",
    )
    check(
        [row["visit_id"] for row in visits] == [f"VIS-{i:03d}" for i in range(1, 41)], "visit ids"
    )
    check([row["result_id"] for row in labs] == [f"LAB-{i:03d}" for i in range(1, 29)], "lab ids")
    check(
        minimums == {"patients": 24, "visits": 40, "lab_results": 28, "invoices": 34},
        "volume gates",
    )
    check(len(patients) == minimums["patients"], "patient volume")
    check(len(visits) == minimums["visits"], "visit volume")
    check(len(labs) == minimums["lab_results"], "lab volume")
    check(len(invoices) == minimums["invoices"], "invoice volume")

    completed = {row["visit_id"] for row in visits if row["status"] == "completed"}
    invoiced = {row["visit_id"] for row in invoices}
    check(completed == invoiced, "completed visits and invoices diverge")

    for row in patients:
        dob = date.fromisoformat(row["date_of_birth"])
        created = date.fromisoformat(row["created_at"])
        check(
            row["species"] in accepted["accepted.patients.species"], f"{row['patient_id']} species"
        )
        check(row["sex"] in accepted["accepted.patients.sex"], f"{row['patient_id']} sex")
        check(row["status"] in accepted["accepted.patients.status"], f"{row['patient_id']} status")
        check(min_birth <= dob <= as_of, f"{row['patient_id']} dob")
        check(dob <= created <= as_of, f"{row['patient_id']} created_at")

    for row in visits:
        owner = patients_by_id.get(row["patient_id"])
        check(owner is not None, f"{row['visit_id']} patient")
        check(row["status"] in accepted["accepted.visits.status"], f"{row['visit_id']} status")
        visit_day = date.fromisoformat(row["visit_date"])
        check(visit_day <= as_of, f"{row['visit_id']} after as_of")
        if owner is not None:
            check(
                visit_day >= date.fromisoformat(owner["date_of_birth"]),
                f"{row['visit_id']} before birth",
            )
        if row["weight_kg"]:
            if owner is None:
                check(False, f"{row['visit_id']} weight without a patient")
            else:
                weight = Decimal(row["weight_kg"])
                low, high = bounds[owner["species"]]
                check(low <= weight <= high, f"{row['visit_id']} weight {weight}")
        else:
            check(row["status"] != "completed", f"{row['visit_id']} completed without weight")
        if row["temperature_c"]:
            temp = Decimal(row["temperature_c"])
            check(temp_min <= temp <= temp_max, f"{row['visit_id']} temperature")
        elif row["status"] == "completed" and owner is not None:
            check(
                owner["species"] not in temp_required,
                f"{row['visit_id']} missing mammal temperature",
            )

    for row in labs:
        visit_row = visits_by_id[row["visit_id"]]
        check(row["patient_id"] == visit_row["patient_id"], f"{row['result_id']} patient")
        check(row["collected_at"] == visit_row["visit_date"], f"{row['result_id']} collected_at")
        check(
            row["test_code"] in accepted["accepted.lab_results.test_code"],
            f"{row['result_id']} test",
        )
        check(
            row["abnormal_flag"] in accepted["accepted.lab_results.abnormal_flag"],
            f"{row['result_id']} flag",
        )
        check(Decimal(row["result_value"]) >= 0, f"{row['result_id']} value")
        check(visit_row["status"] == "completed", f"{row['result_id']} visit status")

    for row in invoices:
        visit_row = visits_by_id[row["visit_id"]]
        check(row["patient_id"] == visit_row["patient_id"], f"{row['invoice_id']} patient")
        check(row["issued_at"] == visit_row["visit_date"], f"{row['invoice_id']} issued_at")
        check(row["currency"] == "USD", f"{row['invoice_id']} currency")
        check(row["status"] in {"paid", "issued"}, f"{row['invoice_id']} status")
        amount = Decimal(row["amount"])
        tax = Decimal(row["tax_amount"])
        check(amount > 0 and tax >= 0 and tax <= amount, f"{row['invoice_id']} amounts")
        check(tax == Decimal(_tax(row["amount"])), f"{row['invoice_id']} tax math")
        if row["status"] == "paid":
            paid = date.fromisoformat(row["paid_at"])
            issued = date.fromisoformat(row["issued_at"])
            check(issued <= paid <= as_of, f"{row['invoice_id']} paid_at")
        else:
            check(row["paid_at"] == "", f"{row['invoice_id']} paid_at should be empty")

    if problems:
        raise SystemExit("Fixture builder failed validation:\n- " + "\n- ".join(problems))


def _csv(fieldnames: list[str], rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    return buffer.getvalue()


def _load_catalog() -> dict:
    return yaml.safe_load((ROOT / "config" / "checks.yaml").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify data/clean CSV extracts.")
    parser.add_argument("--write", action="store_true", help="Write data/clean CSV files.")
    parser.add_argument(
        "--check", action="store_true", help="Fail if data/clean drifts from the builder."
    )
    args = parser.parse_args(argv)
    if args.write and args.check:
        print("Choose either --write or --check.", file=sys.stderr)
        return 2
    extracts = build_extracts(_load_catalog())
    if args.write:
        CLEAN.mkdir(parents=True, exist_ok=True)
        for name, text in extracts.items():
            (CLEAN / name).write_text(text, encoding="utf-8")
        print(f"Wrote {len(extracts)} files to {CLEAN.relative_to(ROOT)}")
        return 0
    drifted = []
    for name, text in extracts.items():
        path = CLEAN / name
        if not path.is_file() or path.read_text(encoding="utf-8") != text:
            drifted.append(name)
    if drifted:
        print("Extracts differ from the builder: " + ", ".join(drifted), file=sys.stderr)
        print("Run python scripts/build_sample_data.py --write", file=sys.stderr)
        return 1
    print("Extracts match the builder.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
