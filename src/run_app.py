from __future__ import annotations

import tempfile
from pathlib import Path

from src import api
from src import extra_api  # noqa: F401  # registers saved-review/metrics endpoints
from src import multi_photo_api  # noqa: F401  # registers /api/reviews/photos


def _replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"web patch not found: {label}")
    return text.replace(old, new, 1)


def _build_web_ui() -> Path:
    source = api.UI_INDEX_PATH.read_text(encoding="utf-8")

    source = source.replace('<title>MathCheck AI — ЕГЭ №13</title>', '<title>MathCheck — ЕГЭ №13</title>', 1)
    source = source.replace('<h1>MathCheck AI</h1>', '<h1>MathCheck</h1>', 1)

    # ID нужен API, но пользователю он не нужен.
    source = _replace_once(
        source,
        '<label for="studentId">ID ученика</label><input id="studentId" class="input" value="student-001">',
        '<input id="studentId" type="hidden" value="student-local">',
        "student id field",
    )

    # Диагностику оставляем доступной, чтобы при ошибке было видно запрос и ответ сервера.
    source = _replace_once(
        source,
        '<details><summary>Технические данные / JSON для отправки</summary>',
        '<details><summary>Диагностика: запрос и ответ сервера</summary>',
        "technical details",
    )

    source = source.replace('class="version"', 'class="version hidden"', 1)

    # Служебные фрагменты OCR нужны внутри ответа, но пользователю их не показываем.
    source = _replace_once(
        source,
        '<div id="chips" class="chips"></div>',
        '<div id="chips" class="chips hidden"></div>',
        "ocr fragments",
    )

    source = _replace_once(
        source,
        '<h2>3. Результат проверки</h2><p>Формулы показываются через LaTeX, а исправление стоит сразу под тем пунктом, к которому относится.</p>',
        '<h2>3. Результат проверки</h2>',
        "result subtitle",
    )

    # История теперь показывается прямо из SQLite. Каждую запись можно открыть.
    source = _replace_once(
        source,
        '<section id="historyCard" class="card"><div class="head"><div><h2>Предыдущие проверки</h2><p>Новая загрузка не стирает законченные результаты.</p></div><button id="clearHistoryBtn" class="btn ghost">Очистить историю</button></div>',
        '<section id="historyCard" class="card"><div class="head"><div><h2>Предыдущие проверки</h2><p>Сохранено в SQLite. Нажми на проверку, чтобы снова открыть полный результат.</p></div><button id="clearHistoryBtn" class="btn ghost">Обновить</button></div>',
        "history header",
    )
    source = source.replace(
        '</style>',
        '.historyItem{cursor:pointer;transition:.16s ease}.historyItem:hover{border-color:rgba(245,158,11,.42);background:rgba(245,158,11,.05);transform:translateY(-1px)}.historyItem:focus{outline:2px solid rgba(245,158,11,.45);outline-offset:2px}.historyOpen{margin-top:8px;color:#fde68a;font-size:10.5px;font-weight:850}.historyDb{display:inline-flex;align-items:center;gap:5px;margin-left:6px;padding:2px 6px;border-radius:999px;border:1px solid rgba(52,211,153,.24);color:#a7f3d0;background:rgba(52,211,153,.06);font-size:9.5px;font-weight:850}\n</style>',
        1,
    )

    source = _replace_once(
        source,
        '<input id="file" type="file" accept="image/png,image/jpeg,image/webp">',
        '<input id="file" type="file" accept="image/png,image/jpeg,image/webp" multiple>',
        "file input",
    )
    source = _replace_once(
        source,
        'id="fileName">Выбери PNG, JPG или WEBP<',
        'id="fileName">Выбери одно или несколько фото<',
        "file label",
    )
    source = _replace_once(
        source,
        '<div class="paneTitle">Исходный скан</div>',
        '<div class="paneTitle">Исходные сканы · в порядке загрузки</div>',
        "scan title",
    )
    source = source.replace('>2.9.7.17<', '>2.9.7.20<', 1)

    source = _replace_once(
        source,
        "const $=id=>document.getElementById(id);const HISTORY_KEY='mathcheck-ege13-result-history-v3';const st={file:null,url:null,ocr:null,final:null,timer:null,start:0,activeMathTarget:'equationText',currentArchived:false,history:[],progressTimer:null};let mathRetry=0;",
        "const $=id=>document.getElementById(id);const HISTORY_KEY='mathcheck-ege13-result-history-v3';const st={file:null,files:[],url:null,urls:[],ocr:null,final:null,timer:null,start:0,activeMathTarget:'equationText',currentArchived:false,history:[],progressTimer:null,lastScanRequest:null};let mathRetry=0;",
        "state",
    )

    # Старую browser-local историю заменяем реальными записями SQLite.
    history_start = source.find("function loadHistory(){")
    history_end = source.find("function setActiveMathTarget", history_start)
    if history_start == -1 or history_end == -1:
        raise RuntimeError("web patch not found: history functions")
    sqlite_history_js = r'''
async function loadHistory(showToast=false){const grid=$('historyGrid');if(grid){grid.replaceChildren();const e=document.createElement('div');e.className='emptyHistory';e.textContent='Загружаю историю из SQLite…';grid.append(e)}try{const sid=$('studentId').value.trim()||'student-local';const data=await json(await fetch(`/api/students/${encodeURIComponent(sid)}/history?limit=20`));st.history=Array.isArray(data.reviews)?data.reviews:[];renderHistory();if(showToast)toast(`SQLite: ${st.history.length} проверок`)}catch(e){st.history=[];if(grid){grid.replaceChildren();const x=document.createElement('div');x.className='emptyHistory';x.textContent='Не удалось загрузить историю из SQLite: '+e.message;grid.append(x)}if(showToast)toast('Не удалось обновить историю')}}
function saveHistory(){}
function reportSnapshot(data){return data||null}
function archiveCurrentResult(){loadHistory()}
async function openSavedReview(reviewId,card){if(!reviewId)return;const old=card?.querySelector('.historyOpen')?.textContent;if(card?.querySelector('.historyOpen'))card.querySelector('.historyOpen').textContent='Открываю из SQLite…';try{const d=await json(await fetch(`/api/reviews/${encodeURIComponent(reviewId)}`));st.final=d;st.currentArchived=true;$('finalJson').textContent=pretty({source:'sqlite',response:d});$('resultCard').classList.remove('hidden');render(d);if(d.stage_timings)renderStageProgress(d.stage_timings);progress(3);$('resultCard').scrollIntoView({behavior:'smooth'})}catch(e){toast('Не удалось открыть проверку: '+e.message)}finally{if(card?.querySelector('.historyOpen'))card.querySelector('.historyOpen').textContent=old||'Открыть результат →'}}
function renderHistory(){const grid=$('historyGrid');grid.replaceChildren();if(!st.history.length){const e=document.createElement('div');e.className='emptyHistory';e.textContent='В SQLite пока нет сохранённых проверок.';grid.append(e);return}st.history.forEach(item=>{const card=document.createElement('div');card.className='historyItem';card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label','Открыть сохранённую проверку');const head=document.createElement('div');head.className='historyHead';const left=document.createElement('div');left.innerHTML='<div class="historyMeta"></div><div class="historySummary"></div>';const dt=new Date(item.created_at||Date.now());left.querySelector('.historyMeta').textContent=dt.toLocaleString('ru-RU');const metaBadge=document.createElement('span');metaBadge.className='historyDb';metaBadge.textContent='SQLite';left.querySelector('.historyMeta').append(metaBadge);left.querySelector('.historySummary').textContent=item.summary||item.error_class||'Проверка завершена';const score=document.createElement('div');score.className='historyScore';score.textContent=item.final_score==null?'—':`${item.final_score}/${item.max_score??2}`;head.append(left,score);const parts=document.createElement('div');parts.className='historyParts';parts.textContent=[item.status?`Статус: ${statusRu(item.status)}`:'',item.task_type==='ege_13'?'ЕГЭ №13':''].filter(Boolean).join(' · ');const open=document.createElement('div');open.className='historyOpen';open.textContent='Открыть результат →';card.append(head,parts,open);card.addEventListener('click',()=>openSavedReview(item.review_id,card));card.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();openSavedReview(item.review_id,card)}});grid.append(card)})}
'''.strip()
    source = source[:history_start] + sqlite_history_js + "\n" + source[history_end:]

    helpers = r'''
function releasePhotoUrls(){(st.urls||[]).forEach(u=>{try{URL.revokeObjectURL(u)}catch{}});if(st.url&&!(st.urls||[]).includes(st.url)){try{URL.revokeObjectURL(st.url)}catch{}}st.urls=[];st.url=null;const scan=$('full')?.parentElement;if(scan)scan.querySelectorAll('.multiPage').forEach(x=>x.remove())}
function showSelectedPhotos(files){releasePhotoUrls();st.files=files;st.file=files[0]||null;st.urls=files.map(f=>URL.createObjectURL(f));st.url=st.urls[0]||null;if(st.url){$('mini').src=st.url;$('full').src=st.url}const scan=$('full')?.parentElement;if(scan){scan.style.gap='10px';files.slice(1).forEach((_,i)=>{const img=document.createElement('img');img.className='multiPage';img.src=st.urls[i+1];img.alt=`Страница ${i+2}`;img.style.marginTop='10px';scan.append(img)})}}
function scanRequestInfo(files){return {endpoint:'/api/reviews/photos',method:'POST',task_type:'ege_13',student_id:$('studentId').value.trim()||'student-local',images:files.map(f=>({name:f.name,type:f.type,size_bytes:f.size}))}}
function showScanDebug(response=null,error=null){const data={request:st.lastScanRequest};if(response!==null)data.response=response;if(error)data.error=String(error?.message||error);$('ocrJson').textContent=pretty(data)}
'''.strip()
    source = _replace_once(source, "function clearCurrent(){", helpers + "\nfunction clearCurrent(){", "multi helpers")

    source = _replace_once(
        source,
        "if(st.url)URL.revokeObjectURL(st.url);st.url=null;st.file=null;$('file').value='';$('mini').removeAttribute('src');$('full').removeAttribute('src');$('fileName').textContent='Выбери PNG, JPG или WEBP';",
        "releasePhotoUrls();st.file=null;st.files=[];st.lastScanRequest=null;$('file').value='';$('mini').removeAttribute('src');$('full').removeAttribute('src');$('fileName').textContent='Выбери одно или несколько фото';",
        "clear photos",
    )

    old_change = "$('file').addEventListener('change',e=>{const f=e.target.files?.[0];if(!f)return;archiveCurrentResult();stopProgressPolling();st.ocr=null;st.final=null;st.currentArchived=false;$('confirmCard').classList.add('hidden');$('resultCard').classList.add('hidden');$('preflightBox').classList.add('hidden');$('stageProgress').classList.add('hidden');$('ocrJson').textContent='—';$('finalJson').textContent='—';$('equationText').value='';$('intervalText').value='';$('solutionText').value='';st.file=f;if(st.url)URL.revokeObjectURL(st.url);st.url=URL.createObjectURL(f);$('mini').src=st.url;$('full').src=st.url;$('fileName').textContent=`${f.name} · ${(f.size/1024).toFixed(0)} КБ`;$('scanBtn').disabled=false;progress(1)});"
    new_change = "$('file').addEventListener('change',e=>{const files=Array.from(e.target.files||[]);if(!files.length)return;if(files.length>8){toast('Можно загрузить максимум 8 фото одной работы');$('file').value='';return}archiveCurrentResult();stopProgressPolling();st.ocr=null;st.final=null;st.currentArchived=false;st.lastScanRequest=null;$('confirmCard').classList.add('hidden');$('resultCard').classList.add('hidden');$('preflightBox').classList.add('hidden');$('stageProgress').classList.add('hidden');$('ocrJson').textContent='—';$('finalJson').textContent='—';$('equationText').value='';$('intervalText').value='';$('solutionText').value='';showSelectedPhotos(files);const total=files.reduce((s,f)=>s+f.size,0);$('fileName').textContent=files.length===1?`${files[0].name} · ${(files[0].size/1024).toFixed(0)} КБ`:`${files.length} фото · ${(total/1024/1024).toFixed(1)} МБ`;$('scanBtn').disabled=false;progress(1)});"
    source = _replace_once(source, old_change, new_change, "file change")

    old_scan = "$('scanBtn').addEventListener('click',async()=>{if(!st.file)return;$('scanBtn').disabled=true;busy('scanStatus','scanStatusText','Распознаю работу');try{const fd=new FormData();fd.append('image',st.file);fd.append('student_id',$('studentId').value.trim()||'student-001');fd.append('task_type','ege_13');const d=await json(await fetch('/api/reviews/photo',{method:'POST',body:fd}));st.ocr=d;$('ocrJson').textContent=pretty(d);if((d.errors||[]).length&&!(d.transcript||'').trim())throw new Error(d.errors[0]);fillDraft();$('chips').replaceChildren();(d.task_uncertain_fragments||[]).concat(d.uncertain_fragments||[]).forEach(x=>{const c=document.createElement('span');c.className='chip';c.textContent=x;$('chips').append(c)});if(d.stage_timings)renderStageProgress(d.stage_timings);$('confirmCard').classList.remove('hidden');progress(2);$('confirmCard').scrollIntoView({behavior:'smooth'});$('equationText').focus()}catch(e){toast('Ошибка: '+e.message)}finally{idle('scanStatus');$('scanBtn').disabled=false}});"
    new_scan = "$('scanBtn').addEventListener('click',async()=>{const files=(st.files&&st.files.length?st.files:[st.file]).filter(Boolean);if(!files.length)return;$('scanBtn').disabled=true;busy('scanStatus','scanStatusText',files.length===1?'Распознаю работу':`Распознаю ${files.length} фото одним проходом`);st.lastScanRequest=scanRequestInfo(files);showScanDebug();try{const fd=new FormData();files.forEach(f=>fd.append('images',f));fd.append('student_id',$('studentId').value.trim()||'student-local');fd.append('task_type','ege_13');const d=await json(await fetch('/api/reviews/photos',{method:'POST',body:fd}));st.ocr=d;showScanDebug(d);if((d.errors||[]).length&&!(d.transcript||'').trim())throw new Error(d.errors[0]);fillDraft();$('chips').replaceChildren();(d.task_uncertain_fragments||[]).concat(d.uncertain_fragments||[]).forEach(x=>{const c=document.createElement('span');c.className='chip';c.textContent=x;$('chips').append(c)});if(d.stage_timings)renderStageProgress(d.stage_timings);$('confirmCard').classList.remove('hidden');progress(2);$('confirmCard').scrollIntoView({behavior:'smooth'});$('equationText').focus()}catch(e){showScanDebug(st.ocr,e);toast('Ошибка: '+e.message)}finally{idle('scanStatus');$('scanBtn').disabled=false}});"
    source = _replace_once(source, old_scan, new_scan, "scan click")

    # На финальном этапе показываем не только ответ, но и точный payload,
    # отправленный после ручного подтверждения. Это позволяет сразу отличить
    # ошибку модели от ситуации, когда браузер отправил старое значение поля.
    confirm_payload = "const task=buildTask(eq,iv);const payload={review_id:st.ocr.review_id,student_id:$('studentId').value.trim()||st.ocr.student_id||'student-001',task_type:'ege_13',confirmed_task_equation:eq,confirmed_interval:iv,task_statement:task,confirmed_task_statement:task,original_task_statement:st.ocr.original_task_statement||'',original_transcript:st.ocr.original_transcript||st.ocr.transcript||'',confirmed_transcript:sol};busy('gradeStatus','gradeStatusText','Проверяю решение');"
    source = _replace_once(
        source,
        confirm_payload,
        confirm_payload.replace(";busy('gradeStatus'", ";$('finalJson').textContent=pretty({request:payload});busy('gradeStatus'"),
        "confirm request debug",
    )
    source = _replace_once(
        source,
        "stopProgressPolling();st.final=d;st.currentArchived=false;$('finalJson').textContent=pretty(d);",
        "stopProgressPolling();st.final=d;st.currentArchived=false;$('finalJson').textContent=pretty({request:payload,response:d});loadHistory();",
        "confirm response debug",
    )

    source = _replace_once(
        source,
        "$('clearHistoryBtn').addEventListener('click',()=>{st.history=[];saveHistory();renderHistory();toast('История очищена')});loadHistory();",
        "$('clearHistoryBtn').addEventListener('click',()=>loadHistory(true));loadHistory();",
        "history refresh",
    )

    output = Path(tempfile.gettempdir()) / "mathcheck-index.html"
    output.write_text(source, encoding="utf-8")
    return output


api.UI_INDEX_PATH = _build_web_ui()
app = api.app
