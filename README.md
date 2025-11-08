# HRMS AI

A Human Resource Management System powered by AI.

## Features

- AI-powered employee management
- Automated HR workflows
- Intelligent reporting and analytics

## HR Profile Generator API

Expose a FastAPI endpoint that transforms natural-language prompts into structured HR job profile JSON payloads using Groq Cloud models.

### Prerequisites

- Python 3.9+
- A Groq Cloud account and API key (`GROQ_API_KEY`)
- Optional: a `.env` file to store local environment variables

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
echo "GROQ_API_KEY=your_api_key" > .env  # or export manually
```

### Run the API

```bash
uvicorn app:app --reload
```

The server exposes:

- `GET /health` – uptime probe
- `POST /profiles/generate` – generate a profile

### Example Request

```bash
curl -X POST http://localhost:8000/profiles/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Generate a detailed JSON response for a Java Backend Developer position with 3 years of experience based in Hyderabad.",
    "schema": {
      "jobTitle": "",
      "jobCode": "",
      "descriptionCaption": "",
      "description": "",
      "justificationJobDescription": "",
      "requirement": "",
      "aboutCompany": "",
      "experience": [],
      "salary": [],
      "skills": [],
      "benefits": []
    }
  }'
```

You can supply any schema object to match the desired JSON layout—for example `schemas/angular_extended_schema.json` for Angular roles.

Optional parameters: `model`, `temperature`, `max_tokens`, and `retries`.
