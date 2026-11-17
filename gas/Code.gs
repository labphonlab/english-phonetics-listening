/**
 * 英語音声学「聞き取りテスト」の受付（Google Apps Script ウェブアプリ）
 *
 * テストページ（GitHub Pages）が解答をまとめて POST し、ここがスプレッドシートに書く。
 *   シート「結果」：1回の受験＝1行（学籍番号・氏名・何回目・得点など）
 *   シート「解答」：1問＝1行（どの語対で、何が流れ、何と答えたか）
 * 設置手順は web/gas/README.md。最初に一度だけ setup() を実行する。
 *
 * 2026-11 追加：発音テスト（lectureNN/record.html）の録音の受付。
 *   rec-upload：1問の録音（WAV）をドライブ「英語音声学_録音提出/<テスト>/<学籍番号>_<氏名>/」に保存し、シート「録音」に1行
 *   rec-finish：全問そろったか確かめて、シート「録音提出」に1行（回目・最新かどうか・得点の式）
 *   採点：メニュー「英語音声学」→「録音を採点する」のサイドバー（0・1・2、教科書 付録G.6 の尺度）
 *   受付の開け閉めは「設定」の B3（録音の受付）。聞き取りテスト（B1）とは別。
 */
const TZ = 'Asia/Tokyo';
const SHEET_RESULTS = '結果';
const SHEET_ITEMS = '解答';
const SHEET_SETTINGS = '設定';
const RESULTS_HEADER = ['受信日時', '受付番号', 'テスト', '学籍番号', '氏名', '回目', '得点', '問題数', '正答率',
  '開始', '終了', '所要（秒）', '間違えた語対', '端末'];
const ITEMS_HEADER = ['受付番号', 'テスト', '学籍番号', '氏名', '回目', '問', '節', '対立', '語A', '語B',
  '流れた語', '答え', '正誤', '再生回数', '解答までの秒'];

/** 最初に一度だけ実行：シートと見出しを作る */
function setup() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  [[SHEET_RESULTS, RESULTS_HEADER], [SHEET_ITEMS, ITEMS_HEADER]].forEach(([name, header]) => {
    const sh = ss.getSheetByName(name) || ss.insertSheet(name);
    sh.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
    sh.setFrozenRows(1);
    // 学籍番号の先頭の 0 が消えないよう文字列にする
    const col = header.indexOf('学籍番号') + 1;
    sh.getRange(2, col, sh.getMaxRows() - 1, 1).setNumberFormat('@');
  });
  const st = ss.getSheetByName(SHEET_SETTINGS) || ss.insertSheet(SHEET_SETTINGS);
  if (!st.getRange('A1').getValue()) {
    st.getRange('A1:B2').setValues([['受付', 'する'], ['説明', '「しない」にすると、テストページは送信を受け付けない（受験はできない表示になる）']]);
  }
  recSetup_(ss, st);
}

function accepting_() {
  const st = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_SETTINGS);
  return !st || String(st.getRange('B1').getValue()).trim() !== 'しない';
}

/** 受付状況の確認（テストページが開いたときに呼ぶ） */
function doGet(e) {
  return json_({ ok: true, accepting: accepting_(), recAccepting: recAccepting_() });
}

function doPost(e) {
  try {
    const p = JSON.parse(e.postData.contents);
    if (p.action === 'rec-upload' || p.action === 'rec-finish') return json_(recPost_(p));
    if (p.action !== 'submit' || !p.submissionId || !p.testId || !p.studentId || !p.name || !Array.isArray(p.items)) {
      return json_({ ok: false, error: 'bad_request' });
    }
    if (!accepting_()) return json_({ ok: false, error: 'closed' });
    return json_(submit_(p));
  } catch (err) {
    return json_({ ok: false, error: String(err) });
  }
}

