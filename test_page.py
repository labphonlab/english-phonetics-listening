"""聞き取りテストのページ（lecture03/test.html）を作る。build_web.py の main() から呼ぶ。

練習ページと同じ語対（3.1 の18対＋3.2 の8対）を、順番と流れる語をランダムにして二択で出す。
最後の問題に答えた時点で、解答を Apps Script（web/gas/Code.gs）へ自動で送る。送信先 URL は web/config.js。
"""
import json

TEST_ID = "l03-listening"   # スプレッドシートの「テスト」列に入る名前
MAX_PLAYS = 3              # 1問で聞ける回数（最初の自動再生を含む）


def items(W, S31, S32):
    out = []
    for contrast, pairs in S31:
        for a, b in pairs:
            out.append({"sec": "3.1", "contrast": contrast, "a": a, "b": b})
    for pre, a, b, post in S32:
        out.append({"sec": "3.2", "contrast": "文脈の語対", "a": a, "b": b})
    for it in out:
        for k in ("a", "b"):
            key, mean = W[it[k]]
            assert key, it[k]          # 録音の無い語は出さない
            it[k + "Src"] = f"audio/{key}.mp3"
            it[k + "Ja"] = mean
        it["kind"] = "pair"
    return out


CSS = """
:root{--bg:#F6F4EF;--card:#FFFFFF;--ink:#1B2238;--sub:#5B6573;--line:#E2DED5;--btn:#F2A93B;--btn-ink:#1B2238;--hd:#2B3A67;
--ok:#1F8A7D;--ng:#D6452B;--warn:#FFF3D6}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15181F;--card:#1F242E;--ink:#ECEEF2;--sub:#A3ABB8;--line:#323947;
--btn:#E9A23A;--btn-ink:#1B1B1B;--hd:#3A4C8A;--ok:#4CC3B3;--ng:#FF7A63;--warn:#3A3220}}
:root[data-theme="dark"]{--bg:#15181F;--card:#1F242E;--ink:#ECEEF2;--sub:#A3ABB8;--line:#323947;--btn:#E9A23A;--btn-ink:#1B1B1B;--hd:#3A4C8A;--ok:#4CC3B3;--ng:#FF7A63;--warn:#3A3220}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Segoe UI",sans-serif;
line-height:1.6;font-size:17px;padding-bottom:env(safe-area-inset-bottom)}
header{background:var(--hd);color:#fff;padding:calc(16px + env(safe-area-inset-top)) 16px 14px}
header p{margin:0;font-size:14px;opacity:.85}header h1{margin:2px 0 0;font-size:23px;line-height:1.3}
main{max-width:560px;margin:0 auto;padding:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;margin:0 0 14px}
label{display:block;font-weight:700;margin:4px 0 6px}
input{width:100%;font:inherit;font-size:18px;padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--bg);color:var(--ink);margin-bottom:12px}
button{font:inherit;color:inherit;-webkit-tap-highlight-color:transparent;cursor:pointer;touch-action:manipulation}
.main{width:100%;min-height:56px;border:0;border-radius:14px;background:var(--btn);color:var(--btn-ink);font-size:19px;font-weight:700}
.main:disabled{opacity:.45}
.sub{color:var(--sub);font-size:14px}
.err{color:var(--ng);font-size:14px;min-height:1.2em;margin:4px 0 8px}
.banner{background:var(--warn);border-radius:10px;padding:10px 12px;font-size:14px;margin-bottom:14px}
.prog{display:flex;justify-content:space-between;font-size:15px;color:var(--sub);margin-bottom:6px}
.bar{height:8px;background:var(--line);border-radius:99px;overflow:hidden;margin-bottom:16px}.bar i{display:block;height:100%;background:var(--btn);width:0}
.again{width:100%;min-height:52px;border:2px solid var(--btn);border-radius:14px;background:transparent;font-size:17px;font-weight:700;margin-bottom:16px}
.again:disabled{opacity:.4}
.q{font-size:18px;font-weight:700;text-align:center;margin:0 0 12px}
.choices{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.choice{min-height:96px;border:0;border-radius:16px;background:var(--btn);color:var(--btn-ink);display:flex;flex-direction:column;align-items:center;justify-content:center;
box-shadow:0 2px 0 rgba(0,0,0,.15);padding:8px}
.choice .en{font-size:26px;font-weight:700;line-height:1.15}.choice .ja{font-size:13px;opacity:.85}
.choice:active{transform:translateY(1px)}
.score{font-size:44px;font-weight:800;text-align:center;margin:4px 0}
.status{text-align:center;font-weight:700;margin:6px 0 12px}.ok{color:var(--ok)}.ng{color:var(--ng)}
ul.wrong{padding-left:0;list-style:none;margin:0}ul.wrong li{border-top:1px solid var(--line);padding:8px 0;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
ul.wrong button{border:1px solid var(--line);border-radius:999px;background:var(--bg);padding:4px 10px;font-size:14px}
[hidden]{display:none!important}
"""

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#2B3A67">
<title>{title}</title>
<style>{css}</style></head>
<body>
<header><p>英語音声学　{lecture}</p><h1>{title}</h1></header>
<main>
<div class="banner" id="demo" hidden>送信先が未設定のため、いまはお試し表示です（結果は送られません）。</div>

