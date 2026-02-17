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
| **`[ID]-[feedback]`** | Generates data with AI feedback included. | `225-use kidney transplant` |
| **`[ID],[ID],[ID]`** | Batch mode for specific comma-separated patient IDs. | `221,222,223` |
| **`*`** | Runs **Batch Mode** for all missing patients. | `*` |
| **`q`** or **`exit`** | Quits the application. | `q` |
| **`--`** | **SELECTIVE PURGE**. Shows menu to delete specific artifact types. | `--` |
| **`--[ID]`** | Deletes all data for a specific patient. | `--225` |

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
* `summary/*.pdf`: Annotator verification summaries
* `logs/`: Execution logs

---

## ✨ Key Features

### Prior Authorization Workflow Support

**Future Procedure Dates**: All personas include expected procedure dates (7-90 days in the future) for realistic PA workflows.

**Complete PA Request Forms**: Each persona includes a comprehensive Prior Authorization request section with:
* Requesting provider with credentials
* Urgency level (Routine/Urgent/Emergency)
* Clinical justification (medical necessity)
* Supporting ICD-10 diagnoses
* Previous treatments attempted
* Expected clinical outcome

**Facility Location**: Realistic healthcare facility addresses matching patient locality:
* Facility name and department
* Complete street address
* City, state, and ZIP code
* Automatically matched to patient's state

### Temporal Consistency

All generated data follows a realistic timeline:
* **Medical History**: 6 months to 5 years before procedure
* **Recent Encounters**: 1-12 weeks before procedure
* **Lab Results**: 1-4 weeks before procedure
* **Today**: Current date
* **Procedure Date**: 7-90 days in the future

### Document Coherence

When generating documents in different modes (persona only, reports only, summary only), the system ensures consistency:
* Reports reference the same facility and dates from the persona
* Summaries align with existing persona and reports
* No contradictory information across documents

### FHIR-Compliant Data

* Complete patient demographics
* Biometrics (race, height, weight)
* Emergency contacts
* Insurance/payer details (UnitedHealthcare standardized)
* Provider information with NPI
* Medical coding (ICD-10, CPT)

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
    
    # Optional: Web Search Integration
    ENABLE_WEB_SEARCH=false  # Set to true to enable
    TAVILY_API_KEY=your_tavily_key  # Get free key at https://tavily.com
    SEARCH_CACHE_TTL=24  # Cache duration in hours
    
    # Optional
    OUTPUT_DIR=generated_output
    TEST_MODE=false
    ```

4. **Service Account Key** (Vertex AI only): Place your JSON key at `cred/gcp_auth_key.json`.

**Web Search Setup** (Optional):

* Get a free Tavily API key at [https://tavily.com](https://tavily.com) (1,000 searches/month free)
* Enable with `ENABLE_WEB_SEARCH=true` in `.env`
* Used to retrieve precise CPT/ICD descriptions when Excel data is incomplete
* Adds verification notes when data quality is uncertain

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
│   ├── summary/                # Annotator verification summaries
│   └── logs/                   # Execution logs
│
├── prompts.py                  # ⚡ AI prompts configuration
├── ai_engine.py                # LLM interaction (OpenAI/Vertex AI)
├── generator.py                # Main orchestrator & REPL loop
├── pdf_generator.py            # PDF rendering (ReportLab)
├── search_engine.py            # 🔍 Web search for medical codes (Tavily API)
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
* **`cred/.env`** - Configure API keys and settings (including web search)
* **`core/UAT Plan.xlsx`** - Add patient test cases
* **`templates/summary_template.json`** - Modify PDF layouts

---

## 🚀 Key Features

* **AI-Powered Generation**: Uses **GPT-4o / Gemini 2.5** for intelligent clinical document creation
* **Web Search Integration** (Optional):
  * 🔍 Retrieves precise CPT/ICD code descriptions from authoritative sources (AAPC, CMS)
  * ⚠️ Automatic verification notes for missing/uncertain data
  * 💾 24-hour caching to reduce API costs
  * ✅ Conservative strategy: Excel data prioritized, search only when needed
* **Annotator Verification Guide**:
  * Simplified PDF layout with expected outcome and verification notes
  * All CPT/ICD codes embedded in narrative (no redundant tables)
  * Data quality alerts for manual review
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