function submit_(p) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const res = ss.getSheetByName(SHEET_RESULTS);
  const its = ss.getSheetByName(SHEET_ITEMS);
  const sid = String(p.submissionId).slice(0, 64);
  const studentId = normId_(p.studentId);
  const name = String(p.name).trim().slice(0, 60);
  const testId = String(p.testId).slice(0, 40);

  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    // 通信の再試行で同じ受験が2回届いたら、2回目は書かない
    const dup = res.createTextFinder(sid).matchEntireCell(true).findNext();
    if (dup) {
      const row = dup.getRow();
      return { ok: true, duplicate: true, attempt: res.getRange(row, 6).getValue(), score: res.getRange(row, 7).getValue() };
    }
    // 何回目か（同じテスト・同じ学籍番号の行を数える）
    let attempt = 1;
    const last = res.getLastRow();
    if (last > 1) {
      const vals = res.getRange(2, 3, last - 1, 2).getValues();
      attempt += vals.filter(v => String(v[0]) === testId && normId_(v[1]) === studentId).length;
    }
    // 得点はこちらで数え直す（流れた語と答えが同じなら正解）
    const items = p.items.slice(0, 200);
    const score = items.filter(it => it.answer && it.answer === it.target).length;
    const total = items.length;
    const wrong = items.filter(it => it.answer !== it.target).map(it => it.a + '–' + it.b + '（' + it.target + '→' + (it.answer || '未') + '）');
    const started = Number(p.startedAt) ? new Date(Number(p.startedAt)) : '';
    const finished = Number(p.finishedAt) ? new Date(Number(p.finishedAt)) : '';
    const secs = started && finished ? Math.round((finished - started) / 1000) : '';
    res.appendRow([new Date(), sid, testId, studentId, name, attempt, score, total, total ? score / total : '',
      started, finished, secs, wrong.join('、'), String(p.ua || '').slice(0, 200)]);
    res.getRange(res.getLastRow(), 9).setNumberFormat('0%');
    const rows = items.map((it, i) => [sid, testId, studentId, name, attempt, i + 1, String(it.sec || ''), String(it.contrast || ''),
      String(it.a || ''), String(it.b || ''), String(it.target || ''), String(it.answer || ''), it.answer === it.target ? 1 : 0,
      Number(it.plays) || '', it.ms ? Math.round(Number(it.ms) / 100) / 10 : '']);
    if (rows.length) its.getRange(its.getLastRow() + 1, 1, rows.length, ITEMS_HEADER.length).setValues(rows);
    return { ok: true, attempt: attempt, score: score, total: total };
  } finally {
    lock.releaseLock();
  }
}

// 全角の英数字を半角に、空白を除く
function normId_(s) {
  return String(s || '').replace(/[Ａ-Ｚａ-ｚ０-９]/g, c => String.fromCharCode(c.charCodeAt(0) - 0xFEE0)).replace(/\s+/g, '').toUpperCase();
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}

// =====================================================================
// 発音テストの録音（lectureNN/record.html）
// =====================================================================
const SHEET_REC_SUBS = '録音提出';
const SHEET_REC_ITEMS = '録音';
const REC_ROOT_NAME = '英語音声学_録音提出';
const REC_MAX_BYTES = 12 * 1024 * 1024;   // 1問の WAV の上限（48 kHz・16bit で約2分）
const REC_SUBS_HEADER = ['受信日時', '受付番号', 'テスト', '学籍番号', '氏名', '回目', '状態', '問題数', '受信数',
  '得点', '満点', '採点済み', '開始', '終了', 'フォルダ', '端末'];
const REC_ITEMS_HEADER = ['受信日時', '受付番号', 'テスト', '学籍番号', '氏名', '問', '提示文', '領域', '見る点',
  '秒数', '録音回数', 'Hz', 'ピーク', 'ファイル', 'ファイルID', '評価', 'メモ'];
const RI = {}; REC_ITEMS_HEADER.forEach((h, i) => { RI[h] = i + 1; });   // 列番号（1始まり）
const RS = {}; REC_SUBS_HEADER.forEach((h, i) => { RS[h] = i + 1; });

function recSetup_(ss, st) {
  [[SHEET_REC_SUBS, REC_SUBS_HEADER], [SHEET_REC_ITEMS, REC_ITEMS_HEADER]].forEach(([name, header]) => {
    const sh = ss.getSheetByName(name) || ss.insertSheet(name);
    sh.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');
    sh.setFrozenRows(1);
    const col = header.indexOf('学籍番号') + 1;
    sh.getRange(2, col, sh.getMaxRows() - 1, 1).setNumberFormat('@');
  });
  // 評価は 0・1・2 だけ選べるように
  const its = ss.getSheetByName(SHEET_REC_ITEMS);
  its.getRange(2, RI['評価'], its.getMaxRows() - 1, 1).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(['0', '1', '2'], true).setAllowInvalid(false).build());
  if (!st.getRange('A3').getValue()) {
    st.getRange('A3:B4').setValues([['録音の受付', 'する'], ['説明', '「しない」にすると、発音テスト（record.html）は録音を受け付けない']]);
  }
  recRoot_();   // ドライブの権限をここで確かめる
}