<section id="start">
 <div class="card">
  <p style="margin-top:0">{intro}全 <b>{total}</b> 問。各問 <b>{maxplays}</b> 回まで聞けます。最後の問題に答えると、結果が自動で先生に送信されます。</p>
  <p class="sub">イヤホンを使い、静かな場所で受けてください。途中でページを閉じると最初からになります。</p>
 </div>
 <div class="card">
  <label for="sid">学籍番号</label>
  <input id="sid" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="例：24A0001">
  <label for="nm">氏名</label>
  <input id="nm" autocomplete="name" placeholder="例：目白 花子">
  <p class="err" id="err"></p>
  <button class="main" id="go">テストをはじめる</button>
 </div>
</section>

<section id="quiz" hidden>
 <div class="prog"><span id="no"></span><span id="who"></span></div>
 <div class="bar"><i id="barin"></i></div>
 <button class="again" id="again">▶ もう一度聞く</button>
 <p class="q" id="prompt"></p>
 <div class="choices" id="choices"></div>
</section>

<section id="done" hidden>
 <div class="card">
  <p class="sub" style="text-align:center;margin:0" id="who2"></p>
  <p class="score" id="score"></p>
  <p class="status" id="status">送信しています…</p>
  <button class="main" id="resend" hidden>もう一度送信する</button>
 </div>
 <div class="card" id="wrongbox">
  <p style="margin:0 0 6px;font-weight:700">間違えた問題（聞き直せます）</p>
  <ul class="wrong" id="wrong"></ul>
 </div>
 <button class="main" id="retry">もう一度受ける</button>
</section>
</main>
<script src="../config.js"></script>
<script>
const ITEMS={items};
const TEST_ID="{testid}", MAX_PLAYS={maxplays};
const API=(window.LISTENING_TEST_CONFIG||{}).apiUrl||"";
{js}
</script>
</body></html>
"""

JS = r"""
const $=id=>document.getElementById(id);
const store={get(k){try{return JSON.parse(localStorage.getItem(k))}catch(e){return null}},set(k,v){try{localStorage.setItem(k,JSON.stringify(v))}catch(e){}}};
if(!API)$("demo").hidden=false;
const me=store.get("lt-me")||{};$("sid").value=me.sid||"";$("nm").value=me.nm||"";

// 音声（同じファイルは使い回す）
const cache={};let cur=null;
function aud(src){if(!cache[src]){const a=new Audio(src);a.preload="auto";cache[src]=a}return cache[src]}
function play(src){if(cur){cur.pause()}const a=aud(src);cur=a;a.currentTime=0;a.play().catch(()=>{})}

// 受付状況（「設定」シートで止めているときは始められない）
if(API){fetch(API).then(r=>r.json()).then(j=>{if(j&&j.accepting===false){$("go").disabled=true;$("err").textContent="いまは受け付けていません。"}}).catch(()=>{})}

let order=[],k=0,res=[],t0=0,tq=0,plays=0,startedAt=0,sub=null;
function shuffle(a){for(let i=a.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[a[i],a[j]]=[a[j],a[i]]}return a}
function normId(s){return s.replace(/[Ａ-Ｚａ-ｚ０-９]/g,c=>String.fromCharCode(c.charCodeAt(0)-0xFEE0)).replace(/\s+/g,"").toUpperCase()}

