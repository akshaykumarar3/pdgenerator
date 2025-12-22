# Clinical Data Generator (v2.0)

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![AI Provider](https://img.shields.io/badge/AI-Google%20Vertex%20AI-green.svg)](https://cloud.google.com/vertex-ai)
[![Status](https://img.shields.io/badge/Status-Operational-brightgreen.svg)]()

> **Automated Synthetic Healthcare Data Pipeline**
> Generates high-fidelity, schema-valid SQL datasets, clinical PDFs, and medical imaging for testing Prior Authorization workflows.

---

## 🏃 Usage (Interactive Mode)

The tool now runs as an **Interactive REPL (Read-Eval-Print Loop)**, allowing you to process multiple patients without restarting.

### 1. Launch the Generator
```bash
./run.sh
# OR
python3 generator.py
```

### 2. Interactive Commands
Once launched, you will see a prompt: `🎯 Enter Patient ID (or '*' for Batch, 'q' to Quit):`

| Command | Description | Example |
| :--- | :--- | :--- |
| **`[Patient ID]`** | Generates data for a single patient. | `210` or `237` |
| **`[Patient ID]-sql`** | Force SQL generation for a patient. | `237-sql` |
| **`*`** | Runs **Batch Mode** for all missing patients in the Excel tracker. | `*` |
| **`q`** or **`exit`** | Quits the application. | `q` |
| **`--`** | **PURGE ALL**. Deletes logs, documents, and SQLs. | `--` |
| **`--documents`** | Purge only documents (keeps personas). | `--documents` |

### 3. Output Artifacts
Results are saved in the **configured output directory** (Default: `generated_output/`):
*   `persona/*.pdf`: Comprehensive Face Sheet & Bio for the patient.
*   `sqls/*_final.sql`: The finalized SQL script.
*   `patient-reports/<ID>/*.pdf`: Clinical documents (Consults, Labs, Notes).
*   `patient-reports/<ID>/images/*.png`: Embeddable medical images.
*   `logs/`: Execution logs.

---

## 🛠️ Installation & Setup

### 1. Prerequisites-
*   Python 3.10+
*   Google Cloud Platform Project with **Vertex AI API** enabled.
*   Service Account Key (JSON) with `Vertex AI User` role.

### 2. Environment Setup
```bash
# Clone repository
git clone <repo-url>
cd pdgenerator

# Create Virtual Environment
python3 -m venv venv
source venv/bin/activate

# Install Dependencies
pip install -r requirements.txt
# Upgrade key libraries to support Vertex AI
pip install --upgrade google-genai google-cloud-aiplatform instructor
```

### 3. Configuration (`cred/`)
The system expects credentials in a `cred/` directory to keep them secure.

1.  **Create Directory**: `mkdir cred`
2.  **Environment File**: Create `cred/.env` with the following template:
    ```bash
    # cred/.env
    LLM_PROVIDER=vertexai
    GCP_PROJECT_ID=your-project-id
    GCP_LOCATION=us-central1
    # Points to the key in the SAME folder
    GOOGLE_APPLICATION_CREDENTIALS=./cred/gcp_auth_key.json
    
    # Optional: Custom Output Path
    OUTPUT_DIR=generated_output
    ```
3.  **Service Account Key**: Place your JSON key at `cred/gcp_auth_key.json`.

---

## 🔐 Credentials Management
*   **`.gitignore`**: The `cred/` folder is ignored by default.
*   **Templates**: Use the snippet above to reconstruct your environment on a new machine.

---

## 🚀 Key Features

*   **Multi-Modal AI**: Uses **Gemini 2.5 Pro** (Reasoning/Text) and **Imagen 3** (Medical Imaging).
*   **Interactive Workflow**: Continuous processing loop with admin purge commands.
*   **Optimized Batch Processing**: In-memory caching for high-efficiency bulk generation (O(1) lookups).
*   **Configurable Output**: Define completely custom output paths via `.env`.
*   **Structured Data**: Outputs validated SQL adhering to a rigid FHIR-like schema.
*   **Rich Clinical Narrative**: Generates comprehensive SOAP notes, Imaging Reports, and Discharge Summaries.
*   **Persona Consistency**: Maintains identity across runs (e.g., "Walter White" for ID 210).
*   **Advanced PDFs**: Embedded images, barcode headers, and realistic formatting.

---

## 🏗️ Architecture
For a deep dive into the code structure, module interactions, and how to extend the system, please refer to the [Architecture Documentation](ARCHITECTURE.md).

---

## 📝 License
Proprietary / Internal Use Only.
