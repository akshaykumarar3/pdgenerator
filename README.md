# Clinical Data Generator (v3.0)

> **Automated Synthetic Healthcare Data Pipeline**
> Generates high-fidelity clinical PDFs and FHIR-compliant personas for testing Prior Authorization workflows.

---

## 🚀 Quick Start

### Option A — Web UI (Recommended)

The fastest way to use the generator is through the interactive browser interface.

**Step 1:** Start the API server

```bash
# Mac / Linux
API_PORT=410 venv/bin/python api_server.py

# Windows
set API_PORT=410 && venv\Scripts\python api_server.py
```

> **Note (macOS):** Port 5000 is reserved by AirPlay Receiver by default. The default port is now `410`.

**Step 2:** Open `ui/index.html` in your browser (no web server needed — just double-click the file).

---

### Option B — Command Line

```bash
# Mac / Linux
./run.sh
# OR
python3 generator.py

# Windows
run.bat
# OR
python generator.py
```

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

## 🖥️ Web UI Features

The `ui/index.html` interface provides a rich, dark-themed clinical data studio.

### Sidebar Controls

- **Patient ID** — Select an existing patient or leave blank for a new one
- **Generate Selected Patient** — Toggle which documents to create: Persona, Reports, Summary
- **Generate All Patients (Batch)** — 🔁 Automatically generate documents for all patients in the database sequentially
- **Purge Data** — 🗑️ Open a management modal to permanently clear specific generated data, personas, or the entire database
- **PA Approval Optimization** — Strengthens clinical justifications for cases likely to be denied
- **Feedback / Instructions** — Multi-line instruction field (no character limit)

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

### Intensive Document Generation (PA Support)

To support Prior Authorization use cases, generated clinical documents are tuned for depth and audit-readiness:

- **Content intensity**: Prompts require multi-sentence sections (e.g. findings, impression, clinical justification) with specific measurements and clinical detail; one-line or N/A-style answers are discouraged for core sections.
- **Template-driven PDF layout**: Report sections follow the order defined in each template (`templates/*.json`), and nested fields (e.g. patient_information, study_information) are rendered as readable key-value text instead of raw JSON.
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
mkdir cred
cp cred/examples/.env.example cred/.env
```

Fill in `cred/.env`:

```bash
# Choose provider
LLM_PROVIDER=openai          # or vertexai

# OpenAI
OPENAI_API_KEY=sk-your-key-here

# OR Vertex AI
GCP_PROJECT_ID=your-project-id
GCP_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./cred/gcp_auth_key.json

# Output directory (absolute path recommended)
OUTPUT_DIR=/path/to/generated_output

# API server port (default: 410)
API_PORT=410

# Optional: Web Search
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
├── core/                       # Reference data & patient database
│   ├── UAT Plan.xlsx           # Patient test cases
│   ├── patient_db.py           # Patient database module
│   └── patients_db.json        # Patient records (auto-generated)
│
├── ui/
│   └── index.html              # Interactive web UI
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
├── generator.py                # Main orchestrator & CLI loop
├── ai_engine.py                # LLM interaction + Pydantic models
├── pdf_generator.py            # PDF rendering (ReportLab)
├── prompts.py                  # AI prompt configuration
├── state_manager.py            # V3 Core: Patient State deterministic source of truth
├── document_planner.py         # V3 Core: Dynamic template planning and schema rendering
├── search_engine.py            # Web search for medical codes (Tavily)
├── doc_validator.py            # Document structure validation & template-driven formatting
├── data_loader.py              # Excel case data loading
├── history_manager.py          # Per-patient generation history
├── purge_manager.py            # Data cleanup utilities
├── remove_persona.py           # CLI tool to completely wipe a persona
│
├── run.bat                     # Windows CLI launcher
├── run.sh                      # Mac/Linux CLI launcher
└── requirements.txt
```

### Key Files to Customize

| File | Purpose |
| :--- | :--- |
| `prompts.py` | Edit AI behaviour and generation instructions |
| `cred/.env` | Configure API keys, output path, port |
| `core/UAT Plan.xlsx` | Patient test cases |
| `templates/summary_template.json` | PDF layout structure |

---

## 🚀 Server Management

The Web UI requires the Flask backend server (`api_server.py`) to be running.

**Start the Server:**

```bash
# Mac/Linux
source venv/bin/activate
python api_server.py

# Windows
venv\Scripts\activate
python api_server.py
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
| POST | `/api/purge` | 🗑️ Purge specific databases or generated files |
| POST | `/api/template/save` | 💾 Save a generated document as a global template |
| GET | `/api/job/<job_id>?since=N` | Poll job status + incremental logs |
| GET | `/api/output/<patient_id>` | List all generated PDFs for a patient |
| GET | `/api/download/<id>/<type>/<file>` | Serve PDF inline in browser |

---

## 🔐 Credentials Management

- The `cred/` folder is gitignored by default (except `cred/examples/`)
- Never commit API keys or service account files
- Use `cred/examples/.env.example` to reconstruct your environment

---

## 🏗️ Architecture

For a deep dive into the code structure, module interactions, and how to extend the system, refer to [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 📝 License

Proprietary / Internal Use Only.