$("go").onclick=()=>{
  const sid=normId($("sid").value),nm=$("nm").value.trim();
  if(!sid||!nm){$("err").textContent="学籍番号と氏名を入力してください。";return}
  if(!/^[0-9A-Z-]{4,16}$/.test(sid)){$("err").textContent="学籍番号は半角の英数字で入力してください。";return}
  store.set("lt-me",{sid,nm});
  order=shuffle(ITEMS.map((it,i)=>Object.assign({},it,{target:Math.random()<.5?"a":"b"})));
  k=0;res=[];startedAt=Date.now();
  sub={action:"submit",testId:TEST_ID,submissionId:(crypto.randomUUID?crypto.randomUUID():String(Date.now())+Math.random().toString(36).slice(2)),
       studentId:sid,name:nm,startedAt,ua:navigator.userAgent};
  $("who").textContent=nm;$("start").hidden=true;$("quiz").hidden=false;window.scrollTo(0,0);
  ITEMS.forEach(it=>{[it.aSrc,it.bSrc,it.src].filter(Boolean).forEach(aud)});
  show();
};
function opts(it){
  if(it.kind==="count")return it.opts.map(o=>({en:o,ja:""}));
  return [{en:it.a,ja:it.aJa},{en:it.b,ja:it.bJa}];
}
function src(it){return it.kind==="count"?it.src:it[it.target+"Src"]}
function right(it){return it.kind==="count"?it.ans:it[it.target]}
function show(){
  const it=order[k];
  $("no").textContent="問 "+(k+1)+" / "+order.length;$("barin").style.width=(k/order.length*100)+"%";
  $("prompt").innerHTML=it.kind==="count"?"<span style='font-size:28px'>"+it.word+"</span><br>何音節に聞こえる？":"流れたのはどっち？";
  const box=$("choices");box.innerHTML="";
  opts(it).forEach((o,i)=>{const b=document.createElement("button");b.className="choice";b.disabled=true;
    b.innerHTML="<span class='en'>"+o.en+"</span>"+(o.ja?"<span class='ja'>"+o.ja+"</span>":"");b.onclick=()=>answer(i);box.appendChild(b)});
  setTimeout(()=>box.querySelectorAll(".choice").forEach(b=>b.disabled=false),350);  // 連打で次の問題に答えないように
  plays=0;tq=Date.now();hear();
}
function hear(){
  const it=order[k];if(plays>=MAX_PLAYS)return;
  plays++;play(src(it));
  $("again").disabled=plays>=MAX_PLAYS;$("again").textContent=plays>=MAX_PLAYS?"聞けるのはここまで":"▶ もう一度聞く（あと "+(MAX_PLAYS-plays)+" 回）";
}
$("again").onclick=hear;
function answer(i){
  const it=order[k];document.querySelectorAll(".choice").forEach(x=>x.disabled=true);
  res.push({sec:it.sec,contrast:it.contrast,a:it.kind==="count"?it.word:it.a,b:it.kind==="count"?"":it.b,
    target:right(it),answer:opts(it)[i].en,plays,ms:Date.now()-tq,tSrc:src(it)});
  k++;
  if(k<order.length){show()}else{finish()}
}
window.addEventListener("beforeunload",e=>{if(!$("quiz").hidden){e.preventDefault();e.returnValue=""}});

function finish(){
  if(cur)cur.pause();
  $("quiz").hidden=true;$("done").hidden=false;window.scrollTo(0,0);
  const score=res.filter(r=>r.answer===r.target).length;
  $("score").textContent=score+" / "+res.length;$("who2").textContent=sub.studentId+"　"+sub.name;
  const w=res.filter(r=>r.answer!==r.target);
  $("wrongbox").hidden=!w.length;
  $("wrong").innerHTML="";
  w.forEach(r=>{const li=document.createElement("li");
    li.innerHTML="<span>"+(r.b?r.a+" – "+r.b+"：流れたのは ":r.a+"：")+"<b>"+r.target+"</b>（答え "+r.answer+"）</span>";
    const bt=document.createElement("button");bt.textContent="▶ "+(r.b?r.target:r.a);bt.onclick=()=>play(r.tSrc);li.appendChild(bt);$("wrong").appendChild(li)});
  Object.assign(sub,{finishedAt:Date.now(),items:res.map(({tSrc,...r})=>r)});
  const pend=store.get("lt-pending")||[];pend.push(sub);store.set("lt-pending",pend);
  send();
}
async function post(body){
  for(let n=0;n<3;n++){
    try{const r=await fetch(API,{method:"POST",body:JSON.stringify(body)});const j=await r.json();if(j.ok)return j;if(j.error)throw Object.assign(new Error(j.error),{server:true})}
    catch(e){if(e.server)throw e;await new Promise(r=>setTimeout(r,1500*(n+1)))}
  }
  throw new Error("network");
}
async function send(){
  const st=$("status");$("resend").hidden=true;
  if(!API){st.className="status";st.textContent="お試し表示のため送信していません。";return}
  st.className="status";st.textContent="送信しています…";
  try{
    const j=await post(sub);
    store.set("lt-pending",(store.get("lt-pending")||[]).filter(p=>p.submissionId!==sub.submissionId));
    st.className="status ok";st.textContent="✓ 送信しました（"+j.attempt+"回目の受験として記録）";
  }catch(e){
    st.className="status ng";
    st.textContent=e.message==="closed"?"いまは受け付けていません。先生に伝えてください。":"送信できませんでした。電波のよい所で「もう一度送信する」を押してください。";
    $("resend").hidden=e.message==="closed";
  }
}
$("resend").onclick=send;
$("retry").onclick=()=>{$("done").hidden=true;$("start").hidden=false;window.scrollTo(0,0)};

// 前回送れなかった結果があれば、開いたときに送り直す
if(API){(store.get("lt-pending")||[]).forEach(p=>post(p).then(()=>store.set("lt-pending",(store.get("lt-pending")||[]).filter(x=>x.submissionId!==p.submissionId))).catch(()=>{}))}
"""


def render(its, test_id, lecture, title, intro):
    """its: 問題の並び（kind=pair か count）。test_id はスプレッドシートの「テスト」列に入る"""
    return (PAGE.replace("{items}", json.dumps(its, ensure_ascii=False)).replace("{total}", str(len(its)))
            .replace("{testid}", test_id).replace("{maxplays}", str(MAX_PLAYS))
            .replace("{lecture}", lecture).replace("{title}", title).replace("{intro}", intro)
            .replace("{css}", CSS).replace("{js}", JS))


def page(W, S31, S32):
    return render(items(W, S31, S32), TEST_ID, "第3回", "子音の聞き取りテスト", "流れた英単語はどちらか、2つから選びます。")
