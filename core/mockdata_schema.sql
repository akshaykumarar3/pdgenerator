CREATE SCHEMA IF NOT EXISTS mockdata;

-- mockdata.insurance_payers definition

CREATE TABLE mockdata.insurance_payers (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    payer_name text NOT NULL,
    payer_id_availity text NULL,
    contact_phone text NULL,
    contact_email text NULL,
    website text NULL,
    submission_methods jsonb NULL,
    submission_guidelines jsonb NULL,
    is_active bool DEFAULT true NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT insurance_payers_payer_id_availity_key UNIQUE (payer_id_availity),
    CONSTRAINT insurance_payers_payer_name_key UNIQUE (payer_name),
    CONSTRAINT insurance_payers_pkey PRIMARY KEY (id)
);
CREATE INDEX idx_insurance_payers_name ON mockdata.insurance_payers USING btree (payer_name);


-- mockdata.condition_fhir definition

CREATE TABLE mockdata.condition_fhir (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    identifier varchar(255) NULL,
    clinical_status text NULL,
    verification_status text NULL,
    category text NULL,
    severity text NULL,
    code text NULL,
    body_site text NULL,
    subject varchar(255) NULL,
    encounter varchar(255) NULL,
    onset_date_time timestamptz NULL,
    onset_age varchar(255) NULL,
    onset_period_start timestamptz NULL,
    onset_period_end timestamptz NULL,
    onset_range_low int4 NULL,
    onset_range_high int4 NULL,
    onset_string varchar(255) NULL,
    abatement_date_time timestamptz NULL,
    abatement_age varchar(255) NULL,
    abatement_period_start timestamptz NULL,
    abatement_period_end timestamptz NULL,
    abatement_range_low int4 NULL,
    abatement_range_high int4 NULL,
    abatement_string varchar(255) NULL,
    recorded_date timestamptz NULL,
    recorder varchar(255) NULL,
    asserter varchar(255) NULL,
    stage_summary text NULL,
    stage_assessment text NULL,
    stage_type varchar(255) NULL,
    evidence_code text NULL,
    evidence_detail text NULL,
    note_author varchar(255) NULL,
    note_time timestamptz NULL,
    note_text text NULL,
    CONSTRAINT condition_fhir_pkey PRIMARY KEY (id)
);


-- mockdata.document_reference_fhir definition

CREATE TABLE mockdata.document_reference_fhir (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    identifier varchar(255) NULL,
    status varchar(50) NULL,
    doc_status varchar(50) NULL,
    "type" text NULL,
    category text NULL,
    subject varchar(255) NULL,
    "date" timestamptz NULL,
    author varchar(255) NULL,
    authenticator varchar(255) NULL,
    custodian varchar(255) NULL,
    relates_to_code varchar(50) NULL,
    relates_to_target varchar(255) NULL,
    description text NULL,
    security_label text NULL,
    content_attachment_content_type varchar(255) NULL,
    content_attachment_language varchar(50) NULL,
    content_attachment_data text NULL,
    content_attachment_url text NULL,
    content_attachment_size int4 NULL,
    content_attachment_hash varchar(255) NULL,
    content_attachment_title text NULL,
    content_attachment_creation timestamptz NULL,
    content_format_code varchar(255) NULL,
    context_encounter varchar(255) NULL,
    context_event text NULL,
    context_period_start timestamptz NULL,
    context_period_end timestamptz NULL,
    context_facility_type varchar(255) NULL,
    context_practice_setting varchar(255) NULL,
    context_source_patient_info varchar(255) NULL,
    context_related varchar(255) NULL,
    CONSTRAINT document_reference_fhir_pkey PRIMARY KEY (id)
);


-- mockdata.encounter_fhir definition

