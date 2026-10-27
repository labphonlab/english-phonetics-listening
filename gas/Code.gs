/**
 * 英語音声学「聞き取りテスト」の受付（Google Apps Script ウェブアプリ）
 *
 * テストページ（GitHub Pages）が解答をまとめて POST し、ここがスプレッドシートに書く。
 *   シート「結果」：1回の受験＝1行（学籍番号・氏名・何回目・得点など）
 *   シート「解答」：1問＝1行（どの語対で、何が流れ、何と答えたか）
 * 設置手順は web/gas/README.md。最初に一度だけ setup() を実行する。
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
}

function accepting_() {
  const st = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(SHEET_SETTINGS);
  return !st || String(st.getRange('B1').getValue()).trim() !== 'しない';
}

/** 受付状況の確認（テストページが開いたときに呼ぶ） */
function doGet(e) {
  return json_({ ok: true, accepting: accepting_() });
}

function doPost(e) {
  try {
    const p = JSON.parse(e.postData.contents);
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