function recAccepting_() {
  const st = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_SETTINGS);
  if (!st || !SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_REC_ITEMS)) return undefined;   // まだ setup していない
  return String(st.getRange('B3').getValue()).trim() !== 'しない';
}

function recRoot_() {
  const it = DriveApp.getFoldersByName(REC_ROOT_NAME);
  return it.hasNext() ? it.next() : DriveApp.createFolder(REC_ROOT_NAME);
}
function childFolder_(parent, name, prefix) {
  const it = parent.getFolders();
  while (it.hasNext()) {
    const f = it.next();
    if (prefix ? f.getName().indexOf(prefix) === 0 : f.getName() === name) {
      if (f.getName() !== name) f.setName(name);   // 氏名などの書き方が変わったら名前だけ直す
      return f;
    }
  }
  return parent.createFolder(name);
}
function safeName_(s) { return String(s || '').replace(/[\\/:*?"<>|#%\u0000-\u001f]/g, '').replace(/\s+/g, '_').slice(0, 40); }

function recPost_(p) {
  const sid = String(p.submissionId || '');
  const testId = String(p.testId || '');
  const studentId = normId_(p.studentId);
  const name = String(p.name || '').trim().slice(0, 60);
  if (!/^[A-Za-z0-9-]{8,64}$/.test(sid) || !/^l\d\d-[a-z-]{2,30}$/.test(testId) || !/^[0-9A-Z-]{4,16}$/.test(studentId) || !name) {
    return { ok: false, error: 'bad_request' };
  }
  if (recAccepting_() !== true) return { ok: false, error: 'closed' };
  const base = { sid, testId, studentId, name, title: String(p.testTitle || testId).slice(0, 60) };
  return p.action === 'rec-upload' ? recUpload_(p, base) : recFinish_(p, base);
}

function recUpload_(p, b) {
  const no = Number(p.itemNo);
  if (!(no >= 1 && no <= 60) || typeof p.data !== 'string') return { ok: false, error: 'bad_request' };
  if (p.data.length * 0.75 > REC_MAX_BYTES) return { ok: false, error: 'too_large' };
  const bytes = Utilities.base64Decode(p.data);
  if (bytes.length < 44 || String.fromCharCode(bytes[0], bytes[1], bytes[2], bytes[3]) !== 'RIFF') return { ok: false, error: 'bad_request' };
  const text = String(p.itemText || '').slice(0, 200);
  const started = Number(p.startedAt) ? new Date(Number(p.startedAt)) : new Date();
  const stamp = Utilities.formatDate(started, TZ, 'yyyyMMdd-HHmm');
  const tf = childFolder_(recRoot_(), b.testId + '_' + safeName_(b.title), b.testId + '_');
  const sf = childFolder_(tf, b.studentId + '_' + safeName_(b.name), b.studentId + '_');
  const fname = [b.testId, b.studentId, ('0' + no).slice(-2), safeName_(text), stamp].join('_') + '.wav';
  const file = sf.createFile(Utilities.newBlob(bytes, 'audio/wav', fname));
  const row = [new Date(), b.sid, b.testId, b.studentId, b.name, no,
    (p.ctx ? String(p.ctx).slice(0, 200) + ' → ' : '') + text, String(p.area || '').slice(0, 40), String(p.check || '').slice(0, 300),
    Number(p.durationSec) || '', Number(p.takes) || '', Number(p.sampleRate) || '', Number(p.peak) || '',
    file.getUrl(), file.getId(), '', ''];
  const its = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_REC_ITEMS);
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    // 通信の再試行で同じ問題が2回届いたら、前のファイルを捨てて行を差し替える
    const hits = its.getRange(1, RI['受付番号'], its.getLastRow(), 1).createTextFinder(b.sid).matchEntireCell(true).findAll();
    for (const h of hits) {
      const r = h.getRow();
      if (Number(its.getRange(r, RI['問']).getValue()) === no) {
        try { DriveApp.getFileById(String(its.getRange(r, RI['ファイルID']).getValue())).setTrashed(true); } catch (e) { /* 既に無い */ }
        its.getRange(r, 1, 1, row.length).setValues([row]);
        return { ok: true, item: no, replaced: true };
      }
    }
    its.appendRow(row);
    return { ok: true, item: no };
  } finally {
    lock.releaseLock();
  }
}

function recFinish_(p, b) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const subs = ss.getSheetByName(SHEET_REC_SUBS), its = ss.getSheetByName(SHEET_REC_ITEMS);
  const count = Number(p.count) || 0;
  const lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    const dup = subs.getRange(1, RS['受付番号'], subs.getLastRow(), 1).createTextFinder(b.sid).matchEntireCell(true).findNext();
    if (dup) {
      const r = dup.getRow();
      return { ok: true, duplicate: true, receipt: receipt_(b.sid), attempt: subs.getRange(r, RS['回目']).getValue(),
        received: subs.getRange(r, RS['受信数']).getValue(), receivedAt: fmt_(subs.getRange(r, 1).getValue()) };
    }
    const items = its.getRange(1, RI['受付番号'], its.getLastRow(), 1).createTextFinder(b.sid).matchEntireCell(true).findAll()
      .map((h) => Number(its.getRange(h.getRow(), RI['問']).getValue()));
    const received = new Set(items).size;
    if (count < 1 || received < count) return { ok: false, error: 'missing', received: received };
    // 何回目か。同じテスト・同じ学籍番号の前の提出は「以前」にする（採点は「最新」だけ）
    let attempt = 1;
    const last = subs.getLastRow();
    if (last > 1) {
      const vals = subs.getRange(2, RS['テスト'], last - 1, RS['状態'] - RS['テスト'] + 1).getValues();
      vals.forEach((v, i) => {
        if (String(v[0]) === b.testId && normId_(v[1]) === b.studentId) {
          attempt++;
          if (v[RS['状態'] - RS['テスト']] === '最新') subs.getRange(i + 2, RS['状態']).setValue('以前');
        }
      });
    }
    const now = new Date();
    const started = Number(p.startedAt) ? new Date(Number(p.startedAt)) : '';
    const finished = Number(p.finishedAt) ? new Date(Number(p.finishedAt)) : '';
    const folder = childFolder_(childFolder_(recRoot_(), b.testId + '_' + safeName_(b.title), b.testId + '_'),
      b.studentId + '_' + safeName_(b.name), b.studentId + '_');
    subs.appendRow([now, b.sid, b.testId, b.studentId, b.name, attempt, '最新', count, received, '', count * 2, '',
      started, finished, folder.getUrl(), String(p.ua || '').slice(0, 200)]);
    const r = subs.getLastRow();
    const L = (h) => colLetter_(RI[h]);
    const rng = "'" + SHEET_REC_ITEMS + "'!";
    subs.getRange(r, RS['採点済み']).setFormula('=COUNTIFS(' + rng + L('受付番号') + ':' + L('受付番号') + ',B' + r + ',' + rng + L('評価') + ':' + L('評価') + ',"<>")');
    subs.getRange(r, RS['得点']).setFormula('=IF(' + colLetter_(RS['採点済み']) + r + '=0,"",SUMIFS(' + rng + L('評価') + ':' + L('評価') + ',' +
      rng + L('受付番号') + ':' + L('受付番号') + ',B' + r + '))');
    return { ok: true, receipt: receipt_(b.sid), attempt: attempt, received: received, receivedAt: fmt_(now) };
  } finally {
    lock.releaseLock();
  }
}