CREATE TABLE mockdata.encounter_fhir (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    identifier varchar(255) NULL,
    status varchar(50) NULL,
    class_code text NULL,
    "type" text NULL,
    service_type varchar(255) NULL,
    priority varchar(50) NULL,
    subject varchar(255) NULL,
    episode_of_care varchar(255) NULL,
    based_on varchar(255) NULL,
    participant_type varchar(255) NULL,
    participant_individual varchar(255) NULL,
    appointment varchar(255) NULL,
    period_start timestamptz NULL,
    period_end timestamptz NULL,
    length int4 NULL,
    reason_code text NULL,
    reason_reference text NULL,
    diagnosis_condition varchar(255) NULL,
    diagnosis_use varchar(50) NULL,
    diagnosis_rank int4 NULL,
    hospitalization_pre_admission_identifier varchar(255) NULL,
    hospitalization_origin varchar(255) NULL,
    hospitalization_admit_source varchar(255) NULL,
    hospitalization_re_admission varchar(255) NULL,
    hospitalization_diet_preference text NULL,
    hospitalization_special_courtesy text NULL,
    hospitalization_special_arrangement text NULL,
    hospitalization_destination varchar(255) NULL,
    hospitalization_discharge_disposition varchar(255) NULL,
    "location" varchar(255) NULL,
    service_provider varchar(255) NULL,
    part_of varchar(255) NULL,
    CONSTRAINT encounter_fhir_pkey PRIMARY KEY (id)
);


-- mockdata.medication_fhir definition

CREATE TABLE mockdata.medication_fhir (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    identifier varchar(255) NULL,
    code text NULL,
    status varchar(50) NULL,
    manufacturer varchar(255) NULL,
    form varchar(255) NULL,
    amount_numerator_value int4 NULL,
    amount_numerator_unit varchar(50) NULL,
    amount_denominator_value int4 NULL,
    amount_denominator_unit varchar(50) NULL,
    ingredient_item_codeable_concept text NULL,
    ingredient_item_reference varchar(255) NULL,
    ingredient_is_active bool NULL,
    ingredient_strength varchar(255) NULL,
    batch_lot_number varchar(255) NULL,
    batch_expiration_date timestamptz NULL,
    CONSTRAINT medication_fhir_pkey PRIMARY KEY (id)
);


-- mockdata.observation_fhir definition

CREATE TABLE mockdata.observation_fhir (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    identifier varchar(255) NULL,
    based_on text NULL,
    part_of text NULL,
    status varchar(50) NULL,
    category text NULL,
    code text NULL,
    subject varchar(255) NULL,
    focus varchar(255) NULL,
    encounter varchar(255) NULL,
    effective_date_time timestamptz NULL,
    effective_period_start timestamptz NULL,
    effective_period_end timestamptz NULL,
    effective_timing varchar(255) NULL,
    effective_instant timestamptz NULL,
    issued timestamptz NULL,
    performer varchar(255) NULL,
    value_quantity varchar(255) NULL,
    value_codeable_concept text NULL,
    value_string text NULL,
    value_boolean varchar(50) NULL,
    value_integer varchar(255) NULL,
    value_range varchar(255) NULL,
    value_ratio varchar(255) NULL,
    value_sampled_data text NULL,
    value_time varchar(255) NULL,
    value_date_time timestamptz NULL,
    value_period varchar(255) NULL,
    data_absent_reason text NULL,
    interpretation text NULL,
    note text NULL,
    body_site text NULL,
    "method" varchar(255) NULL,
    specimen varchar(255) NULL,
    device varchar(255) NULL,
    reference_range text NULL,
    has_member text NULL,
    derived_from text NULL,
    component text NULL,
    CONSTRAINT observation_fhir_pkey PRIMARY KEY (id)
);


-- mockdata.patient_fhir definition

CREATE TABLE mockdata.patient_fhir (
    id serial4 NOT NULL,
    identifier text NULL,
    active bool DEFAULT true NULL,
    "name" text NULL,
    telecom text NULL,
    gender varchar(50) NULL,
    birth_date date NULL,
    address text NULL,
    marital_status text NULL,
    multiple_birth_boolean bool NULL,
    multiple_birth_integer int4 NULL,
    photo text NULL,
    contact_relationship varchar(255) NULL,
    contact_name varchar(255) NULL,
    contact_telecom varchar(255) NULL,
    contact_address text NULL,
    contact_gender varchar(50) NULL,
    contact_organization varchar(255) NULL,
    contact_period_start timestamptz NULL,
    contact_period_end timestamptz NULL,
    communication_language varchar(50) NULL,
    communication_preferred bool NULL,
    general_practitioner varchar(255) NULL,
    managing_organization varchar(255) NULL,
    link_other_patient varchar(255) NULL,
    link_type varchar(50) NULL,
    CONSTRAINT patient_fhir_pkey PRIMARY KEY (id)
);


