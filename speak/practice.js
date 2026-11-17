/* 「話して練習」（lectureNN/speak.html）。core.js のあとに読み、ページの最後で SP.practice(DATA) を呼ぶ。
 * 1項目ずつ：お手本を聞く → 録音 → 自分の声を聞く → 聞き比べ → 声紋／高さ・強さを同じ時間目盛りで並べて見る → 自己評価（0・1・2）。
 * 録音は端末の中だけで使い、送信しない（ページを閉じると消える）。自己評価だけを端末に保存する。
 */
(function () {
  'use strict';
  const { $, esc } = SP;
  const RATING = ['まだ難しい', '意識すればできる', '安定してできる'];

  SP.practice = function (DATA) {
    const items = [];
    DATA.sections.forEach((s, si) => s.items.forEach((it) => items.push(Object.assign({ si, view: s.view || DATA.view }, it))));
    const KEY = 'sp-' + DATA.page;
    const marks = SP.store.get(KEY) || {};
    const takes = {};          // 項目ID → { t0, samples, rate, an, url }
    const models = {};         // 音声ファイル → Promise<{ t0, an }>
    const rec = new SP.Recorder();
    let idx = -1, view = DATA.view, recBusy = false, tick = null;

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
            (takes[it.id] ? '<i class="r">録音</i>' : '') +
            (m !== undefined ? '<i class="k k' + m + '">' + m + '</i>' : '') + '</span></button>';
          ul.appendChild(li);
        });
        box.appendChild(sec);
      });
      const n = [0, 1, 2].map((v) => Object.values(marks).filter((x) => x === v).length);
      $('summary').innerHTML = '自己評価：<b class="k2">2</b> ' + n[2] + '　<b class="k1">1</b> ' + n[1] + '　<b class="k0">0</b> ' + n[0] +
        '　（全 ' + items.length + ' 項目）';
    }
    $('list').addEventListener('click', (e) => { const b = e.target.closest('[data-open]'); if (b) open(Number(b.dataset.open)); });

    // ---------- 1項目の画面 ----------
    const pModel = new Audio(), pSelf = new Audio();
    let playing = null, chain = false;
    [pModel, pSelf].forEach((a) => {
      a.preload = 'auto';
      a.addEventListener('ended', () => {
        if (chain && a === pModel && takes[items[idx].id]) { chain = false; setTimeout(() => play(pSelf), 300); return; }
        chain = false; playing = null; uiPlay();
      });
    });

    function stopAudio() { chain = false; [pModel, pSelf].forEach((a) => { a.pause(); }); playing = null; uiPlay(); }
    function play(a) {
      [pModel, pSelf].forEach((b) => { if (b !== a) b.pause(); });
      a.currentTime = 0;
      playing = a;
      a.play().catch(() => { playing = null; uiPlay(); });
      uiPlay(); animate();
    }
    function uiPlay() {
      $('b-model').classList.toggle('on', playing === pModel);
      $('b-self').classList.toggle('on', playing === pSelf);
      if (!playing) { $('ph-model').hidden = true; $('ph-self').hidden = true; }
    }
    // 再生位置の縦線
    function animate() {
      if (!playing) return;
      const it = items[idx], total = scale();
      const isModel = playing === pModel;
      const t = playing.currentTime - (isModel ? (modelInfo && modelInfo.t0) || 0 : 0);
      const ph = $(isModel ? 'ph-model' : 'ph-self');
      $(isModel ? 'ph-self' : 'ph-model').hidden = true;
      if (t >= 0 && total) { ph.hidden = false; ph.style.left = Math.min(100, t / total * 100) + '%'; }
      if (it) requestAnimationFrame(animate);
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
      $('i-sec').textContent = (it.si + 1) + '. ' + s.title;
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
      $('row-model').hidden = !it.model;
      $('i-prev').disabled = k === 0;
      $('i-next').disabled = k === items.length - 1;
      $('rec-msg').textContent = ''; $('rec-msg').className = 'msg';
      view = it.view || DATA.view;
      modelInfo = null;
      if (it.model) {
        pModel.src = it.model;
        $('d-model').textContent = '読み込み中…';
        if (!models[it.model]) {
          models[it.model] = SP.decodeUrl(it.model).then(([x, rate]) => {
            const p = SP.prepare(x, rate);
            return { t0: p.t0, an: p.an };
          });
          models[it.model].catch(() => { delete models[it.model]; });
        }
        models[it.model].then((m) => { if (items[idx] === it) { modelInfo = m; draw(); } })
          .catch(() => { if (items[idx] === it) $('d-model').textContent = 'お手本の分析ができませんでした（再生はできます）'; });
      } else { pModel.removeAttribute('src'); }
      const tk = takes[it.id];
      if (tk) pSelf.src = tk.url; else pSelf.removeAttribute('src');
      renderRate();
      draw();
    }

    function draw() {
      const it = items[idx], tk = takes[it.id], total = scale();
      document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('on', b.dataset.view === view));
      const fn = view === 'pitch' ? SP.drawPitch : SP.drawSpec;
      $('legend').textContent = view === 'pitch'
        ? '線＝声の高さ（その人のふだんの高さを点線にそろえて表示）、灰色の山＝声の強さ。横は時間（上下で同じ目盛り）。強い音節は、高さの動き・強さ・長さの組み合わせで目立ちます（高さのいちばん上が強勢の位置とは限らない）。'
        : '声紋：横が時間、縦が音の高さ（周波数 0〜8,000 Hz）。濃いほど強い。母音は横じま、摩擦音は上の方のざらざら。上下で同じ時間の目盛り。';
      if (modelInfo) {
        fn($('c-model'), modelInfo.an, total);
        $('d-model').textContent = modelInfo.an.dur.toFixed(2) + ' 秒';
      }
      const cs = $('c-self');
      if (tk) { fn(cs, tk.an, total); $('d-self').textContent = tk.an.dur.toFixed(2) + ' 秒'; cs.classList.remove('empty'); }
      else {
        const g = cs.getContext('2d'); cs.width = cs.clientWidth; cs.height = cs.clientHeight; g.clearRect(0, 0, cs.width, cs.height);
        $('d-self').textContent = 'まだ録音していません'; cs.classList.add('empty');
      }
      $('b-self').disabled = !tk;
      $('b-both').disabled = !(tk && it.model);
    }

    function renderRate() {
      const m = marks[items[idx].id];
      document.querySelectorAll('#rate button').forEach((b) => b.classList.toggle('on', Number(b.dataset.v) === m));
    }

    // ---------- 録音 ----------
    function recUI(state) {
      const b = $('b-rec');
      b.classList.toggle('on', state === 'rec');
      b.classList.toggle('wait', state === 'wait');
      b.querySelector('span').textContent = state === 'rec' ? '止める' : state === 'wait' ? '準備中…' : (takes[items[idx].id] ? '録り直す' : '録音');
      ['b-model', 'b-self', 'b-both', 'i-prev', 'i-next', 'i-back'].forEach((id) => { if (state !== 'idle') $(id).disabled = true; });
      if (state === 'idle') open(idx);
    }

    async function startRec() {
      if (recBusy || rec.recording) return;   // 連打で2つ目のマイクを開かない
      stopAudio();
      if (!SP.canRecord()) { msg('このブラウザでは録音できません。Safari（iPhone）か Chrome（Android）で開いてください。', 'warn'); return; }
      recBusy = true;
      recUI('wait');
      const max = items[idx].maxSec || 8;
      rec.onlive = () => {
        recUI('rec');
        $('rec-msg').className = 'msg live'; $('rec-msg').textContent = '● 録音中　0:00 / ' + SP.fmt(max);
        tick = setInterval(() => {
          $('rec-msg').textContent = '● 録音中　' + SP.fmt(rec.seconds) + ' / ' + SP.fmt(max);
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
      const q = SP.assess(voiced, SP.peak(x));
      const old = takes[it.id];
      if (old) URL.revokeObjectURL(old.url);
      p.url = URL.createObjectURL(SP.encodeWav(p.samples, rate));
      takes[it.id] = p;
      recUI('idle');
      msg(q.level === 'ok' ? '録音しました。「自分」で聞く・「比べる」でお手本のあとに続けて聞けます。' : q.text, q.level);
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
    $('b-model').addEventListener('click', () => { if (playing === pModel) stopAudio(); else play(pModel); });
    $('b-self').addEventListener('click', () => { if (playing === pSelf) stopAudio(); else play(pSelf); });
    $('b-both').addEventListener('click', () => { stopAudio(); chain = true; play(pModel); });
    $('tabs').addEventListener('click', (e) => { const b = e.target.closest('[data-view]'); if (b) { view = b.dataset.view; draw(); } });
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

    const w = SP.inAppNotice();
    if (w) { $('inapp').innerHTML = w; $('inapp').hidden = false; }
    renderList();
  };
})();