function receipt_(sid) { return 'R-' + sid.replace(/-/g, '').slice(-8).toUpperCase(); }
function fmt_(d) { return d instanceof Date ? Utilities.formatDate(d, TZ, 'yyyy/MM/dd HH:mm') : String(d); }
function colLetter_(n) { let s = ''; while (n > 0) { const m = (n - 1) % 26; s = String.fromCharCode(65 + m) + s; n = Math.floor((n - 1) / 26); } return s; }

// =====================================================================
// 採点サイドバー（スプレッドシートの持ち主だけが使う。ウェブアプリからは呼べない）
// =====================================================================
function onOpen() {
  SpreadsheetApp.getUi().createMenu('英語音声学').addItem('録音を採点する', 'openGrader').addSeparator().addItem('初期設定（setup）', 'setup').addToUi();
}

function openGrader() {
  SpreadsheetApp.getUi().showSidebar(HtmlService.createHtmlOutput(GRADER_HTML).setTitle('録音の採点'));
}

/** 採点できるテストの一覧 */
function graderTests() {
  const sh = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_REC_SUBS);
  if (!sh || sh.getLastRow() < 2) return [];
  return Array.from(new Set(sh.getRange(2, RS['テスト'], sh.getLastRow() - 1, 1).getValues().map((v) => String(v[0])))).sort();
}

