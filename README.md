# InboxROI Agent

Streamlit demo for triaging inbound email by urgency, revenue impact, and next action.

## Quick start

1. Create a virtual environment and install dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and add any API keys you have.

3. Run the app:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## Project structure

- `app.py` - Streamlit UI
- `agent.py` - Baseten-backed classification with heuristic fallback
- `email_loader.py` - Bundled demo dataset loader and Hugging Face regeneration script
- `enricher.py` - You.com company intel enrichment
- `escalator.py` - VoiceRun outbound call trigger
- `veris_eval.py` - Local evaluation harness for three pitch scenarios
- `veris_api.py` - Optional FastAPI wrapper for Veris sandbox integration
- `voicerun_handler.py` - Reference VoiceRun handler to speak generated alert scripts
- `.veris/veris.yaml` - Veris environment config for HTTP-based agent evaluation
- `.env.example` - Placeholder environment template with no real credentials

## Team split

Two engineers can finish this project in 4 hours if they keep ownership clean and avoid editing the same files.

### Beibarys - UI, classification, and product demo surface

Primary files:

- `app.py`
- `agent.py`
- `data/emails.json`

Responsibilities:

- Own the full product surface that judges will see on screen.
- Wire the inbox scan flow in Streamlit and make the app feel polished.
- Match the UI to the target mock as closely as possible.
- Replace heuristic classification with live Baseten once the key is available.
- Confirm the Baseten model slug that actually exists in the workspace.
- Tune prompts so P0, P1, and P3 outputs are stable on live inputs.
- Verify sorting, metrics, draft text, confidence display, and expanders.

Definition of done:

- `Scan & Classify` produces stable ranked results.
- At least one clear `P0` row appears in the UI.
- Cost-to-ignore, draft opening, and company intel are visible.
- App looks presentation-ready on one laptop screen.

### Daniyar - VoiceRun, You.com, Veris, and live demo reliability

Primary files:

- `enricher.py`
- `escalator.py`
- `voicerun_handler.py`
- `veris_eval.py`
- `veris_api.py`
- `.veris/veris.yaml`
- `.env`

Responsibilities:

- Own the live integrations that make the demo credible and memorable.
- Get a real `YOUCOM_API_KEY` and make company intel work for `P0` and `P1` rows.
- Get real `VOICERUN_API_KEY`, `VOICERUN_AGENT_ID`, `VOICERUN_ENVIRONMENT`, and `PHONE_NUMBER`.
- Make outbound calling work from the `Call me now` button.
- Verify the search response looks useful and grounded before it reaches the UI.
- Confirm the spoken script sounds clean and urgent enough for the demo.
- Run the local evaluation harness and capture results for the pitch.
- If time allows, log into Veris, create the environment, and push the HTTP wrapper.
- Keep the fallback demo path safe in case a provider key breaks during the final hour.

UI ownership:

- Daniyar does not own the main Streamlit UI implementation.
- Daniyar only needs enough UI interaction to smoke test the `Call me now` flow and final demo path.
- Beibarys owns the visible app experience and all UI-facing polish.

Definition of done:

- Clicking `Call me now` on a `P0` email starts a real phone call or a provable VoiceRun session.
- `python veris_eval.py` returns clean metrics for the three demo scenarios.
- `uvicorn veris_api:app --host 0.0.0.0 --port 8008` starts without errors.
- `.veris/veris.yaml` points Veris at the local HTTP classification endpoint.

## Daniyar runbook

This is the recommended order for your track.

### 1. Configure environment variables

Create `.env` from `.env.example` and fill in:

- `YOUCOM_API_KEY`
- `VOICERUN_API_KEY`
- `VOICERUN_AGENT_ID`
- `VOICERUN_ENVIRONMENT`
- `PHONE_NUMBER`
- `BASETEN_API_KEY` if you also get access to the shared model workspace

### 2. Smoke test local evaluation

Run:

```powershell
.\.venv\Scripts\python.exe veris_eval.py
```

Expected result:

- `pass_rate` should be `1`
- `p0_precision` should be `1.0`
- `no_false_p0_on_spam` should be `true`

### 3. Smoke test the Veris HTTP adapter

Run:

```powershell
.\.venv\Scripts\uvicorn.exe veris_api:app --host 0.0.0.0 --port 8008
```

Then verify:

- `http://localhost:8008/health`
- `http://localhost:8008/classify`

This adapter is what lets Veris treat the classifier as an HTTP agent endpoint.

### 4. Smoke test Streamlit + VoiceRun flow

Run:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Then:

1. Click `Scan & Classify`
2. Open a `P0` row
3. Click `Call me now`
4. Confirm whether the result is real VoiceRun or simulated fallback

### 5. If Veris is available, push the environment

Recommended commands:

```powershell
veris login
veris env create --name "inboxroi-agent"
veris env push
veris run
```

If you do not finish the full Veris loop, the local eval in `veris_eval.py` is enough to support the pitch.

## 4-hour execution plan

### Hour 1

- Beibarys: finalize app layout and classification flow
- Daniyar: get VoiceRun credentials and make outbound calling work first

### Hour 2

- Beibarys: Baseten live integration and prompt tuning
- Daniyar: verify call script quality and capture a working phone demo

### Hour 3

- Beibarys: UI cleanup and final demo polish
- Daniyar: You.com live enrichment, run `veris_eval.py`, then try Veris login and push if available

### Hour 4

- Freeze feature work
- Rehearse the full demo end to end
- Prepare one fallback story if live APIs fail

## Demo sequence

Use this exact order on stage:

1. Open the inbox with already-classified results visible.
2. Point at the top `P0` row and the `$ at risk` metric.
3. Expand the row and show the summary, draft, and company intel.
4. Click `Call me now`.
5. Let the phone call be the wow moment.
6. Close by showing evaluation readiness from `veris_eval.py` or Veris.

## Notes

- The repo ships with `data/emails.json`, so the app works immediately in demo mode.
- If `BASETEN_API_KEY` is missing, the app uses a deterministic heuristic classifier so the UI still works.
- If `YOUCOM_API_KEY` is missing, bundled demo intel is shown for known company domains.
- If VoiceRun variables are missing, escalation returns a simulated success when `DEMO_MODE=true`.
- Keep real credentials only in `.env`; `.env.example` should remain placeholder-only for safe commits.
