# Clinical Data Generator (v5.2)

> **Automated Synthetic Healthcare Data Pipeline**
> Generates high-fidelity clinical PDFs and FHIR-compliant personas for testing Prior Authorization workflows.

---

## 🚀 Quick Start

### 🏁 Platform-Independent Launch

To simplify setup, we provide launch scripts for both Windows and macOS/Linux.

#### 1. Start the API Server (Web UI)

The Web UI is the recommended way to use the generator.

- **Windows**: Run `run_api.bat`
- **macOS / Linux**: Run `chmod +x run_api.sh && ./run_api.sh`

> **Note**: The default port is `410` (to avoid macOS port 5000 conflicts). Open either UI in your browser:
>
> - **Dark UI**: `ui/index.html` (Material You dark theme)
> - **Light UI**: `ui/index2.html` (Command Center light theme)

#### 2. Start the CLI (Terminal Mode)

- **Windows**: Run `run.bat`
- **macOS / Linux**: Run `chmod +x run.sh && ./run.sh`
- **Direct** (any OS): `python run.py`

---

### 📦 Manual Setup (If scripts fail)

1. **Environment**: Python 3.10+
2. **Virtual Env**: `python -m venv venv`
3. **Dependencies**: `pip install -r requirements.txt`
4. **Credentials**: Copy `core/.env.example` to `cred/.env` and add your API keys.

#### Interactive Commands

| Command | Description | Example |
| :--- | :--- | :--- |
| **`[Patient ID]`** | Generates data for a single patient. | `210` or `237` |
| **`[ID]-[feedback]`** | Generates data with AI feedback. | `225-use kidney transplant` |
| **`[ID],[ID],[ID]`** | Batch mode for specific IDs. | `221,222,223` |
| **`*`** | Runs Batch Mode for all missing patients. | `*` |
| **`q`** / **`exit`** | Quits the application. | `q` |

#### Persona Removal CLI

To completely wipe out all generated history, data, and database entries for a specific Persona, you can run the standalone remove utility:

```bash
python remove_persona.py <Patient_ID>
# Or to skip confirmation:
python remove_persona.py -f <Patient_ID>
```

---

## 🖥️ Web UI — 3-Silo Layout

Two interface files in `ui/` share the same **3-silo layout**:

| File | Theme |
|------|-------|
| `index.html` | Dark (Material You) |
| `index2.html` | Light (Command Center) |

### Silo 1 — Patient & Case Info (Left)

- Patient selector dropdown (all IDs from Excel plan)
- Identity summary: DOB, Gender, Provider
- UAT case details: Test Case #, Department, Procedure / CPT code
- Expected outcome with **approval** (green) / **denial** (red) color coding
- Primary diagnosis

### Silo 2 — Clinical Detail Tabs (Center)

7 inline tabs (no modal required):

- **Medications** — brand, generic, dosage, status, prescriber
- **Allergies** — allergen, reaction, severity with warnings
- **Therapy** — CPT code, provider, frequency, status
- **Procedures** — procedure, date, provider, facility
- **Encounters** — type, date, provider, chief complaint
- **Imaging** — type, date, facility, findings
- **Labs** — type, date, results

### Silo 3 — Generate & Documents (Right)

- **Feedback textarea** — optional AI instructions
- **Doc type checkboxes** — Persona / Reports / Summary
- **Generate button** → `POST /api/generate` → live log polling
- **Live log panel** — streams real-time generation output
- **Document list** with type filter tabs (All / P / R / S) + inline PDF links
- **Batch Modal** — header button opens patient checklist → `POST /api/generate_all`

### Clinical Data Input Tabs

Enter structured clinical history that will be locked into the patient persona and incorporated into all generated documents:

| Tab | Fields |
| :--- | :--- |
| **Medications** | Brand, Generic/Dosage, Qty, Prescribed By, Status, Start, End, Reason |
| **Allergies** | Allergen, Type, Reaction, Severity, Onset Date |
| **Vaccinations** | Name, Type, Date, Administered By, Dose #, Reason |
| **Therapy & Behavioral Health** | Type, Provider, Facility, Frequency, Status, Dates, Reason, Notes |

All rows are addable, removable, and pre-filled from an existing patient's stored record.

### Live Generation Log

A real-time console streams progress events as the AI runs, including milestones for persona creation, document generation, and any fixes applied.

### Generated Output

After generation, all documents (Reports, Persona, Summary) are listed as clickable links that open the PDF inline in a new browser tab.
You will also see a **💾 Save as Template** button next to each document, which allows you to save that specific document as the global baseline template (archiving any previous template automatically).

### Changes Summary Panel

After each run, a 2×2 summary panel is shown:

- **What Was Requested** — Sections chosen, data counts, PA optimize flag, feedback preview
- **What Was Produced** — Patient name, document count, status
- **Key Events** — Milestone log entries
- **AI Changes Narrative** — The AI's own description of what changed

