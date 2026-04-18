# LeadGuard

LeadGuard is an AI inbox triage demo for finding the highest-value inbound emails, enriching sender context, drafting the response opening, and escalating the top alert with a live phone call.

The app is built as a hackathon-ready workflow with a simple, reliable pipeline:

1. Load a bundled inbox of demo emails
2. Classify each email by urgency and revenue impact
3. Enrich top-priority senders with company intel
4. Surface draft replies and cost-to-ignore in the UI
5. Trigger a live VoiceRun call for the top `P0`
6. Evaluate the agent locally and in Veris

## Stack Used

- `Python 3.12`
- `Streamlit` for the product demo UI
- `Baseten` using an OpenAI-compatible endpoint for classification
- `DeepSeek-V3.1` via Baseten as the live classification model
- `You.com Search API` for company enrichment
- `VoiceRun / Primvoices` for outbound phone escalation
- `FastAPI` for the Veris HTTP adapter
- `Veris CLI + Veris Sandbox` for simulation and evaluation
- `requests` and `python-dotenv` for provider integration

## Final Project Structure

The project is intentionally kept flat at the root so it is easy to demo, debug, and hand off quickly.

```text
Veris-hack/
|-- .veris/
|   |-- .dockerignore
|   |-- config.yaml
|   |-- Dockerfile.sandbox
|   `-- veris.yaml
|-- assets/
|   `-- logo.png
|-- data/
|   `-- emails.json
|-- agent.py
|-- app.py
|-- email_loader.py
|-- enricher.py
|-- escalator.py
|-- requirements.txt
|-- veris_api.py
|-- veris_eval.py
|-- voicerun_handler.py
|-- .env.example
`-- README.md
```

## File Guide

- `app.py` - Streamlit UI, metrics, scan flow, sorted results, and escalation button
- `agent.py` - Baseten classification plus heuristic fallback
- `email_loader.py` - loads the bundled inbox and supports one-time dataset regeneration
- `enricher.py` - You.com enrichment for `P0` and `P1` emails
- `escalator.py` - VoiceRun outbound call logic
- `veris_api.py` - FastAPI wrapper that exposes classification over HTTP for Veris
- `veris_eval.py` - local evaluation harness for core pitch scenarios
- `voicerun_handler.py` - minimal VoiceRun handler reference for the deployed call agent
- `data/emails.json` - bundled inbox used in the demo
- `assets/logo.png` - branding asset used by the UI
- `.veris/veris.yaml` - Veris target config
- `.veris/Dockerfile.sandbox` - Veris sandbox build definition
- `.veris/config.yaml` - current local Veris environment mapping for this repo

## Environment Variables

Create `.env` from `.env.example`.

Full live demo configuration:

```env
BASETEN_API_KEY=
BASETEN_BASE_URL=https://inference.baseten.co/v1
BASETEN_MODEL=deepseek-ai/DeepSeek-V3.1

YOUCOM_API_KEY=
YOUCOM_BASE_URL=https://ydc-index.io

VOICERUN_API_KEY=
VOICERUN_AGENT_ID=
VOICERUN_ENVIRONMENT=debug
VOICERUN_BASE_URL=https://api.primvoices.com/v1
VOICERUN_VOICE=nova
PHONE_NUMBER=+15555555555

DEMO_MODE=true
```

Fallback behavior:

- If `BASETEN_API_KEY` is missing, the app uses heuristic classification
- If `YOUCOM_API_KEY` is missing, the app falls back to bundled company intel where available
- If VoiceRun is not configured and `DEMO_MODE=true`, the escalation path returns a simulated success

## Run Locally

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Run the app:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Basic smoke test:

1. Click `Scan & Classify`
2. Open the top `P0` row
3. Verify summary, cost-to-ignore, draft opening, and company intel
4. Click `Call me now`

## Evaluation

Run the local evaluation harness:

```powershell
.\.venv\Scripts\python.exe veris_eval.py
```

Expected outputs include:

- `pass_rate`
- `p0_precision`
- `no_false_p0_on_spam`

Run the Veris HTTP adapter locally:

```powershell
.\.venv\Scripts\uvicorn.exe veris_api:app --host 0.0.0.0 --port 8008
```

## Veris Workflow

This repo is already wired for Veris with a single target in `.veris/veris.yaml`.

Typical commands:

```powershell
.\.venv\Scripts\veris.exe login
.\.venv\Scripts\veris.exe env push
.\.venv\Scripts\veris.exe scenarios create --num 3
.\.venv\Scripts\veris.exe run --scenario-set-id <SCENARIO_SET_ID> --report
```

Download a generated report:

```powershell
.\.venv\Scripts\veris.exe reports get <REPORT_ID> -o veris-report.html
```

## Demo Flow

1. Launch the app
2. Click `Scan & Classify`
3. Show the top `P0` and the total risk metrics
4. Open the row and show the summary, company intel, and reply draft
5. Click `Call me now`
6. Close with local eval or Veris results

## Notes

- The product is intentionally demo-first and uses a bundled inbox instead of Gmail
- The top-level structure is intentionally flat for faster hackathon debugging
- Real credentials should only live in `.env`
- `.env.example` must stay placeholder-only
