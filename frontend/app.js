// API base 讀寫（可從 localStorage 設定）
function getApiBase(){
  // 若前端由 FastAPI 同源提供，直接使用同源
  const sameOrigin = window.location.origin;
  return localStorage.getItem('bioflow_api_base') || window.API_BASE_OVERRIDE || sameOrigin;
}
function setApiBase(v){ localStorage.setItem('bioflow_api_base', v); }

const els = {
  authState: document.getElementById('auth-state'),
  apiIndicator: document.getElementById('api-indicator'),
  apiBaseInput: document.getElementById('api-base'),
  btnSaveApi: document.getElementById('btn-save-api'),
  btnLogin: document.getElementById('btn-login'),
  btnRegister: document.getElementById('btn-register'),
  btnLogout: document.getElementById('btn-logout'),
  loginUsername: document.getElementById('login-username'),
  loginPassword: document.getElementById('login-password'),
  regUsername: document.getElementById('register-username'),
  regPassword: document.getElementById('register-password'),
  fileInput: document.getElementById('file-input'),
  btnStart: document.getElementById('btn-start'),
  status: document.getElementById('status'),
  jobsEmpty: document.getElementById('jobs-empty'),
  jobsTable: document.getElementById('jobs-table'),
  jobsBody: document.getElementById('jobs-body'),
};

function getToken(){ return localStorage.getItem('bioflow_token'); }
function setToken(t){ localStorage.setItem('bioflow_token', t); }
function clearToken(){ localStorage.removeItem('bioflow_token'); }

function setAuthUI(){
  const token = getToken();
  const loggedIn = !!token;
  els.authState.textContent = loggedIn ? '已登入' : '未登入';
  els.btnLogout.disabled = !loggedIn;
  els.btnStart.disabled = !loggedIn || !els.fileInput.files.length;
  if (loggedIn) {
    loadJobs();
  } else {
    els.jobsBody.innerHTML = '';
    els.jobsTable.classList.add('hidden');
    els.jobsEmpty.classList.remove('hidden');
  }
}

function authHeaders(){
  const t = getToken();
  return t ? { 'Authorization': `Bearer ${t}` } : {};
}

async function checkHealth(){
  const base = getApiBase();
  els.apiBaseInput.value = base;
  try{
    const resp = await fetch(`${base}/health`);
    if(!resp.ok) throw new Error(await resp.text());
    els.apiIndicator.textContent = `API: ${base} ✅`;
  }catch(e){
    els.apiIndicator.textContent = `API: ${base} ❌ (${e})`;
  }
}

