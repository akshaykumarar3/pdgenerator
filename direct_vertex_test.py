import os
import vertexai
from vertexai.generative_models import GenerativeModel
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv("cred/.env")

project_id = os.getenv("GCP_PROJECT_ID")
location = os.getenv("GCP_LOCATION")
key_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

print(f"Project: {project_id}, Location: {location}")
print(f"Key: {key_path}")

try:
    creds = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )
    vertexai.init(project=project_id, location=location, credentials=creds)
    
    model_name = "gemini-2.5-flash" 
    print(f"Init Model: {model_name}")
    model = GenerativeModel(model_name)
    
    print("Generating...")
    response = model.generate_content("Say hello")
    print(f"Response: {response.text}")
    print("SUCCESS")

except Exception as e:
    print(f"FAILED: {e}")
