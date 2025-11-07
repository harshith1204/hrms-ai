# HRMS AI

A Human Resource Management System powered by AI.

## Features

- AI-powered employee management
- Automated HR workflows
- Intelligent reporting and analytics

## HR Profile Creator CLI

Create structured HR job profiles from natural-language prompts using Groq Cloud models.

### Prerequisites

- Python 3.9+
- A Groq Cloud account and API key (`GROQ_API_KEY`)

### Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export GROQ_API_KEY="your_api_key"
```

### Usage

Generate a profile directly from a prompt:

```bash
python hr_profile_creator.py \
  --prompt "Generate a detailed JSON response for a Java Backend Developer position with 3 years of experience based in Hyderabad." \
  --schema schemas/sample_job_profile_schema.json
```

Produce an Angular-focused profile using an extended structure:

```bash
python hr_profile_creator.py \
  --prompt "Generate a professional JSON response for an Angular Developer position with 4+ years of experience." \
  --schema schemas/angular_extended_schema.json
```

Optional flags:

- `--model` to select a Groq model (default `llama3-8b-8192`)
- `--temperature` to control creativity (default `0.3`)
- `--max-tokens` to cap response length (default `2048`)
- `--output` to write the JSON to a file
- `--no-pretty` to disable pretty-printing

You can also store prompts in files using `--prompt-file`.