async function login(){
  const username = els.loginUsername.value.trim();
  const password = els.loginPassword.value.trim();
  if(!username || !password){ alert('請輸入帳號與密碼'); return; }
  try{
    // 先試 JSON 版
    let resp = await fetch(`${getApiBase()}/auth/login-json`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if(!resp.ok && resp.status !== 401){
      // 後端可能尚未更新或 CORS 預檢被擋，降級 query 參數 POST
      resp = await fetch(`${getApiBase()}/auth/login?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, { method: 'POST' });
    }
    if(!resp.ok && resp.status !== 401){
      // 再降級為 GET（避免某些環境的預檢問題）
      resp = await fetch(`${getApiBase()}/auth/login?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`);
    }
    if(!resp.ok){
      const t = await resp.text();
      throw new Error(t);
    }
    const data = await resp.json();
    if(data && data.access_token){
      setToken(data.access_token);
      setAuthUI();
      alert('登入成功');
    }else{
      alert('登入成功但未回傳 token');
    }
  }catch(e){
    alert(`登入失敗: ${e}`);
  }
}

async function registerUser(){
  const username = els.regUsername.value.trim();
  const password = els.regPassword.value.trim();
  if(!username || !password){ alert('請輸入帳號與密碼'); return; }
  try{
    // 先試 JSON 版
    let resp = await fetch(`${getApiBase()}/auth/register-json`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    if(!resp.ok && resp.status !== 409){
      // 降級 query 參數 POST
      resp = await fetch(`${getApiBase()}/auth/register?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`, { method: 'POST' });
    }
    if(!resp.ok && resp.status !== 409){
      // 再降級為 GET
      resp = await fetch(`${getApiBase()}/auth/register?username=${encodeURIComponent(username)}&password=${encodeURIComponent(password)}`);
    }
    if(!resp.ok){
      const t = await resp.text();
      throw new Error(t);
    }
    alert('註冊成功，請使用上方登入');
  }catch(e){
    alert(`註冊失敗: ${e}`);
  }
}

async function startAnalysis(){
  const file = els.fileInput.files[0];
  if(!file){ alert('請選擇 CSV 檔'); return; }
  els.status.textContent = '上傳中...';
  try{
    const formData = new FormData();
    formData.append('file', file, file.name);
    const resp = await fetch(`${getApiBase()}/upload-csv/`, {
      method: 'POST',
      headers: authHeaders(),
      body: formData
    });
    const data = await resp.json();
    if(!resp.ok){ throw new Error(data.detail || JSON.stringify(data)); }
    const jobId = data.job_id;
    els.status.textContent = `任務建立成功：${jobId}，分析中...`;
    await pollJob(jobId);
    await loadJobs();
  }catch(e){
    els.status.textContent = `錯誤：${e}`;
  }
}

async function pollJob(jobId){
  // 後端在同一請求裡處理計算，回傳狀態 queued；這裡輪詢直到 finished/failed
  try{
    for(let i=0;i<60;i++){
      const resp = await fetch(`${getApiBase()}/jobs/${encodeURIComponent(jobId)}`, {
        headers: authHeaders()
      });
      if(!resp.ok){
        const t = await resp.text();
        els.status.textContent = `狀態錯誤：${t}`;
        return;
      }
      const data = await resp.json();
      const status = data.status || 'unknown';
      els.status.textContent = `當前狀態：${status}`;
      if(status === 'finished'){
        els.status.textContent = `分析完成！摘要：${data.summary ?? ''}`;
        return;
      }
      if(status === 'failed'){
        els.status.textContent = '分析失敗';
        return;
      }
      await new Promise(r => setTimeout(r, 1000));
    }
  }catch(e){
    els.status.textContent = `輪詢錯誤：${e}`;
  }
}

async function loadJobs(){
  try{
    const resp = await fetch(`${getApiBase()}/jobs`, { headers: authHeaders() });
    if(!resp.ok){ throw new Error(await resp.text()); }
    const jobs = await resp.json();
    renderJobs(jobs);
  }catch(e){
    els.jobsBody.innerHTML = '';
    els.jobsTable.classList.add('hidden');
    els.jobsEmpty.classList.remove('hidden');
  }
}

function renderJobs(jobs){
  if(!jobs || jobs.length === 0){
    els.jobsBody.innerHTML = '';
    els.jobsTable.classList.add('hidden');
    els.jobsEmpty.classList.remove('hidden');
    return;
  }
  els.jobsEmpty.classList.add('hidden');
  els.jobsTable.classList.remove('hidden');
  els.jobsBody.innerHTML = '';
  for(const j of jobs){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${j.job_id}</td>
      <td><span class="badge ${j.status==='finished'?'success':(j.status==='failed'?'failed':'')}">${j.status}</span></td>
      <td>${j.summary ?? ''}</td>
      <td>${j.created_at}</td>
      <td>${j.result_filename?`<a class="link" href="#" data-job="${j.job_id}" data-kind="result">下載</a>`:''}</td>
      <td>${j.plot_filename?`<a class="link" href="#" data-job="${j.job_id}" data-kind="plot">下載</a>`:''}</td>
      <td><button data-del="${j.job_id}" class="danger">刪除</button></td>
    `;
    els.jobsBody.appendChild(tr);
  }
}

async function downloadByJob(jobId, kind){
  try{
    const url = `${getApiBase()}/jobs/${encodeURIComponent(jobId)}?download=true&kind=${encodeURIComponent(kind)}`;
    const resp = await fetch(url, { headers: authHeaders() });
    if(!resp.ok){ throw new Error(await resp.text()); }
    const blob = await resp.blob();
    const cd = resp.headers.get('Content-Disposition') || '';
    const suggested = /filename="?([^";]+)"?/i.exec(cd)?.[1] || `${kind}_${jobId}`;
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = suggested;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }catch(e){
    alert(`下載失敗：${e}`);
  }
}

async function deleteJob(jobId){
  if(!confirm(`確定刪除 ${jobId} ?`)) return;
  try{
    const resp = await fetch(`${getApiBase()}/jobs/${encodeURIComponent(jobId)}`, {
      method: 'DELETE',
      headers: authHeaders()
    });
    if(!resp.ok && resp.status !== 204){
      throw new Error(await resp.text());
    }
    await loadJobs();
  }catch(e){
    alert(`刪除失敗：${e}`);
  }
}

// Events
els.btnLogin.addEventListener('click', login);
els.btnRegister.addEventListener('click', registerUser);
els.btnLogout.addEventListener('click', () => { clearToken(); setAuthUI(); });
els.fileInput.addEventListener('change', () => { els.btnStart.disabled = !getToken() || !els.fileInput.files.length; });
els.btnStart.addEventListener('click', startAnalysis);
els.btnSaveApi.addEventListener('click', () => { const v = els.apiBaseInput.value.trim(); if(v){ setApiBase(v); checkHealth(); }});

els.jobsBody.addEventListener('click', (e) => {
  const t = e.target;
  if(t.matches('a[data-job]')){
    e.preventDefault();
    downloadByJob(t.getAttribute('data-job'), t.getAttribute('data-kind'));
  }
  if(t.matches('button[data-del]')){
    deleteJob(t.getAttribute('data-del'));
  }
});

// Init
setAuthUI();
checkHealth();
// Auto refresh jobs every 10s when logged in
setInterval(() => { if(getToken()) loadJobs(); }, 10000);