/** 採点する録音の並び。各学生の「最新」の提出だけ。order：'item'（問題ごと）か 'student'（学生ごと） */
function graderQueue(testId, order, onlyUngraded) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const subs = ss.getSheetByName(SHEET_REC_SUBS), its = ss.getSheetByName(SHEET_REC_ITEMS);
  if (subs.getLastRow() < 2 || its.getLastRow() < 2) return [];
  const latest = new Set(subs.getRange(2, 1, subs.getLastRow() - 1, REC_SUBS_HEADER.length).getValues()
    .filter((v) => String(v[RS['テスト'] - 1]) === testId && v[RS['状態'] - 1] === '最新').map((v) => String(v[RS['受付番号'] - 1])));
  let q = its.getRange(2, 1, its.getLastRow() - 1, REC_ITEMS_HEADER.length).getValues()
    .filter((v) => latest.has(String(v[RI['受付番号'] - 1])))
    .map((v) => ({ fileId: String(v[RI['ファイルID'] - 1]), studentId: String(v[RI['学籍番号'] - 1]), name: String(v[RI['氏名'] - 1]),
      no: Number(v[RI['問'] - 1]), text: String(v[RI['提示文'] - 1]), check: String(v[RI['見る点'] - 1]), takes: v[RI['録音回数'] - 1],
      score: v[RI['評価'] - 1] === '' ? '' : String(v[RI['評価'] - 1]), memo: String(v[RI['メモ'] - 1] || '') }));
  if (onlyUngraded) q = q.filter((x) => x.score === '');
  q.sort((a, b) => order === 'student'
    ? (a.studentId < b.studentId ? -1 : a.studentId > b.studentId ? 1 : a.no - b.no)
    : (a.no - b.no || (a.studentId < b.studentId ? -1 : a.studentId > b.studentId ? 1 : 0)));
  return q;
}

/** 録音を data URL で返す（サイドバーの再生用） */
function graderAudio(fileId) {
  const blob = DriveApp.getFileById(fileId).getBlob();
  return 'data:audio/wav;base64,' + Utilities.base64Encode(blob.getBytes());
}

/** 評価（0・1・2 か空欄）とメモを書く */
function graderSet(fileId, score, memo) {
  const its = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_REC_ITEMS);
  const h = its.getRange(1, RI['ファイルID'], its.getLastRow(), 1).createTextFinder(fileId).matchEntireCell(true).findNext();
  if (!h) throw new Error('行が見つかりません');
  const s = String(score);
  if (['', '0', '1', '2'].indexOf(s) < 0) throw new Error('評価は 0・1・2');
  its.getRange(h.getRow(), RI['評価'], 1, 2).setValues([[s === '' ? '' : Number(s), String(memo || '').slice(0, 300)]]);
  return true;
}

