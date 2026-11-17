/* 「発音テスト」（lectureNN/record.html）。core.js のあとに読み、ページの最後で SP.record(DATA) を呼ぶ。
 * 単純な流れ：学籍番号・氏名 → 1問ずつ「録音」→「止める」（話し終わると自動でも止まる）→ その場で自動送信して次の問題へ。
 * お手本は流さない。聞き直し・録り直しはしない。ただし声が録れていない・音が割れているときだけ、その問題をもう一度録れる（2回まで）。
 * 送信は裏で順番に行い、失敗したら自動でやり直す。最後の問題のあと、全部届いたのを確かめて「完了」を送る。
 * 送信先は聞き取りテストと同じ Apps Script（web/config.js の apiUrl、受付は web/gas/Code.gs の rec-upload / rec-finish）。
 */
(function () {
  'use strict';
  const { $, esc } = SP;
  const RETRY_BAD = 2;   // 録音に失敗したとき（声が無い・音割れ）にやり直せる回数

  SP.record = function (DATA) {
    const DEMO = !SP.api();
    const items = DATA.items;
    const st = { sid: '', name: '', idx: 0, takes: [], tries: [], state: [], submissionId: SP.newId(), startedAt: 0, finished: false };
    // state[k]：undefined＝未録音、'q'＝送信待ち、'up'＝送信中、'ok'＝送信済み、'ng'＝送信失敗（自動で再試行）
    const rec = new SP.Recorder();
    let tick = null, starting = false;

    function show(id) { ['s-start', 's-rec', 's-send', 's-done'].forEach((s) => { $(s).hidden = s !== id; }); window.scrollTo(0, 0); }

    // ---------- 開始 ----------
    const me = SP.store.get('lt-me') || {};
    $('sid').value = me.sid || ''; $('nm').value = me.nm || '';
    $('demo').hidden = !DEMO;
    const w = SP.inAppNotice();
    if (w) { $('inapp').innerHTML = w; $('inapp').hidden = false; }
    SP.recStatus().then((s) => {
      if (s === false) { $('go').disabled = true; $('err').textContent = 'いまは受け付けていません。'; }
      else if (s === undefined) { $('go').disabled = true; $('err').textContent = '受付の準備ができていません（先生に伝えてください）。'; }
    });

    $('go').addEventListener('click', async () => {
      const sid = SP.normId($('sid').value), nm = $('nm').value.trim();
      $('err').textContent = '';
      if (!sid || !nm) { $('err').textContent = '学籍番号と氏名を入力してください。'; return; }
      if (!/^[0-9A-Z-]{4,16}$/.test(sid)) { $('err').textContent = '学籍番号は半角の英数字で入力してください。'; return; }
      if (!SP.canRecord()) { $('err').innerHTML = 'このブラウザでは録音できません。<b>Safari（iPhone）か Chrome（Android）</b>で開き直してください。'; return; }
      SP.store.set('lt-me', { sid, nm });
      Object.assign(st, { sid, name: nm, idx: 0 });
      // マイクの許可をここで先にもらう（すぐ閉じる）
      $('go').disabled = true;
      rec.prime();
      try { await rec.start(); rec.stop(); }
      catch (e) { $('err').innerHTML = SP.MIC_HELP; $('go').disabled = false; return; }
      $('go').disabled = false;
      st.startedAt = Date.now();
      $('who').textContent = nm;
      show('s-rec'); render();
    });

    // ---------- 録音画面 ----------
    function render() {
      const i = st.idx, it = items[i];
      $('r-count').textContent = '問 ' + (i + 1) + ' / ' + items.length;
      dots();
      $('r-ctx').textContent = it.ctx || ''; $('r-ctx').hidden = !it.ctx;
      $('r-text').textContent = it.text;
      $('r-note').textContent = it.note || ''; $('r-note').hidden = !it.note;
      setRecUI('idle');
      $('rec-timer').textContent = '最長 ' + SP.fmt(it.maxSec || 8);
      $('rec-meter').firstElementChild.style.width = '0%';
    }
    function dots() {
      $('r-dots').innerHTML = items.map((_, k) => {
        const s = st.state[k];
        return '<span class="dot' + (s === 'ok' ? ' done' : s ? ' sending' : '') + (s === 'ng' ? ' fail' : '') + (k === st.idx && !st.finished ? ' current' : '') + '"></span>';
      }).join('');
      const ok = st.state.filter((s) => s === 'ok').length, rec = st.state.filter(Boolean).length;
      $('up-state').textContent = rec ? '送信済み ' + ok + ' / 録音 ' + rec : '';
    }

    function setRecUI(s) {
      $('btn-rec').classList.toggle('on', s === 'rec');
      $('btn-rec').setAttribute('aria-label', s === 'rec' ? '録音を止める' : '録音を始める');
      $('rec-label').textContent = s === 'rec' ? '話し終わったらタップ（自動でも止まります）' : s === 'wait' ? '準備中…' : 'タップして録音';
      $('btn-rec').disabled = s === 'wait';
    }

    async function startRec() {
      if (starting || rec.recording) return;   // 連打で2つ目のマイクを開かない
      starting = true;
      const max = items[st.idx].maxSec || 8;
      $('r-msg').textContent = ''; $('r-msg').className = 'msg';
      setRecUI('wait');
      rec.onchunk = SP.endDetector(() => { if (rec.recording) stopRec(); }, 1.2);
      rec.onlive = () => {
        setRecUI('rec');
        tick = setInterval(() => {
          $('rec-timer').textContent = SP.fmt(rec.seconds) + ' / ' + SP.fmt(max);
          const v = Math.min(1, rec.level * 1.4);
          $('rec-meter').firstElementChild.style.width = (v * 100).toFixed(0) + '%';
          $('rec-meter').classList.toggle('hot', rec.level >= 0.98);
          if (rec.seconds >= max) stopRec();
        }, 100);
      };
      try { await rec.start(); }
      catch (e) { setRecUI('idle'); $('r-msg').innerHTML = SP.MIC_HELP; }
      finally { starting = false; }
    }

    function stopRec() {
      if (!rec.recording) return;
      clearInterval(tick); tick = null;
      const x = rec.stop(), rate = rec.rate, i = st.idx;
      const [a, b] = SP.trim(x, rate);
      const q = SP.assess(Math.max(0, (b - a) / rate - 0.24), SP.peak(x));
      st.tries[i] = (st.tries[i] || 0) + 1;
      // 録音そのものの失敗（声が無い・音割れ・小さすぎ）は、その場でもう一度録らせる
      if (q.level === 'warn' && st.tries[i] <= RETRY_BAD) {
        setRecUI('idle');
        $('r-msg').className = 'msg warn';
        $('r-msg').textContent = q.text + '（この問題をもう一度録音してください）';
        return;
      }
      st.takes[i] = { blob: SP.encodeWav(x, rate), dur: x.length / rate, peak: SP.peak(x), rate, tries: st.tries[i] };
      st.state[i] = 'q';
      pump();
      if (i < items.length - 1) {
        st.idx = i + 1; render();
        $('r-msg').className = 'msg ok'; $('r-msg').textContent = '問 ' + (i + 1) + ' を送信しています。次の問題です。';
      } else { st.finished = true; finish(); }
    }

    $('btn-rec').addEventListener('click', () => {
      if (rec.recording) { stopRec(); return; }
      rec.prime();
      startRec();
    });

    // ---------- 送信（裏で1問ずつ） ----------
    let pumping = false;
    async function pump() {
      if (pumping) return;
      pumping = true;
      try {
        for (;;) {
          const k = st.state.findIndex((s) => s === 'q' || s === 'ng');
          if (k < 0) break;
          st.state[k] = 'up'; dots();
          const t = st.takes[k], it = items[k];
          try {
            if (DEMO) await new Promise((r) => setTimeout(r, 300));
            else await SP.post({
              action: 'rec-upload', testId: DATA.testId, testTitle: DATA.title, submissionId: st.submissionId, studentId: st.sid, name: st.name,
              startedAt: st.startedAt, itemNo: k + 1, itemText: it.text, ctx: it.ctx || '', area: it.area || '', check: it.check || '',
              durationSec: +t.dur.toFixed(3), sampleRate: t.rate, peak: +t.peak.toFixed(4), takes: t.tries, data: await SP.toBase64(t.blob),
            });
            st.state[k] = 'ok';
          } catch (e) {
            st.state[k] = 'ng'; dots();
            if (e.server && e.message !== 'missing') { fatal(e.message); return; }
            await new Promise((r) => setTimeout(r, 4000));   // 電波が戻るのを待って自動でやり直す
          }
          dots();
        }
      } finally { pumping = false; }
      if (st.finished) finish();
    }

    // ---------- 完了 ----------
    let finishing = false;
    async function finish() {
      show('s-send');
      const ok = st.state.filter((s) => s === 'ok').length;
      $('send-bar').style.width = (ok / (items.length + 1) * 100) + '%';
      $('send-label').textContent = '送信中 ' + ok + ' / ' + items.length + '（このままお待ちください）';
      if (ok < items.length) { pump(); return; }
      if (finishing) return;
      finishing = true;
      try {
        const j = DEMO ? { receipt: 'DEMO', attempt: 1, received: items.length, receivedAt: new Date().toLocaleString('ja-JP') }
          : await SP.post({ action: 'rec-finish', testId: DATA.testId, testTitle: DATA.title, submissionId: st.submissionId, studentId: st.sid,
            name: st.name, startedAt: st.startedAt, count: items.length, finishedAt: Date.now(), ua: navigator.userAgent });
        $('d-receipt').textContent = j.receipt;
        $('d-name').textContent = st.name + '（' + st.sid + '）';
        $('d-count').textContent = j.received + ' / ' + items.length + ' 問';
        $('d-time').textContent = j.receivedAt;
        $('d-attempt').textContent = j.attempt + ' 回目の提出';
        $('d-demo').hidden = !DEMO;
        st.done = true;
        show('s-done');
      } catch (e) {
        finishing = false;
        if (e.server && e.message !== 'missing') { fatal(e.message); return; }
        $('send-label').textContent = '受付の確認ができませんでした。電波のよい場所で「もう一度送信する」を押してください。';
        $('resend').hidden = false;
      }
    }
    $('resend').addEventListener('click', () => { $('resend').hidden = true; st.state = st.state.map((s) => (s === 'ok' ? 'ok' : 'q')); finish(); });
    function fatal(code) {
      show('s-send');
      $('send-label').textContent = SP.SERVER_ERRORS[code] || ('受付側でエラーが起きました（' + code + '）。先生に伝えてください。');
    }
    $('again').addEventListener('click', () => { location.reload(); });

    window.addEventListener('beforeunload', (e) => {
      if (st.state.some(Boolean) && !st.done) { e.preventDefault(); e.returnValue = ''; }
    });
  };
})();