-- mockdata.procedure_fhir definition

CREATE TABLE mockdata.procedure_fhir (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    identifier varchar(255) NULL,
    instantiates_canonical text NULL,
    instantiates_uri text NULL,
    based_on text NULL,
    part_of text NULL,
    status varchar(50) NULL,
    status_reason varchar(255) NULL,
    category text NULL,
    code text NULL,
    subject varchar(255) NULL,
    encounter varchar(255) NULL,
    performed_date_time timestamptz NULL,
    performed_string varchar(255) NULL,
    recorder varchar(255) NULL,
    asserter varchar(255) NULL,
    performer_function varchar(255) NULL,
    performer_actor varchar(255) NULL,
    performer_on_behalf_of varchar(255) NULL,
    "location" varchar(255) NULL,
    reason_code text NULL,
    reason_reference text NULL,
    body_site text NULL,
    outcome varchar(255) NULL,
    report varchar(255) NULL,
    complication text NULL,
    complication_detail text NULL,
    follow_up text NULL,
    note_author varchar(255) NULL,
    note_time timestamptz NULL,
    note_text text NULL,
    focal_device_action varchar(255) NULL,
    focal_device_manipulated varchar(255) NULL,
    used_reference varchar(255) NULL,
    used_code text NULL,
    CONSTRAINT procedure_fhir_pkey PRIMARY KEY (id)
);

-- Create the patient_info table
CREATE TABLE IF NOT EXISTS mockdata.patient_info (
    id serial4 NOT NULL,
    patient_id int4 NOT NULL,
    payer_id varchar(255) NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    CONSTRAINT patient_info_pkey PRIMARY KEY (id)
);

-- Add the foreign key relationship to patient_fhir
-- This ensures that a patient_id in this table must exist in the patient_fhir table
ALTER TABLE mockdata.patient_info 
    ADD CONSTRAINT patient_info_patient_id_fkey 
    FOREIGN KEY (patient_id) 
    REFERENCES mockdata.patient_fhir(id) 
    ON DELETE CASCADE;

-- Optional: Create an index on patient_id for faster lookups since it will be a common join key
CREATE INDEX idx_patient_info_patient_id ON mockdata.patient_info(patient_id);



-- mockdata.condition_fhir foreign keys

ALTER TABLE mockdata.condition_fhir ADD CONSTRAINT condition_fhir_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES mockdata.patient_fhir(id) ON DELETE CASCADE;


-- mockdata.document_reference_fhir foreign keys

ALTER TABLE mockdata.document_reference_fhir ADD CONSTRAINT document_reference_fhir_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES mockdata.patient_fhir(id) ON DELETE CASCADE;


-- mockdata.encounter_fhir foreign keys

ALTER TABLE mockdata.encounter_fhir ADD CONSTRAINT encounter_fhir_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES mockdata.patient_fhir(id) ON DELETE CASCADE;


-- mockdata.medication_fhir foreign keys

ALTER TABLE mockdata.medication_fhir ADD CONSTRAINT medication_fhir_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES mockdata.patient_fhir(id) ON DELETE CASCADE;


-- mockdata.observation_fhir foreign keys

ALTER TABLE mockdata.observation_fhir ADD CONSTRAINT observation_fhir_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES mockdata.patient_fhir(id) ON DELETE CASCADE;


-- mockdata.procedure_fhir foreign keys

ALTER TABLE mockdata.procedure_fhir ADD CONSTRAINT procedure_fhir_patient_id_fkey FOREIGN KEY (patient_id) REFERENCES mockdata.patient_fhir(id) ON DELETE CASCADE;
