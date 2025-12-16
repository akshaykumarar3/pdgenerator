-- PATIENT
INSERT INTO mockdata.patient_fhir (
  id, identifier, active, "name", telecom, gender, birth_date, address, marital_status, multiple_birth_boolean,
  contact_relationship, contact_name, contact_telecom, contact_address, contact_gender, contact_organization, 
  contact_period_start, contact_period_end, communication_language, communication_preferred, general_practitioner, managing_organization
) VALUES (
  0, 'MRN-SEED-000', true, 'John Doe', '555-000-0000', 'male', '1980-01-01', '123 Seed Lane', 'M', false,
  'self', 'Jane Doe', '555-000-0001', '123 Seed Lane', 'female', 'Family', '2020-01-01', '2030-01-01', 'en-US', true, 
  'Dr. Seed', 'Seed Medical Center'
);

-- CONDITIONS
INSERT INTO mockdata.condition_fhir (
  patient_id, identifier, clinical_status, verification_status, category, severity, code, subject, encounter, onset_date_time, recorded_date, recorder, asserter, note_text
) VALUES (
  0, 'COND-000-001', 'active', 'confirmed', 'problem-list-item', 'mild', '{"coding":[{"code":"I10","display":"Essential Hypertension"}]}', 'Patient/0', 'ENC-000-001',
  '2024-01-01', '2024-01-01', 'Dr. Seed', 'Dr. Seed', 'Stable on meds.'
);

-- MEDICATIONS
INSERT INTO mockdata.medication_fhir (
  patient_id, identifier, code, status, manufacturer, form, ingredient_item_codeable_concept, ingredient_is_active, ingredient_strength
) VALUES (
  0, 'MED-000-001', '197361', 'active', 'Pfizer', 'tablet', 'Amlodipine', true, '5mg'
);

-- ENCOUNTERS
INSERT INTO mockdata.encounter_fhir (
  patient_id, identifier, status, class_code, type, service_type, priority, subject, participant_individual, period_start, period_end, reason_code, location, service_provider
) VALUES (
  0, 'ENC-000-001', 'finished', 'AMB', 'checkup', 'General', 'routine', 'Patient/0', 'Dr. Seed', '2024-01-01 09:00', '2024-01-01 09:30', 'Z00.00', 'Room 1', 'Seed Medical Center'
);

-- OBSERVATIONS
INSERT INTO mockdata.observation_fhir (
  patient_id, identifier, status, category, code, subject, encounter, effective_date_time, issued, performer, value_quantity, value_string, interpretation, note
) VALUES (
  0, 'OBS-000-001', 'final', 'vital-signs', '85354-9', 'Patient/0', 'ENC-000-001', '2024-01-01 09:15', '2024-01-01 09:15', 'Nurse Seed', 0, '120/80', 'N', 'Normal BP'
);

-- PROCEDURES
INSERT INTO mockdata.procedure_fhir (
  patient_id, identifier, based_on, status, category, code, subject, encounter, performed_date_time, recorder, asserter, location, reason_code, reason_reference, note_text
) VALUES (
  0, 'PROC-000-001', 'SR-000', 'completed', 'surgical', '12345', 'Patient/0', 'ENC-000-001', '2024-01-01 10:00', 'Dr. Seed', 'Dr. Seed', 'OR 1', 'D123', 'COND-001', 'Routine procedure.'
);

-- DOCUMENTS
INSERT INTO mockdata.document_reference_fhir (
  patient_id, identifier, status, doc_status, type, category, subject, date, author, authenticator, custodian, description, content_attachment_title, context_encounter, context_event, context_period_start, context_period_end
) VALUES (
  0, 'DOC-000-001', 'current', 'final', '11506-3', 'clinical-note', 'Patient/0', '2024-01-01', 'Dr. Seed', 'Dr. Seed', 'Seed Med', 'Seed Note', 'Clinical_Summary_Seed.pdf', 'ENC-001', 'Event', '2024-01-01', '2024-01-01'
);

-- PATIENT INFO
INSERT INTO mockdata.patient_info (patient_id, payer_id) VALUES (0, 'J1113');
