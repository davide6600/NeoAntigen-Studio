-- NeoAntigen Studio PostgreSQL Core Schema
-- Phase 1 baseline entities from architecture requirements.

BEGIN;

CREATE TABLE IF NOT EXISTS patient (
    patient_id TEXT PRIMARY KEY,
    consent_status TEXT NOT NULL,
    project_id TEXT NOT NULL,
    clinical_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sample (
    sample_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patient(patient_id) ON DELETE CASCADE,
    sample_type TEXT NOT NULL,
    collection_date DATE,
    lims_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sequence_run (
    run_id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL REFERENCES sample(sample_id) ON DELETE CASCADE,
    object_store_path TEXT NOT NULL,
    md5 TEXT NOT NULL,
    platform TEXT,
    read_type TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS variant (
    variant_id TEXT PRIMARY KEY,
    sample_id TEXT NOT NULL REFERENCES sample(sample_id) ON DELETE CASCADE,
    chr TEXT NOT NULL,
    pos BIGINT NOT NULL,
    ref TEXT NOT NULL,
    alt TEXT NOT NULL,
    gene TEXT,
    effect TEXT,
    vaf DOUBLE PRECISION,
    depth INTEGER,
    clonal_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS peptide_candidate (
    peptide_id TEXT PRIMARY KEY,
    source_variant_id TEXT NOT NULL REFERENCES variant(variant_id) ON DELETE CASCADE,
    seq TEXT NOT NULL,
    hla_allele TEXT NOT NULL,
    binding_scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression_tpm DOUBLE PRECISION,
    clonality DOUBLE PRECISION,
    features_vector JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prediction_record (
    prediction_id TEXT PRIMARY KEY,
    peptide_id TEXT NOT NULL REFERENCES peptide_candidate(peptide_id) ON DELETE CASCADE,
    model_version TEXT NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    feature_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,
    pipeline_version TEXT NOT NULL,
    image_digest TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS experiment_label (
    label_id TEXT PRIMARY KEY,
    peptide_id TEXT NOT NULL REFERENCES peptide_candidate(peptide_id) ON DELETE CASCADE,
    assay_type TEXT NOT NULL,
    assay_id TEXT NOT NULL,
    result TEXT NOT NULL,
    score DOUBLE PRECISION,
    qc_flags JSONB NOT NULL DEFAULT '{}'::jsonb,
    uploaded_by TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT experiment_label_result_check CHECK (result IN ('positive', 'negative', 'ambiguous'))
);

CREATE TABLE IF NOT EXISTS tcr_record (
    tcr_id TEXT PRIMARY KEY,
    peptide_id TEXT REFERENCES peptide_candidate(peptide_id) ON DELETE SET NULL,
    cdr3_alpha TEXT,
    cdr3_beta TEXT NOT NULL,
    v_gene TEXT,
    j_gene TEXT,
    paired_cell_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS provenance_record (
    provenance_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    dataset_id TEXT,
    model_version TEXT,
    pipeline_version TEXT NOT NULL,
    image_digest TEXT NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_sample_patient_id ON sample(patient_id);
CREATE INDEX IF NOT EXISTS idx_variant_sample_id ON variant(sample_id);
CREATE INDEX IF NOT EXISTS idx_peptide_variant_id ON peptide_candidate(source_variant_id);
CREATE INDEX IF NOT EXISTS idx_prediction_peptide_id ON prediction_record(peptide_id);
CREATE INDEX IF NOT EXISTS idx_label_peptide_id ON experiment_label(peptide_id);
CREATE INDEX IF NOT EXISTS idx_tcr_peptide_id ON tcr_record(peptide_id);
CREATE INDEX IF NOT EXISTS idx_provenance_entity ON provenance_record(entity_type, entity_id);

COMMIT;