const GRADER_HTML = `<!doctype html><html><head><base target="_top"><meta charset="utf-8">
<style>
body{font:14px/1.5 -apple-system,"Hiragino Sans","Noto Sans JP",Arial,sans-serif;margin:0;padding:12px;color:#1B2238}
select,input,button{font:inherit}select{width:100%;padding:4px}
.row{display:flex;gap:8px;align-items:center;margin:6px 0;flex-wrap:wrap}
.card{border:1px solid #E2DED5;border-radius:10px;padding:10px;margin:10px 0}
.who{font-weight:700}.sub{color:#5B6573;font-size:12px}
.text{font-size:18px;font-weight:700;margin:6px 0}
.check{background:#2B3A67;color:#fff;border-radius:8px;padding:6px 8px;font-size:13px}
audio{width:100%;margin:8px 0}
.sc{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.sc button{padding:8px 0;border-radius:8px;border:2px solid #E2DED5;background:#fff;cursor:pointer;line-height:1.2}
.sc button b{font-size:18px;display:block}.sc button span{font-size:11px;color:#5B6573}
.sc button.on{border-color:#1F8A7D;background:#E3F3EA}
.nav{display:flex;justify-content:space-between;margin-top:8px}
.nav button,#load{padding:6px 12px;border-radius:8px;border:1px solid #CCC;background:#F6F4EF;cursor:pointer}
#memo{width:100%;box-sizing:border-box;padding:4px;margin-top:6px}
#msg{color:#D6452B;font-size:12px;min-height:1em}
</style></head><body>
<div class="row"><select id="test"><option>読み込み中…</option></select></div>
<div class="row">
 <label><input type="radio" name="ord" value="item" checked> 問題ごと</label>
 <label><input type="radio" name="ord" value="student"> 学生ごと</label>
</div>
<div class="row"><label><input type="checkbox" id="ung" checked> 未採点だけ</label><label><input type="checkbox" id="anon" checked> 氏名を隠す</label></div>
<button id="load">読み込む</button>
<div id="box" hidden>
 <div class="card">
  <div class="row" style="justify-content:space-between"><span class="who" id="who"></span><span class="sub" id="pos"></span></div>
  <div class="text" id="text"></div>
  <div class="check" id="check"></div>
  <audio id="au" controls></audio>
  <div class="sub" id="takes"></div>
  <div class="sc" id="sc">
   <button data-v="0"><b>0</b><span>まだ難しい</span></button>
   <button data-v="1"><b>1</b><span>意識すればできる</span></button>
   <button data-v="2"><b>2</b><span>課題内で安定</span></button>
  </div>
  <input id="memo" placeholder="メモ（任意。Enter で保存）">
  <div class="nav"><button id="prev">← 前</button><button id="next">次 →</button></div>
 </div>
 <p class="sub">キー：0・1・2＝評価して次へ／R＝もう一度再生／←→＝移動</p>
</div>
<p id="msg"></p>
<script>
var Q=[],k=0,cache={};
function $(id){return document.getElementById(id)}
function err(e){$('msg').textContent=String(e&&e.message||e)}
google.script.run.withSuccessHandler(function(ts){
  $('test').innerHTML=ts.length?ts.map(function(t){return '<option>'+t+'</option>'}).join(''):'<option value="">まだ提出がありません</option>';
}).withFailureHandler(err).graderTests();
$('load').onclick=function(){
  var t=$('test').value;if(!t)return;$('msg').textContent='読み込み中…';
  var ord=document.querySelector('input[name=ord]:checked').value;
  google.script.run.withSuccessHandler(function(q){Q=q;k=0;$('msg').textContent=q.length?'':'該当する録音はありません';$('box').hidden=!q.length;if(q.length)show()})
    .withFailureHandler(err).graderQueue(t,ord,$('ung').checked);
};
function audio(id,cb){if(cache[id])return cb(cache[id]);google.script.run.withSuccessHandler(function(u){cache[id]=u;cb(u)}).withFailureHandler(err).graderAudio(id)}
function show(){
  var x=Q[k];$('pos').textContent=(k+1)+' / '+Q.length;
  $('who').textContent=$('anon').checked?('受験者 '+(k+1)):(x.studentId+' '+x.name);
  $('text').textContent=x.no+'. '+x.text;$('check').textContent='見る点：'+x.check;
  $('takes').textContent='録音回数 '+x.takes;$('memo').value=x.memo;
  [].forEach.call($('sc').children,function(b){b.classList.toggle('on',b.dataset.v===x.score)});
  $('au').removeAttribute('src');
  audio(x.fileId,function(u){if(Q[k]===x){$('au').src=u;$('au').play().catch(function(){})}});
  if(Q[k+1])audio(Q[k+1].fileId,function(){});
}
function save(v,adv){
  var x=Q[k];x.score=v;x.memo=$('memo').value;show();
  google.script.run.withFailureHandler(err).graderSet(x.fileId,v,x.memo);
  if(adv&&k<Q.length-1){k++;show()}
}
$('sc').onclick=function(e){var b=e.target.closest('button');if(b)save(b.dataset.v,true)};
$('prev').onclick=function(){if(k>0){k--;show()}};
$('next').onclick=function(){if(k<Q.length-1){k++;show()}};
$('memo').onkeydown=function(e){if(e.key==='Enter'){e.preventDefault();save(Q[k].score,false)}};
document.addEventListener('keydown',function(e){
  if(e.target.id==='memo'||$('box').hidden)return;
  if(e.key==='0'||e.key==='1'||e.key==='2')save(e.key,true);
  else if(e.key==='r'||e.key==='R'){$('au').currentTime=0;$('au').play()}
  else if(e.key==='ArrowRight')$('next').click();else if(e.key==='ArrowLeft')$('prev').click();
});
</script></body></html>`;
