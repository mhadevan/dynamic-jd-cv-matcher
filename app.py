
from flask import Flask, request, render_template, jsonify, send_file
import os, tempfile, json
import docx2txt, pdfplumber
import openai
import pandas as pd
from io import BytesIO

app = Flask(__name__)
openai.api_key = os.environ.get("OPENAI_API_KEY")

MAX_CVS = 10
MAX_PROMPT_CHARS = 38000  # truncate very long docs

MODEL_CHOICES = {
    "gpt-3.5-turbo": "gpt-3.5-turbo",
    "gpt-4-turbo": "gpt-4-turbo",
    "gpt-4o": "gpt-4o"
}

def extract_text_from_file(fp, filename):
    lower = filename.lower()
    text = ""
    try:
        if lower.endswith(".docx"):
            with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                tmp.write(fp.read())
                tmp.flush()
                tmp_path = tmp.name
            text = docx2txt.process(tmp_path) or ""
            try: os.remove(tmp_path)
            except: pass
        elif lower.endswith(".pdf"):
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(fp.read())
                tmp.flush()
                tmp_path = tmp.name
            parts = []
            with pdfplumber.open(tmp_path) as pdf:
                for page in pdf.pages:
                    parts.append(page.extract_text() or "")
            text = "\n".join(parts)
            try: os.remove(tmp_path)
            except: pass
        else:
            text = fp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        text = ""
    if len(text) > MAX_PROMPT_CHARS:
        text = text[:MAX_PROMPT_CHARS]
    return text

def call_openai_chat(model, messages, max_tokens=1200):
    # Wrapper, returns assistant text or raises
    resp = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0.0,
        max_tokens=max_tokens
    )
    return resp.choices[0].message["content"]

def extract_competencies_from_jd(jd_text, model):
    system = ("You are an expert talent sourcer. Extract the top competencies from the Job Description. "
              "Return ONLY valid JSON with a single key 'competencies' whose value is a list of objects. "
              "Each competency object must have: 'name' (short), 'description' (1-2 lines), 'weight' (integer). "
              "Return 5-12 competencies. Sum of weights must be 100. No extra commentary.")
    user = f"JOB DESCRIPTION:\n{jd_text}\n\nReturn competencies JSON as described."
    content = call_openai_chat(model, [{"role":"system","content":system}, {"role":"user","content":user}], max_tokens=800)
    # try to find JSON inside response
    import re, json
    m = re.search(r"(\{.*\})", content, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # fallback: try direct json loads
    try:
        return json.loads(content)
    except Exception:
        raise ValueError("Failed to parse competencies JSON from model response. Raw response: " + content[:1000])

def score_candidates(jd_text, competencies, candidates, model):
    # Build prompt for scoring
    system = ("You are an expert technical recruiter and evaluator. You will score each candidate against the "
              "competencies list. Return ONLY valid JSON with 'results' and 'heatmap'. 'results' is a list of per-candidate "
              "objects: name, weighted_match_pct (0-100 integer), palantir_knowledge_pct (if not applicable for role, return 0), strengths (list), gaps (list). "
              "'heatmap' maps competency name -> { candidate_name: 'Full'|'Partial'|'Gap' }. Use the competency weights provided to compute weighted_match_pct. "
              "Be concise. Do not include any extra commentary.")
    # prepare a compact user prompt with competencies and each candidate text
    user = "JD:\n" + jd_text + "\n\nCompetencies:\n" + json.dumps(competencies, ensure_ascii=False, indent=2) + "\n\nCandidates:\n"
    for c in candidates:
        user += f"---\nName: {c['name']}\nText:\n{c['text']}\n\n"
    user += ("\nFor each competency, assign Full (meets or exceeds), Partial (some experience), or Gap (not present). "
             "Compute weighted_match_pct as the weighted sum of competency scores: Full=100, Partial=50, Gap=0. Round to nearest integer. "
             "If the role is not Palantir-related, set palantir_knowledge_pct=0 for each candidate. Otherwise, estimate Palantir knowledge percent. "
             "Return compact JSON.")
    content = call_openai_chat(model, [{"role":"system","content":system}, {"role":"user","content":user}], max_tokens=1600)
    import re, json
    m = re.search(r"(\{.*\})", content, re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    try:
        return json.loads(content)
    except Exception:
        raise ValueError("Failed to parse scoring JSON from model response. Raw response: " + content[:1000])

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/process", methods=["POST"])
def process():
    if 'jd' not in request.files:
        return jsonify({"error":"Missing JD file (field name 'jd')"}), 400
    jd_file = request.files['jd']
    cvs = request.files.getlist('cvs')
    model_key = request.form.get('model', 'gpt-3.5-turbo')
    model = MODEL_CHOICES.get(model_key, 'gpt-3.5-turbo')
    if len(cvs) == 0:
        return jsonify({"error":"Upload at least 1 CV"}), 400
    if len(cvs) > MAX_CVS:
        return jsonify({"error":f"Max {MAX_CVS} CVs allowed"}), 400
    jd_text = extract_text_from_file(jd_file.stream, jd_file.filename)
    candidates = []
    for cv in cvs:
        name = cv.filename.rsplit(".",1)[0]
        text = extract_text_from_file(cv.stream, cv.filename)
        candidates.append({"name": name, "text": text})
    # Step 1: extract competencies
    try:
        competencies_resp = extract_competencies_from_jd(jd_text, model)
    except Exception as e:
        return jsonify({"error":"Competency extraction failed","details": str(e)}), 500
    # Validate competencies_resp
    comps = competencies_resp.get("competencies") if isinstance(competencies_resp, dict) else None
    if not comps or not isinstance(comps, list):
        return jsonify({"error":"Invalid competencies JSON returned by model","raw": competencies_resp}), 500
    # Step 2: scoring
    try:
        scoring = score_candidates(jd_text, comps, candidates, model)
    except Exception as e:
        return jsonify({"error":"Scoring failed","details": str(e)}), 500
    # return combined
    return jsonify({"competencies": comps, "results": scoring.get("results"), "heatmap": scoring.get("heatmap")})

@app.route("/export", methods=["POST"])
def export_xlsx():
    # expect JSON body with competencies, results, heatmap
    data = request.get_json()
    if not data:
        return jsonify({"error":"No JSON body provided"}), 400
    comps = data.get("competencies", [])
    results = data.get("results", [])
    heatmap = data.get("heatmap", {})
    # build DataFrames
    df_results = pd.DataFrame(results)
    # heatmap: rows are competencies, columns candidates
    comps_list = [c['name'] for c in comps]
    candidates = [r['name'] for r in results]
    heat_rows = []
    for comp in comps_list:
        row = {"Competency": comp}
        for cand in candidates:
            row[cand] = heatmap.get(comp, {}).get(cand, "")
        heat_rows.append(row)
    df_heat = pd.DataFrame(heat_rows)
    # write to excel in-memory
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df_results.to_excel(writer, sheet_name="Results", index=False)
        df_heat.to_excel(writer, sheet_name="Heatmap", index=False)
        writer.save()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="jd_cv_match.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=True)
