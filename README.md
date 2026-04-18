# LeadGuard

AI inbox triage demo for prioritizing revenue-critical emails, enriching sender context, and escalating the top opportunity with a live phone call.

## What it does

LeadGuard scans a bundled inbox of 20 emails and runs a simple decision pipeline:

1. Load demo emails from `data/emails.json`
2. Classify each email with Baseten
3. Enrich `P0` and `P1` senders with You.com company intel
4. Surface a reply draft and cost-to-ignore in Streamlit
5. Trigger a live VoiceRun call for the top `P0`
6. Evaluate the classifier locally and in Veris

## Stack

- `Streamlit` for the demo UI
- `Baseten` for structured email classification
- `You.com` for sender enrichment
- `VoiceRun` for outbound escalation calls
- `Veris` for simulation and evaluation

## Run locally

Install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Create `.env` from `.env.example`, then run the app:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## Environment variables

Required for the full live demo:

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

Notes:

- If `BASETEN_API_KEY` is missing, the app falls back to heuristic classification.
- If `YOUCOM_API_KEY` is missing, the app falls back to bundled demo intel for known domains.
- If VoiceRun is not configured and `DEMO_MODE=true`, escalation returns a simulated success.

## Project structure

- `app.py` - Streamlit UI and demo flow
- `agent.py` - Baseten classification plus heuristic fallback
- `email_loader.py` - bundled inbox loader and optional dataset regeneration
- `enricher.py` - You.com sender enrichment
- `escalator.py` - VoiceRun outbound call trigger
- `veris_api.py` - FastAPI adapter for Veris HTTP evaluation
- `veris_eval.py` - local evaluation harness
- `voicerun_handler.py` - minimal VoiceRun handler reference
- `data/emails.json` - bundled demo inbox
- `assets/logo.png` - app branding asset
- `.veris/veris.yaml` - Veris target config
- `.veris/Dockerfile.sandbox` - Veris sandbox build file
- `.veris/config.yaml` - local Veris environment mapping

## Evaluation

Run the local eval:

```powershell
.\.venv\Scripts\python.exe veris_eval.py
```

Expected output includes:

- `pass_rate`
- `p0_precision`
- `no_false_p0_on_spam`

Run the Veris adapter locally:

```powershell
.\.venv\Scripts\uvicorn.exe veris_api:app --host 0.0.0.0 --port 8008
```

## Veris workflow

This repo is already wired for Veris with a single target in `.veris/veris.yaml`.

Typical commands:

```powershell
.\.venv\Scripts\veris.exe login
.\.venv\Scripts\veris.exe env push
.\.venv\Scripts\veris.exe scenarios create --num 3
.\.venv\Scripts\veris.exe run --scenario-set-id <SCENARIO_SET_ID> --report
```

If you want to download the generated report:

```powershell
.\.venv\Scripts\veris.exe reports get <REPORT_ID> -o veris-report.html
```

## Demo flow

1. Launch the app
2. Click `Scan & Classify`
3. Open the top `P0`
4. Show summary, cost-to-ignore, draft opening, and company intel
5. Click `Call me now`
6. Close with the Veris or local eval result

## Safety

- Keep real credentials only in `.env`
- Do not commit `.env`
- `.env.example` must stay placeholder-only