---

## ✨ Key Features

### Generation Control & Batching

- **Batch Generation**: Support for processing multiple patients simultaneously. The system builds a queue and processes records sequentially while maintaining strict isolation.
- **Cancel/Abort with Auto-Rollback**: Safely halt any long-running generation (single or batch) at any time. If a job is aborted mid-flight, the system automatically triggers a rollback to restore the previous state of the patient's documents and persona database, preventing corrupted or partial outputs.

### Prior Authorization Workflow Support

- **PA Optimization**: Toggle to automatically strengthen clinical justifications for likely-rejected cases
- **Complete PA Request Forms**: Requesting provider, urgency level, clinical justification, ICD-10 diagnoses, previous treatments, expected outcome
- **Future Procedure Dates**: Procedure dates set 7–90 days in the future for realistic PA workflows

### Clinical Data Sections

Medications, allergies, vaccinations, therapies, and behavioral notes are:

- Captured via the interactive UI
- Stored persistently in the patient database
- Rendered into the **Persona PDF** as structured tables
- Locked for existing patients to ensure consistency across regenerations

### Texas Geographic Constraint

All generated patient data — demographics, providers, facilities, addresses — is constrained to **Texas, USA** with realistic TX hospital names, addresses, and ZIP codes.

### Temporal Consistency

All generated data follows a realistic timeline:

- **Medical History**: 6 months to 5 years before procedure
- **Recent Encounters**: 1–12 weeks before procedure
- **Lab Results**: 1–4 weeks before procedure
- **Procedure Date**: 7–90 days in the future

### Document Coherence

When generating documents in different modes (persona only, reports only, summary only), the system ensures consistency:

- Reports reference the same facility and dates from the persona
- Summaries align with existing persona and reports
- No contradictory information across documents
- **Policy criteria summary is excluded from clinical reports and the persona** (reserved for internal annotator summary content)
- **Medical history and biography are never blank** — bio narrative and report history sections are backfilled if missing
- **Rejection → Approval for reports**: when supporting reports are generated, rejection/denial outcomes are treated as approval for clinical document generation

### Intensive Document Generation (PA Support)

To support Prior Authorization use cases, generated clinical documents are tuned for depth and audit-readiness:

- **Content intensity**: Prompts require multi-sentence sections (e.g. findings, impression, clinical justification) with specific measurements and clinical detail; one-line or N/A-style answers are discouraged for core sections.
- **Template-driven PDF layout**: Report sections follow the order defined in each template (`templates/*.json`). The system handles structured JSON natively, ensuring that clinical metadata is correctly injected by the pipeline rather than halluncinated by the AI.
- **Diagnostic cases**: The default diagnostic case type now includes a consultation/office visit note in addition to the prior auth request and summary, so E&M-style cases produce three documents.
- **Sparse-document warning**: If a report body is very short (&lt; 200 characters), the generator logs a warning suggesting regeneration with feedback.

### FHIR-Compliant Data

- Complete patient demographics, biometrics (race, height, weight)
- Emergency contacts, insurance/payer details
- Provider information with NPI
- Medical coding (ICD-10, CPT)

---

## 🛠️ Installation & Setup

### 1. Prerequisites

- Python 3.10+
- OpenAI API Key **or** Google Cloud Vertex AI credentials

### 2. Environment Setup

```bash
git clone <repo-url>
cd pdgenerator

# Mac / Linux
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Windows
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configuration (`cred/.env`)

```bash
# Mac/Linux
mkdir -p cred
cp core/.env.example cred/.env

# Windows (cmd)
mkdir cred 2>nul
copy core\.env.example cred\.env
```

Fill in `cred/.env`:

```bash
# ─── LLM Provider Configuration ───────────────────────────────────────────────
# Switch between 'openai' and 'vertexai' here. No other changes needed.
LLM_PROVIDER=openai          # or vertexai

# ─── OpenAI ───────────────────────────────────────────────────────────────────
OPENAI_API_KEY=sk-your-key-here

# ─── Google Cloud / Vertex AI ─────────────────────────────────────────────────
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
# Relative paths (./cred/...) are resolved against BASE_DIR automatically
GOOGLE_APPLICATION_CREDENTIALS=./cred/gcp_auth_key.json

# ─── Output & Runtime ─────────────────────────────────────────────────────────
OUTPUT_DIR=/path/to/generated_output
TEST_MODE=false

