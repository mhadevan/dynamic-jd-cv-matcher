
# Dynamic JD ↔ CV Matcher (Prototype)

This prototype accepts one Job Description and up to 10 CVs. It extracts competencies dynamically from the JD using the OpenAI API,
then scores each CV against those competencies and returns a match table + heatmap. It also supports exporting results to Excel.

## Features
- Upload 1 JD (docx/pdf/txt) + up to 10 CVs
- Frontend model selector: GPT-3.5 Turbo, GPT-4 Turbo, GPT-4o
- Dynamic competency extraction from JD (weights sum to 100)
- CV scoring & heatmap (Full / Partial / Gap)
- Export results to an Excel file (Results + Heatmap)
- Default model: gpt-3.5-turbo (cheap)

## Setup (local)
1. Create a virtualenv and activate it:
   - `python -m venv venv && source venv/bin/activate` (Linux/Mac)
   - Windows PowerShell: `python -m venv venv; .\venv\Scripts\Activate.ps1`

2. Install dependencies:
   - `pip install -r requirements.txt`

3. Set your OpenAI API key in the environment:
   - macOS/Linux: `export OPENAI_API_KEY='sk-...'`
   - Windows (cmd): `set OPENAI_API_KEY=sk-...`
   - Windows PowerShell: `$env:OPENAI_API_KEY='sk-...'`

4. Run the app:
   - `python app.py`
   - Open http://localhost:7860 in your browser

## Notes & Customization
- The app sends file text to OpenAI. Ensure candidate consent / data privacy before using.
- Prompt tuning is in `app.py` — adjust competency extraction & scoring prompts as needed.
- For production, add authentication, request size limits, server-side queueing, and monitoring.
- For heavy volume, use a hybrid pipeline: pre-filter with GPT-3.5 Turbo then deep-score with GPT-4o.
