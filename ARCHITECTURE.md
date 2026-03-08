Clinical Data Generator — System Architecture (v3)1. OverviewThe Clinical Data Generator is an AI-driven pipeline that produces realistic synthetic healthcare data for testing Prior Authorization (PA) workflows.The system generates:Patient Personas: FHIR-style patient records.Clinical Reports: Consult notes, imaging reports, and lab reports.Clinical Summaries: Aggregated case overviews.Outputs are rendered as structured PDFs designed for OCR evaluation, LLM document understanding, and Prior Authorization testing pipelines.2. Core Architectural Principle: Single Source of TruthAll generated documents must derive from a single structured patient record called patient_state. This object represents the canonical patient data model and prevents inconsistent patient information across documents.Patient State Hierarchypatient_stateidentifiersdemographicsprovidersdiagnosesmedicationsencountersprocedure_requestfacilityConstraint: Every module reads from this object. Documents must never "hallucinate" or invent patient attributes independently.3. System Architecturegraph TD
    UserInput["User Input / UI"] --> Generator["Workflow Orchestrator (generator.py)"]
    Generator --> DataLoader["Case Loader (data_loader.py)"]
    Generator --> PatientState["Patient State Builder"]

    PatientState --> AIEngine["AI Engine (ai_engine.py)"]
    AIEngine --> Documents["Clinical Document Generator"]
    
    Documents --> Validator["Document Validator (doc_validator.py)"]
    Validator --> PDFFactory["PDF Renderer (pdf_generator.py)"]
    PDFFactory --> Output["generated_output/"]
    
    Generator --> Search["Search Engine (search_engine.py)"]
    Generator --> History["History Manager (history_manager.py)"]
    Generator --> DB["Patient Database (core/patient_db.py)"]
4. Patient State LayerPurposeThe Patient State Layer ensures that all documents reference the same patient data, preventing:Conflicting demographics.Mismatched MRNs.Inconsistent providers.Timeline drift.Schema Example{
  "patient_id": "212",
  "identifiers": {
    "mrn": "MRN-212-2026",
    "insurance_member_id": "MBR-999999",
    "policy_number": "POL-2025-000001"
  },
  "demographics": {
    "name": "Sandor Clegane",
    "dob": "1965-03-23",
    "gender": "Male",
    "height": "6 ft 5 in",
    "weight": "250 lbs"
  },
  "providers": [
    {
      "name": "Dr Jane Smith",
      "specialty": "Cardiology",
      "npi": "1234567890"
    }
  ],
  "diagnoses": [
    {
      "code": "I25.10",
      "condition": "Atherosclerotic heart disease"
    }
  ],
  "requested_procedure": {
    "procedure_name": "Cardiac CT Angiography",
    "cpt_code": "75574",
    "expected_date": "2026-03-15"
  }
}
5. Generation WorkflowStepPhaseResponsibility1User InputReceives Patient ID, feedback, and generation mode.2Case Data LoadingLoads context from core/UAT Plan.xlsx (diagnoses, procedure requests).3Patient State ConstructionBuilds the deterministic patient_state object from Excel, DB, and AI persona fields.4Clinical Data GenerationAI generates narratives/justifications based on the patient_state context.5Document Validationdoc_validator.py checks for missing sections and structural integrity; when rendering JSON to PDF text it uses template-driven section order and flattens nested dicts for intensive, audit-ready output.6PDF Renderingpdf_generator.py handles layout, clinical tables, and metadata.7Output StorageSaves artifacts to generated_output/ with IDs and timestamps.6. Temporal ConsistencyMedical events follow a realistic clinical timeline relative to the requested procedure date.EventTimelineMedical History6 months – 5 years before procedureEncounters1 – 12 weeks before procedureLab Tests1 – 4 weeks before procedureProcedure7 – 90 days in the futureUtility functions in generator.py: calculate_procedure_date(), calculate_encounter_date().7. Duplicate PreventionThe system performs a pre-generation scan of existing outputs:Reads files in the patient-specific folder.Extracts existing document titles.Passes titles to the AI engine as "exclusion list."Prevents duplicate titles like Doc-221-001_CT_Scan.pdf unless explicitly required.8. Modular ComponentsAI Prompt Architecture (prompts.py)All prompts are centralized to allow for easier customization and consistent instructions (e.g., SYSTEM_PROMPT, get_clinical_data_prompt).Search Engine (search_engine.py)Retrieves external medical coding (CPT/ICD-10) and policy criteria from AAPC or CMS.Caching: .search_cache/TTL: 24 hoursPatient Database (core/patient_db.py)Persistent storage of generated personas in core/patients_db.json to preserve consistency across different execution runs.9. Directory Structurepdgenerator/
├── cred/                       # .env and credentials
├── core/                       # Patient DB, Excel UAT plans
├── templates/                  # PDF and Document templates
├── generated_output/           # Final artifacts
│   ├── persona/
│   ├── patient-reports/
│   ├── summary/
│   └── logs/
├── generator.py                # Main Orchestrator
├── ai_engine.py                # LLM Interaction Layer
├── prompts.py                  # Centralized Prompt Library
├── pdf_generator.py            # Rendering Engine
├── search_engine.py            # Web retrieval & Caching
├── doc_validator.py            # Structural Validation & template-driven formatting
├── data_loader.py              # File I/O for Case Data
├── history_manager.py          # Session tracking
├── purge_manager.py            # Cleanup utilities
└── remove_persona.py           # Deep persona removal utility
10. Future ExtensionsPatient State Manager: A dedicated class to handle state mutations.Timeline Engine: Deterministic scheduling of all historical medical events.Planning Layer: A pre-generation step to outline all needed documents before calling the AI.11. SummaryThe Clinical Data Generator (v3) ensures Clinical Coherence by enforcing a deterministic patient_state layer. By combining structured data models with controlled LLM generation, the pipeline produces high-quality synthetic datasets suitable for rigorous healthcare software testing.