# ─── Optional: Web Search ─────────────────────────────────────────────────────
ENABLE_WEB_SEARCH=false
TAVILY_API_KEY=your_tavily_key
```

**Vertex AI only:** Place your service account JSON at `cred/gcp_auth_key.json`.

---

## 📁 Project Structure

```text
pdgenerator/
├── cred/                       # Credentials (gitignored)
│   ├── .env                    # Configuration
│   └── examples/.env.example   # Template
│
├── core/                       # Reference data (Excel plan, code maps)
│   ├── UAT Plan.xlsx           # Patient test cases
│   └── cpt_code_map.json       # Derived CPT map
│
├── config/                     # Externalized rules & patterns
│   ├── remediation_rules.json
│   └── sanitization_patterns.json
│
├── src/
│   ├── ai/                      # LLM client, prompts, models, QA, search
│   ├── core/                    # Config + patient DB + state (patients_db.json)
│   ├── data/                    # Loader + history + record writers
│   ├── doc_generation/          # Planner, validator, PDF generation
│   ├── utils/                   # File/date/purge utilities
│   ├── cli.py                   # CLI entrypoint
│   └── workflow.py              # Orchestration layer
│
├── ui/
│   ├── index.html              # Dark interactive UI (Material You)
│   └── index2.html             # Light interactive UI (Command Center)
│
├── templates/
│   └── summary_template.json   # Clinical summary PDF layout
│
├── generated_output/           # Generated files (gitignored)
│   ├── persona/                # Patient persona PDFs
│   ├── patient-reports/<ID>/   # Clinical report PDFs
│   ├── summary/                # Annotator verification summaries
│   └── logs/                   # Generation history per patient
│
├── api_server.py               # Flask REST API (serves the UI)
├── run.py                      # CLI launcher (recommended)
├── remove_persona.py           # CLI tool to completely wipe a persona
│
├── run.bat                     # Windows CLI launcher
├── run_api.bat                 # Windows API launcher
├── run.sh                      # Mac/Linux CLI launcher
├── run_api.sh                  # Mac/Linux API launcher
└── requirements.txt
```

**Patient DB:** The active database lives at `src/core/patients_db.json`. If a legacy `core/patients_db.json` exists, it is automatically migrated on first load.
**Feedback history:** Per-patient feedback/history is stored in `generated_output/logs` and reused across runs (legacy logs from the old output path are auto-migrated when read).

### Key Files to Customize

| File | Purpose |
| :--- | :--- |
| `src/ai/prompts.py` | Edit AI behaviour and generation instructions |
| `cred/.env` | Configure API keys, output path, port |
| `core/UAT Plan.xlsx` | Patient test cases |
| `templates/summary_template.json` | PDF layout structure |
| `config/*.json` | External rules (remediation, sanitization) |

---

## 🚀 Server Management

The Web UI requires the Flask backend server (`api_server.py`) to be running.

**Start the Server:**

```bash
# Mac/Linux
source venv/bin/activate
python -m api_server

# Windows
venv\Scripts\activate
python -m api_server
```

*The server runs on port 410 by default. Access the UI by opening `ui/index.html` in your browser.*

**Stop the Server:**

- If running in a terminal, press `Ctrl + C`.
- If running in the background, find the process and kill it:

  ```bash
  # Find process ID (PID)
  lsof -i :410
  # Kill process
  kill -9 <PID>
  ```

**Restart the Server:**
Simply stop the server using `Ctrl + C` or `kill`, and start it again using the start command.

---

## 🌐 API Reference

The `api_server.py` Flask server exposes multiple endpoints to power the UI and batch processing.

### 📚 Interactive Swagger API Docs

We have integrated full **Swagger OpenAPI documentation**. To explore the interactive API details, test endpoints, and view payloads, visit:
👉 **[http://localhost:410/apidocs](http://localhost:410/apidocs)** *(assuming port 410)*

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| GET | `/api/status` | Health check |
| GET | `/api/patients` | List all patient IDs from Excel |
| GET | `/api/patient/<id>` | Fetch stored patient record |
| POST | `/api/generate` | Trigger single patient generation |
| POST | `/api/generate_all` | 🔁 Trigger batch generation for all patients |
| POST | `/api/cancel/<job_id>` | ⛔ Cancel an active generation job with auto-rollback |
| POST | `/api/purge` | 🗑️ Purge specific databases or generated files (patient mode supports `targets[]` and `mode=delete/archive`) |
| POST | `/api/template/save` | 💾 Save a generated document as a global template |
| GET | `/api/job/<job_id>?since=N` | Poll job status + incremental logs |
| GET | `/api/output/<patient_id>` | List all generated PDFs for a patient |
| GET | `/api/download/<id>/<type>/<file>` | Serve PDF inline in browser |

---

## 🔐 Credentials Management

- The `cred/` folder is gitignored by default
- Never commit API keys or service account files
- Use `core/.env.example` to reconstruct your environment at `cred/.env`

---

## 🏗️ Architecture

For a deep dive into the code structure, module interactions, and how to extend the system, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📝 License

Proprietary / Internal Use Only.
