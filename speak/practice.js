/* 「話して練習」（lectureNN/speak.html）。core.js のあとに読み、ページの最後で SP.practice(DATA) を呼ぶ。
 * 1項目ずつ：「お手本のあとに言う」＝お手本が流れ、終わると自動で録音が始まり、言い終わると自動で止まって自分の声が流れる。
 *   何回でも録り直せる。「比べる」でお手本→自分を続けて聞き、声紋／高さ・強さを同じ時間目盛りで見る。自己評価（0・1・2）。
 * 課題（DATA.task）：「課題」の印の項目は、納得した録音で「この録音に決定」を押し、全部決定したら一覧の上の「提出する」で送る。
 *   決定した録音はこの端末（IndexedDB）に残り、ページを閉じても提出まで消えない。決定していない録音は送らない・残さない。
 *   送信先は聞き取りテストと同じ Apps Script（rec-upload / rec-finish）。testId は DATA.task.testId。
 */
(function () {
  'use strict';
  const { $, esc } = SP;

  SP.practice = async function (DATA) {
    const items = [];
    DATA.sections.forEach((s, si) => s.items.forEach((it) => items.push(Object.assign({ si, view: s.view || DATA.view }, it))));
    const TASK = DATA.task || null;
    const ANALYSIS = !!DATA.analysis;   // 音声分析つきの版（analyze.html）か、図を出さない版（speak.html）か
    const taskItems = items.filter((it) => it.task);
    const KEY = 'sp-' + DATA.page;
    const DBKEY = 'decided-' + DATA.page;
    const SESSION = SP.newId();   // このページを開いている間の録音か、前に決定して保存した録音かを区別する
    const marks = SP.store.get(KEY) || {};
    const takes = {};          // 項目ID → 最新の録音 { t0, samples, rate, an, url, raw, n, q }
    const count = {};          // 項目ID → 録音した回数
    const models = {};         // 音声ファイル → Promise<{ t0, an }>
    let decided = {};          // 項目ID → { blob, dur, peak, rate, takes, n, session, at, warn }
    const decUrl = {};
    const rec = new SP.Recorder();
    let idx = -1, view = DATA.view, recBusy = false, tick = null, sending = false, repeatPending = false;

    // ---------- 一覧 ----------
    function renderList() {
      const box = $('list');
      box.innerHTML = '';
      DATA.sections.forEach((s, si) => {
        const sec = document.createElement('section');
        sec.innerHTML = '<h2><span class="no">' + (si + 1) + '</span>' + esc(s.title) + '</h2>' +
          (s.lead ? '<p class="lead">' + s.lead + '</p>' : '') + '<div class="card"><ul class="items"></ul></div>';
        const ul = sec.querySelector('.items');
        items.forEach((it, k) => {
          if (it.si !== si) return;
          const li = document.createElement('li');
          const m = marks[it.id];
          li.innerHTML = '<button type="button" data-open="' + k + '"><span class="t">' + it.html + '</span>' +
            '<span class="stat">' + (it.model ? '<i class="m" title="お手本あり">♪</i>' : '') +
            (it.task && TASK ? (decided[it.id] ? '<i class="dec">✓決定</i>' : '<i class="tk">課題</i>') : '') +
            (m !== undefined ? '<i class="k k' + m + '">' + m + '</i>' : '') + '</span></button>';
          ul.appendChild(li);
        });
        box.appendChild(sec);
      });
      const n = [0, 1, 2].map((v) => Object.values(marks).filter((x) => x === v).length);
      $('summary').innerHTML = '自己評価：<b class="k2">2</b> ' + n[2] + '　<b class="k1">1</b> ' + n[1] + '　<b class="k0">0</b> ' + n[0] +
        '　（全 ' + items.length + ' 項目）';
      renderTask();
    }
    $('list').addEventListener('click', (e) => { const b = e.target.closest('[data-open]'); if (b) open(Number(b.dataset.open)); });

    // ---------- 1項目の画面 ----------
    const pModel = new Audio(), pSelf = new Audio(), pDec = new Audio();
    let playing = null, chain = false;
    [pModel, pSelf, pDec].forEach((a) => {
      a.preload = 'auto';
      a.addEventListener('ended', () => {
        if (repeatPending && a === pModel) { repeatPending = false; playing = null; uiPlay(); startRec(true); return; }
        if (chain && a === pModel && takes[items[idx].id]) { chain = false; setTimeout(() => play(pSelf), 300); return; }
        chain = false; playing = null; uiPlay();
      });
    });

    function stopAudio() { chain = false; repeatPending = false; [pModel, pSelf, pDec].forEach((a) => a.pause()); playing = null; uiPlay(); }
    function play(a) {
      [pModel, pSelf, pDec].forEach((b) => { if (b !== a) b.pause(); });
      a.currentTime = 0;
      playing = a;
      a.play().catch(() => { playing = null; uiPlay(); });
      uiPlay(); animate();
    }
    function uiPlay() {
      $('b-model').classList.toggle('on', playing === pModel);
      $('b-self').classList.toggle('on', playing === pSelf);
      $('b-dplay').classList.toggle('on', playing === pDec);
      if (playing !== pModel) $('ph-model').hidden = true;
      if (playing !== pSelf) $('ph-self').hidden = true;
    }
    // 再生位置の縦線
    function animate() {
      if (!ANALYSIS || !playing || playing === pDec) return;
      const total = scale(), isModel = playing === pModel;
      const t = playing.currentTime - (isModel ? (modelInfo && modelInfo.t0) || 0 : 0);
      const ph = $(isModel ? 'ph-model' : 'ph-self');
      if (t >= 0 && total) { ph.hidden = false; ph.style.left = Math.min(100, t / total * 100) + '%'; }
      requestAnimationFrame(animate);
    }

    let modelInfo = null;
    function scale() {
      const it = items[idx], tk = takes[it.id];
      return Math.max(0.6, modelInfo ? modelInfo.an.dur : 0, tk ? tk.an.dur : 0);
    }

    function open(k) {
      stopAudio();
      if (recBusy) return;
      idx = k;
      const it = items[k], s = DATA.sections[it.si];
      $('list-view').hidden = true; $('item-view').hidden = false;
      window.scrollTo(0, 0);
      $('i-sec').textContent = (it.si + 1) + '. ' + s.title + (it.task && TASK ? '　（課題）' : '');
      $('i-count').textContent = (k + 1) + ' / ' + items.length;
      $('i-ctx').innerHTML = it.ctx ? esc(it.ctx) : '';
      $('i-ctx').hidden = !it.ctx;
      $('i-text').innerHTML = it.html;
      $('i-note').innerHTML = it.note ? esc(it.note) : '';
      $('i-note').hidden = !it.note;
      $('i-check').innerHTML = '<b>ここを意識</b>' + esc(it.check || '');
      $('i-check').hidden = !it.check;
      $('b-model').disabled = !it.model;
      $('b-model').querySelector('span').textContent = it.model ? 'お手本' : 'お手本なし';
      if (ANALYSIS) $('row-model').hidden = !it.model;
      $('i-prev').disabled = k === 0;
      $('i-next').disabled = k === items.length - 1;
      $('rec-msg').textContent = ''; $('rec-msg').className = 'msg';
      $('b-rec').querySelector('span').textContent = takes[it.id] ? '録り直す' : '録音';
      $('b-repeat').hidden = !it.model;
      $('b-repeat').querySelector('span').textContent = takes[it.id] ? 'もう一度：お手本のあとに言う' : 'お手本のあとに言う（自動で録音）';
      view = it.view || DATA.view;
      modelInfo = null;
      if (it.model) pModel.src = it.model; else pModel.removeAttribute('src');
      if (it.model && ANALYSIS) {
        $('d-model').textContent = '読み込み中…';
        if (!models[it.model]) {
          models[it.model] = SP.decodeUrl(it.model).then(([x, rate]) => { const p = SP.prepare(x, rate); return { t0: p.t0, an: p.an }; });
          models[it.model].catch(() => { delete models[it.model]; });
        }
        models[it.model].then((m) => { if (items[idx] === it) { modelInfo = m; draw(); } })
          .catch(() => { if (items[idx] === it) $('d-model').textContent = 'お手本の分析ができませんでした（再生はできます）'; });
      }
      const tk = takes[it.id];
      if (tk) pSelf.src = tk.url; else pSelf.removeAttribute('src');
      renderRate(); renderDecide(); draw();
    }

    const LEGEND = {
      wave: '波形（オシログラム）：横が時間、縦が空気の圧力の変化。母音や有声音は細かい振動がくり返し、無声の摩擦音は小さくざらざら、破裂音は一瞬の立ち上がり。上下で同じ時間の目盛り（下の線は 0.1 秒ごと）。',
    };
    function draw() {
      const it = items[idx], tk = takes[it.id], total = scale();
      $('b-self').disabled = !tk;
      $('b-both').disabled = !(tk && it.model);
      if (!ANALYSIS) { $('d-self2').textContent = tk ? tk.n + '回目の録音　' + tk.an.dur.toFixed(1) + ' 秒' : 'まだ録音していません'; return; }
      document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.view === view));
      const fn = view === 'pitch' ? SP.drawPitch : view === 'wave' ? SP.drawOsc : SP.drawSpec;
      $('legend').textContent = view === 'wave' ? LEGEND.wave : view === 'pitch'
        ? '線＝声の高さ（その人のふだんの高さを点線にそろえて表示）、灰色の山＝声の強さ。横は時間（上下で同じ目盛り）。強い音節は、高さの動き・強さ・長さの組み合わせで目立ちます（高さのいちばん上が強勢の位置とは限らない）。'
        : '声紋：横が時間、縦が音の高さ（周波数 0〜8,000 Hz）。濃いほど強い。母音は横じま、摩擦音は上の方のざらざら。上下で同じ時間の目盛り。';
      if (modelInfo) { fn($('c-model'), modelInfo.an, total); $('d-model').textContent = modelInfo.an.dur.toFixed(2) + ' 秒'; }
      const cs = $('c-self');
      if (tk) { fn(cs, tk.an, total); $('d-self').textContent = tk.n + '回目の録音　' + tk.an.dur.toFixed(2) + ' 秒'; cs.classList.remove('empty'); }
      else {
        const g = cs.getContext('2d'); cs.width = cs.clientWidth; cs.height = cs.clientHeight; g.clearRect(0, 0, cs.width, cs.height);
        $('d-self').textContent = 'まだ録音していません'; cs.classList.add('empty');
      }
    }

    function renderRate() {
      const m = marks[items[idx].id];
      document.querySelectorAll('#rate button').forEach((b) => b.classList.toggle('on', Number(b.dataset.v) === m));
    }

    // ---------- 課題：決定 ----------
    function renderDecide() {
      const it = items[idx];
      $('decide').hidden = !(TASK && it.task);
      if (!TASK || !it.task) return;
      const tk = takes[it.id], d = decided[it.id];
      const same = !!(tk && d && d.session === SESSION && d.n === tk.n);
      $('dec-state').innerHTML = d
        ? '<b class="ok">✓ 決定済み</b>　' + (d.session === SESSION ? d.n + '回目の録音' : '前に決定した録音') + '・' + d.dur.toFixed(1) + ' 秒' +
          (d.warn ? '　<span class="warn">（' + esc(d.warn) + '）</span>' : '')
        : 'まだ決定していません。何回でも録り直し、お手本と比べて納得したら決定します。';
      $('b-decide').disabled = !tk || same || recBusy || sending;
      $('b-decide').textContent = !tk ? '録音すると決定できます' : same ? 'この録音に決定済み' : d ? '今の録音に決定し直す' : 'この録音に決定';
      $('b-dplay').hidden = !d;
      if (d) {
        if (!decUrl[it.id]) decUrl[it.id] = URL.createObjectURL(d.blob);
        if (pDec.src !== decUrl[it.id]) pDec.src = decUrl[it.id];
      }
      const rest = taskItems.filter((x) => !decided[x.id]).length;
      $('dec-rest').textContent = rest ? '課題の未決定：あと ' + rest + ' 項目' : '課題はすべて決定しました。一覧の上の「提出する」から送れます。';
      $('b-dnext').textContent = rest ? '次の未決定の課題へ →' : '一覧（提出）へ';
    }

    async function decide() {
      const it = items[idx], tk = takes[it.id];
      if (!tk) return;
      stopAudio();
      decided[it.id] = { blob: SP.encodeWav(tk.raw, tk.rate), dur: tk.raw.length / tk.rate, peak: SP.peak(tk.raw), rate: tk.rate,
        takes: count[it.id], n: tk.n, session: SESSION, at: Date.now(), warn: tk.q.level === 'warn' ? '要確認の録音' : '' };
      if (decUrl[it.id]) { URL.revokeObjectURL(decUrl[it.id]); delete decUrl[it.id]; }
      await SP.db.put(DBKEY, decided);
      const rest = taskItems.filter((x) => !decided[x.id]).length;
      msg(rest ? '決定しました（あと ' + rest + ' 項目）。録り直して決定し直すこともできます。' : '課題をすべて決定しました。一覧にもどって提出してください。', 'ok');
      renderDecide();
    }
    $('b-decide').addEventListener('click', decide);
    $('b-dplay').addEventListener('click', () => { if (playing === pDec) stopAudio(); else play(pDec); });
    $('b-dnext').addEventListener('click', () => {
      const k = items.findIndex((x, i) => x.task && !decided[x.id] && i > idx);
      const j = k >= 0 ? k : items.findIndex((x) => x.task && !decided[x.id]);
      if (j >= 0) open(j); else { back(); $('task').scrollIntoView({ block: 'start' }); }
    });

    // ---------- 課題：提出 ----------
    function renderTask() {
      if (!TASK) { $('task').hidden = true; return; }
      $('task').hidden = false;
      const n = taskItems.filter((x) => decided[x.id]).length, N = taskItems.length;
      $('t-prog').innerHTML = '決定 <b>' + n + '</b> / ' + N + ' 項目';
      $('t-bar').style.width = (n / N * 100) + '%';
      const sent = SP.store.get('sp-sent-' + DATA.page);
      $('t-sent').hidden = !sent;
      if (sent) $('t-sent').innerHTML = '<b class="ok">✓ 提出済み</b>　受付番号 <b>' + esc(sent.receipt) + '</b>（' + esc(sent.at) + '・' + sent.attempt + '回目）。' +
        '決定し直して提出すると、新しい提出として受け付けます（採点は最後の提出）。';
      $('t-send').disabled = sending || n < N || $('t-send').dataset.closed === '1';
      $('t-send').textContent = sending ? '送信中…' : n < N ? 'あと ' + (N - n) + ' 項目を決定すると提出できます' : '提出する';
      $('t-next').hidden = n >= N;
    }
    $('t-next').addEventListener('click', () => { const j = items.findIndex((x) => x.task && !decided[x.id]); if (j >= 0) open(j); });

    let pending = null;   // 途中で切れた提出（同じ受付番号の続きとして、未送信分だけ送る）
    async function submit() {
      const sid = SP.normId($('sid').value), nm = $('nm').value.trim();
      $('t-err').textContent = '';
      if (!sid || !nm) { $('t-err').textContent = '学籍番号と氏名を入力してください。'; return; }
      if (!/^[0-9A-Z-]{4,16}$/.test(sid)) { $('t-err').textContent = '学籍番号は半角の英数字で入力してください。'; return; }
      SP.store.set('lt-me', { sid, nm });
      sending = true; renderTask();
      const N = taskItems.length, DEMO = !SP.api();
      if (!pending || pending.sid !== sid || pending.nm !== nm) pending = { sid, nm, id: SP.newId(), sent: new Set() };
      const base = { testId: TASK.testId, testTitle: TASK.title, submissionId: pending.id, studentId: sid, name: nm,
        startedAt: Math.min(...taskItems.map((x) => decided[x.id].at)) };
      const prog = (k, label) => { $('t-progress').hidden = false; $('t-sbar').style.width = (k / (N + 1) * 100) + '%'; $('t-label').textContent = label; };
      try {
        for (let k = 0; k < N; k++) {
          const it = taskItems[k], d = decided[it.id], tag = it.id + ':' + d.at;
          prog(k, '送信中 ' + (k + 1) + ' / ' + N);
          if (pending.sent.has(tag)) continue;
          if (DEMO) await new Promise((r) => setTimeout(r, 200));
          else await SP.post(Object.assign({}, base, {
            action: 'rec-upload', itemNo: k + 1, itemText: it.text, ctx: it.ctx || '', area: it.area || '', check: it.check || '',
            durationSec: +d.dur.toFixed(3), sampleRate: d.rate, peak: +d.peak.toFixed(4), takes: d.takes || 1, data: await SP.toBase64(d.blob),
          }));
          pending.sent.add(tag);
        }
        prog(N, '受付を確認しています…');
        const j = DEMO ? { receipt: 'DEMO', attempt: 1, receivedAt: new Date().toLocaleString('ja-JP') }
          : await SP.post(Object.assign({}, base, { action: 'rec-finish', count: N, finishedAt: Date.now(), ua: navigator.userAgent }));
        prog(N + 1, DEMO ? 'お試し表示のため、実際には送信していません。' : '提出しました。この画面をスクリーンショットで保存しておくと安心です。');
        SP.store.set('sp-sent-' + DATA.page, { receipt: j.receipt, at: j.receivedAt, attempt: j.attempt });
        pending = null;
      } catch (e) {
        $('t-err').textContent = (e.server && SP.SERVER_ERRORS[e.message]) ||
          '送信できませんでした。電波のよい場所で、もう一度「提出する」を押してください（送れた項目は送り直しません）。';
      } finally {
        sending = false; renderTask();
      }
    }
    $('t-send').addEventListener('click', submit);

    // ---------- 録音 ----------
    function recUI(state) {
      const b = $('b-rec');
      b.classList.toggle('on', state === 'rec');
      b.classList.toggle('wait', state === 'wait');
      b.querySelector('span').textContent = state === 'rec' ? '止める' : state === 'wait' ? '準備中…' : (takes[items[idx].id] ? '録り直す' : '録音');
      const r = $('b-repeat');
      r.classList.toggle('on', state === 'rec' || state === 'model');
      if (state === 'model') r.querySelector('span').textContent = 'お手本を聞いて…（終わったら言う）';
      if (state === 'wait') r.querySelector('span').textContent = '準備中…';
      if (state === 'rec') r.querySelector('span').textContent = 'どうぞ（言い終わると自動で止まる）';
      ['b-model', 'b-self', 'b-both', 'i-prev', 'i-next', 'i-back', 'b-decide', 'b-dnext', 'b-dplay'].forEach((id) => { if (state !== 'idle') $(id).disabled = true; });
      if (state === 'idle') { ['b-dnext', 'b-dplay', 'i-back'].forEach((id) => { $(id).disabled = false; }); open(idx); }
    }

    async function startRec(auto) {
      if (recBusy || rec.recording) return;   // 連打で2つ目のマイクを開かない
      stopAudio();
      rec.onchunk = auto ? SP.endDetector(() => { if (rec.recording) stopRec(); }, 0.9) : null;
      if (!SP.canRecord()) { msg('このブラウザでは録音できません。Safari（iPhone）か Chrome（Android）で開いてください。', 'warn'); return; }
      recBusy = true;
      recUI('wait');
      const max = items[idx].maxSec || 8;
      rec.onlive = () => {
        recUI('rec');
        $('rec-msg').className = 'msg live'; $('rec-msg').textContent = (auto ? '● どうぞ　' : '● 録音中　') + '0:00 / ' + SP.fmt(max);
        if (auto && navigator.vibrate) navigator.vibrate(40);
        tick = setInterval(() => {
          $('rec-msg').textContent = (auto ? '● どうぞ　' : '● 録音中　') + SP.fmt(rec.seconds) + ' / ' + SP.fmt(max);
          meter();
          if (rec.seconds >= max) stopRec();
        }, 100);
      };
      try { await rec.start(); }
      catch (e) { recBusy = false; recUI('idle'); msg(SP.MIC_HELP, 'warn', true); }
    }

    function stopRec() {
      if (!rec.recording) return;
      clearInterval(tick); tick = null;
      const x = rec.stop(), rate = rec.rate, it = items[idx];
      recBusy = false;
      $('meter').firstElementChild.style.width = '0%';
      const p = SP.prepare(x, rate);
      const voiced = Array.from(p.an.db).filter((v) => v > p.an.dbMax - 25).length * p.an.hop / p.an.fs;
      p.q = SP.assess(voiced, SP.peak(x));
      p.raw = x;
      count[it.id] = (count[it.id] || 0) + 1;
      p.n = count[it.id];
      const old = takes[it.id];
      if (old) URL.revokeObjectURL(old.url);
      p.url = URL.createObjectURL(SP.encodeWav(p.samples, rate));
      takes[it.id] = p;
      recUI('idle');
      msg(p.q.level === 'ok'
        ? '録音しました（' + p.n + '回目）。いま流れているのが自分の声です。「比べる」でお手本と続けて聞けます。' + (it.task && TASK ? '納得したら「この録音に決定」。' : '')
        : p.q.text, p.q.level);
      if (p.q.level === 'ok') setTimeout(() => { if (items[idx] === it && takes[it.id] === p) play(pSelf); }, 250);
    }

    function meter() {
      const v = Math.min(1, rec.level * 1.4);
      $('meter').firstElementChild.style.width = (v * 100).toFixed(0) + '%';
      $('meter').classList.toggle('hot', rec.level >= 0.98);
    }
    function msg(t, level, isHtml) {
      const m = $('rec-msg');
      m.className = 'msg ' + (level || '');
      if (isHtml) m.innerHTML = t; else m.textContent = t;
    }

    // ---------- 操作 ----------
    $('b-rec').addEventListener('click', () => {
      if (rec.recording) { stopRec(); return; }
      if (recBusy) return;
      rec.prime();         // iPhone：タップの中で音声処理を起こす
      startRec();
    });
    $('b-repeat').addEventListener('click', () => {
      if (rec.recording) { stopRec(); return; }
      if (recBusy) return;
      if (repeatPending) { stopAudio(); recUI('idle'); return; }   // お手本の途中でもう一度押したらやめる
      rec.prime();
      stopAudio();
      repeatPending = true;
      recUI('model');
      pModel.currentTime = 0;
      playing = pModel;
      pModel.play().then(() => { uiPlay(); animate(); })
        .catch(() => { repeatPending = false; playing = null; startRec(true); });   // 再生できなければすぐ録音
    });
    $('b-model').addEventListener('click', () => { if (playing === pModel) stopAudio(); else play(pModel); });
    $('b-self').addEventListener('click', () => { if (playing === pSelf) stopAudio(); else play(pSelf); });
    $('b-both').addEventListener('click', () => { stopAudio(); chain = true; play(pModel); });
    if (ANALYSIS) $('tabs').addEventListener('click', (e) => { const b = e.target.closest('[data-view]'); if (b) { view = b.dataset.view; draw(); } });
    $('rate').addEventListener('click', (e) => {
      const b = e.target.closest('[data-v]'); if (!b) return;
      const id = items[idx].id, v = Number(b.dataset.v);
      if (marks[id] === v) delete marks[id]; else marks[id] = v;
      SP.store.set(KEY, marks); renderRate();
    });
    $('i-prev').addEventListener('click', () => { if (idx > 0) open(idx - 1); });
    $('i-next').addEventListener('click', () => { if (idx < items.length - 1) open(idx + 1); });
    $('i-back').addEventListener('click', back);
    function back() {
      stopAudio();
      $('item-view').hidden = true; $('list-view').hidden = false;
      renderList();
      const b = document.querySelector('[data-open="' + idx + '"]');
      if (b) b.scrollIntoView({ block: 'center' });
    }
    window.addEventListener('resize', () => { if (!$('item-view').hidden) draw(); });
    window.addEventListener('beforeunload', (e) => { if (sending) { e.preventDefault(); e.returnValue = ''; } });

    const w = SP.inAppNotice();
    if (w) { $('inapp').innerHTML = w; $('inapp').hidden = false; }
    if (TASK) {
      const me = SP.store.get('lt-me') || {};
      $('sid').value = me.sid || ''; $('nm').value = me.nm || '';
      decided = (await SP.db.get(DBKEY)) || {};
      Object.keys(decided).forEach((id) => { if (!taskItems.some((x) => x.id === id)) delete decided[id]; });   // 項目を差し替えたときの残り
      SP.recStatus().then((s) => {
        if (s === 'demo') $('t-demo').hidden = false;
        else if (s === false || s === undefined) {
          $('t-send').dataset.closed = '1';
          $('t-err').textContent = s === false ? 'いまは提出を受け付けていません。' : '提出の受付の準備ができていません（先生に伝えてください）。';
          renderTask();
        }
      });
    }
    renderList();
  };
})();
