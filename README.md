# Clinical Data Generator (v2.0)

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![AI Provider](https://img.shields.io/badge/AI-Google%20Vertex%20AI-green.svg)](https://cloud.google.com/vertex-ai)
[![Status](https://img.shields.io/badge/Status-Operational-brightgreen.svg)]()

> **Automated Synthetic Healthcare Data Pipeline**
> Generates high-fidelity clinical PDFs and FHIR-compliant personas for testing Prior Authorization workflows.

---

## 🚀 Quick Start

Already set up? Start generating immediately:

### Launch the Generator

**Windows:**

```cmd
run.bat
:: OR
python generator.py
```

**Mac / Linux:**

```bash
./run.sh
# OR
python3 generator.py
```

### Interactive Commands

Once launched, you'll see: `🎯 Enter Patient ID (or '*' for Batch, 'q' to Quit):`

| Command | Description | Example |
| :--- | :--- | :--- |
| **`[Patient ID]`** | Generates data for a single patient. | `210` or `237` |
| **`*`** | Runs **Batch Mode** for all missing patients. | `*` |
| **`q`** or **`exit`** | Quits the application. | `q` |
| **`--`** | **PURGE ALL**. Deletes logs and documents. | `--` |

### Document Selection

After entering a Patient ID:

```
📋 What to generate?
   [1] Persona + Reports + Summary (default)
   [2] Reports + Summary
   [3] Summary only
   [4] Reports only
   [5] Persona only
```

### Output

Results are saved in `generated_output/` (configurable):

* `persona/*.pdf`: Patient Face Sheet & Bio
* `patient-reports/<ID>/*.pdf`: Clinical documents
* `logs/`: Execution logs

---

## 🛠️ Installation & Setup

### 1. Prerequisites

* Python 3.10+
* Google Cloud Platform Project with **Vertex AI API** enabled (if using Vertex AI)
* OpenAI API Key (if using OpenAI)

### 2. Environment Setup

```bash
# Clone repository
git clone <repo-url>
cd pdgenerator
```

**Windows (PowerShell or CMD):**

```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**Mac / Linux:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration (`cred/`)

The system expects credentials in a `cred/` directory.

1. **Create Directory**: `mkdir cred`
2. **Create Environment File**: Copy the example and customize:

    **Windows:**

    ```cmd
    copy cred\examples\.env.example cred\.env
    notepad cred\.env
    ```

    **Mac / Linux:**

    ```bash
    cp cred/examples/.env.example cred/.env
    nano cred/.env
    ```

3. **Fill in your credentials:**

    ```bash
    # Choose provider
    LLM_PROVIDER=openai  # or vertexai
    
    # OpenAI
    OPENAI_API_KEY=sk-your-key-here
    
    # OR Vertex AI
    GCP_PROJECT_ID=your-project-id
    GCP_LOCATION=us-central1
    GOOGLE_APPLICATION_CREDENTIALS=./cred/gcp_auth_key.json
    
    # Optional
    OUTPUT_DIR=generated_output
    TEST_MODE=false
    ```

4. **Service Account Key** (Vertex AI only): Place your JSON key at `cred/gcp_auth_key.json`.

---

## 📁 Project Structure

```
pdgenerator/
├── cred/                       # Credentials (gitignored, create manually)
│   ├── .env                    # Your configuration (copy from examples)
│   ├── gcp_auth_key.json       # GCP service account (if using Vertex AI)
│   └── examples/               # Example configuration files
│       └── .env.example        # Template for .env
│
├── core/                       # Reference data & patient database
│   ├── UAT Plan.xlsx           # Patient test cases & scenarios
│   ├── mockdata_schema.sql     # Database schema reference
│   ├── seed_template.sql       # SQL template for patient records
│   ├── Sample persona.pdf      # Example output
│   ├── patient_db.py           # Patient database module
│   └── patients_db.json        # Patient records (auto-generated)
│
├── templates/                  # PDF layout templates
│   └── summary_template.json   # Clinical summary structure
│
├── generated_output/           # Generated files (gitignored)
│   ├── persona/                # Patient persona PDFs
│   ├── patient-reports/        # Clinical documents & images
│   └── logs/                   # Execution logs
│
├── prompts.py                  # ⚡ AI prompts configuration
├── ai_engine.py                # LLM interaction (OpenAI/Vertex AI)
├── generator.py                # Main orchestrator & REPL loop
├── pdf_generator.py            # PDF rendering (ReportLab)
├── doc_validator.py            # Document validation
├── data_loader.py              # Excel case data loading
├── history_manager.py          # Conversation history
├── purge_manager.py            # Data cleanup utilities
│
├── run.bat                     # Windows launcher
├── run.sh                      # Mac/Linux launcher
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── AI_CONTEXT.md               # AI assistant reference
└── ARCHITECTURE.md             # System architecture docs
```

### Key Files to Customize

* **`prompts.py`** - Edit AI behavior and instructions
* **`cred/.env`** - Configure API keys and settings
* **`core/UAT Plan.xlsx`** - Add patient test cases
* **`templates/summary_template.json`** - Modify PDF layouts

---

## 🚀 Key Features

* **AI-Powered Generation**: Uses **GPT-4o / Gemini 2.5** for intelligent clinical document creation
* **Interactive Workflow**: Continuous processing loop with admin purge commands
* **Smart Duplicate Detection**:
  * Scans existing documents before generation
  * Prevents creating duplicates like "Doc-221-001 CT scan" and "Doc-221-002 CT scan"
  * Only generates multiple reports when test case specifically requires it
  * Intelligently replaces outdated documents when necessary
* **AI-Friendly Validation**:
  * **Auto-Repair**: Invalid documents are automatically fixed by AI
  * **Fail-Safe**: Failed repairs saved with `-NAF` suffix (Not AI Friendly)
* **Centralized Prompts**: All AI instructions in `prompts.py` for easy editing
* **Configurable Output**: Custom output paths via `.env`
* **Structured Data**: FHIR-compliant JSON objects
* **Rich Clinical Narrative**: Comprehensive SOAP notes, Imaging Reports, Discharge Summaries
* **Persona Consistency**: Maintains character identity across runs
* **Professional PDFs**: Realistic formatting with proper headers and structure

---

## 🔐 Credentials Management

* **`.gitignore`**: The `cred/` folder is ignored by default (except `cred/examples/`)
* **Templates**: Use `cred/examples/.env.example` to reconstruct your environment
* **Security**: Never commit API keys or service account files

---

## 🏗️ Architecture

For a deep dive into the code structure, module interactions, and how to extend the system, please refer to the [Architecture Documentation](ARCHITECTURE.md).

---

## 📝 License

Proprietary / Internal Use Only.
