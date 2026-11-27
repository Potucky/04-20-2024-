-- Permissive staging tables for the Harbor Veterinary Clinic extract.
-- Column types are real dates and numbers so the checks can compare them.
-- Primary keys, foreign keys, and NOT NULL are not enforced at load time.
-- The check suite is the gate, which is the usual split for a raw or
-- staging warehouse layer before a stricter modeled layer.

CREATE TABLE patients (
    patient_id VARCHAR,
    name VARCHAR,
    species VARCHAR,
    breed VARCHAR,
    date_of_birth DATE,
    sex VARCHAR,
    status VARCHAR,
    owner_name VARCHAR,
    created_at DATE
);

CREATE TABLE visits (
    visit_id VARCHAR,
    patient_id VARCHAR,
    visit_date DATE,
    reason VARCHAR,
    veterinarian VARCHAR,
    status VARCHAR,
    weight_kg DOUBLE,
    temperature_c DOUBLE
);

CREATE TABLE lab_results (
    result_id VARCHAR,
    visit_id VARCHAR,
    patient_id VARCHAR,
    test_code VARCHAR,
    result_value DOUBLE,
    unit VARCHAR,
    abnormal_flag VARCHAR,
    collected_at DATE
);

CREATE TABLE invoices (
    invoice_id VARCHAR,
    visit_id VARCHAR,
    patient_id VARCHAR,
    amount DECIMAL(12, 2),
    tax_amount DECIMAL(12, 2),
    currency VARCHAR,
    status VARCHAR,
    issued_at DATE,
    paid_at DATE
);
