
const form = document.getElementById('uploadForm');
const resultsDiv = document.getElementById('results');
const exportBtn = document.getElementById('exportBtn');
let lastPayload = null;

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const jd = document.getElementById('jd').files[0];
  const cvs = document.getElementById('cvs').files;
  const model = document.getElementById('model').value;
  if (!jd) return alert('Please upload JD');
  if (!cvs.length) return alert('Please upload at least one CV');
  if (cvs.length > 10) return alert('Maximum 10 CVs allowed');
  const fd = new FormData();
  fd.append('jd', jd);
  for (let i=0;i<cvs.length;i++) fd.append('cvs', cvs[i]);
  fd.append('model', model);
  document.getElementById('submitBtn').disabled = true;
  resultsDiv.innerHTML = '<p>Processing... (this may take 5–25s depending on model)</p>';
  try {
    const resp = await fetch('/process', { method:'POST', body: fd });
    const data = await resp.json();
    if (data.error) {
      resultsDiv.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
    } else {
      lastPayload = data; // store for export
      renderResults(data);
      exportBtn.disabled = false;
    }
  } catch (err) {
    resultsDiv.innerHTML = `<pre>${err.toString()}</pre>`;
  } finally {
    document.getElementById('submitBtn').disabled = false;
  }
});

exportBtn.addEventListener('click', async () => {
  if (!lastPayload) return alert('No results to export');
  // POST JSON to /export and download the returned xlsx
  try {
    exportBtn.disabled = true;
    const resp = await fetch('/export', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(lastPayload)
    });
    if (!resp.ok) {
      const text = await resp.text();
      alert('Export failed: ' + text);
      return;
    }
    const blob = await resp.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'jd_cv_match.xlsx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  } catch (err) {
    alert('Export error: ' + err.toString());
  } finally {
    exportBtn.disabled = false;
  }
});

function renderResults(data){
  const comps = data.competencies || [];
  const results = data.results || [];
  const heatmap = data.heatmap || {};
  let html = '<h2>Competencies & Weights</h2>';
  html += '<div class="weights"><strong>Competency (weight)</strong><br/>';
  for (const c of comps){
    html += `<div style="margin-top:6px;"><strong>${c.name}</strong> (${c.weight}) — <em>${c.description}</em></div>`;
  }
  html += '</div>';
  html += '<h2 style="margin-top:16px">Match Results</h2>';
  html += '<table><thead><tr><th>Candidate</th><th>Weighted Match %</th><th>Palantir %</th><th>Strengths</th><th>Gaps</th></tr></thead><tbody>';
  for (const r of results){
    html += '<tr>';
    html += `<td>${r.name}</td>`;
    html += `<td>${r.weighted_match_pct}</td>`;
    html += `<td>${r.palantir_knowledge_pct || 0}</td>`;
    html += `<td>${(r.strengths || []).slice(0,6).join(', ')}</td>`;
    html += `<td>${(r.gaps || []).slice(0,6).join(', ')}</td>`;
    html += '</tr>';
  }
  html += '</tbody></table>';
  html += '<h2 style="margin-top:18px">Heatmap</h2>';
  html += '<table><thead><tr><th>Competency</th>';
  const candidates = results.map(r=>r.name);
  for (const c of candidates) html += `<th>${c}</th>`;
  html += '</tr></thead><tbody>';
  for (const comp of comps){
    html += `<tr><td>${comp.name}</td>`;
    for (const cand of candidates){
      const val = (heatmap[comp.name] && heatmap[comp.name][cand]) || 'Gap';
      const cls = (val.toLowerCase().includes('full')? 'full': (val.toLowerCase().includes('partial')? 'partial' : 'gap'));
      html += `<td><span class="heatcell ${cls}">${val}</span></td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  document.getElementById('results').innerHTML = html;
}
