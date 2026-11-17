/* 「発音テスト」（lectureNN/record.html）。core.js のあとに読み、ページの最後で SP.record(DATA) を呼ぶ。
 * 学籍番号・氏名 → 1項目ずつ録音（お手本は流さない。録り直しは1項目 maxTakes 回まで）→ 一覧で聞き直し → 送信。
 * 送信先は聞き取りテストと同じ Apps Script（web/config.js の apiUrl、受付側は web/gas/Code.gs）。
 * 録音は1項目ずつ送り（WAV・16bit・モノラル・端末のサンプリング周波数のまま）、最後に「完了」を送る。
 * 途中で切れたら、送れていない項目だけ送り直す。同じ項目が2回届いても受付側で1つにまとめる。
 */
(function () {
  'use strict';
  const { $, esc } = SP;

  SP.record = function (DATA) {
    const API = ((window.LISTENING_TEST_CONFIG || {}).apiUrl || '').trim();
    const DEMO = !API;
    const MAX_TAKES = DATA.maxTakes || 3;
    const items = DATA.items;
    const st = { sid: '', name: '', idx: 0, takes: [], count: [], uploaded: new Set(), submissionId: '', startedAt: 0, submitted: false, back: false };
    const rec = new SP.Recorder();
    let tick = null;

    function show(id) {
      ['s-start', 's-rec', 's-review', 's-done'].forEach((s) => { $(s).hidden = s !== id; });
      window.scrollTo(0, 0);
    }

    // ---------- 開始 ----------
    const me = SP.store.get('lt-me') || {};
    $('sid').value = me.sid || ''; $('nm').value = me.nm || '';
    $('demo').hidden = !DEMO;
    const w = SP.inAppNotice();
    if (w) { $('inapp').innerHTML = w; $('inapp').hidden = false; }
    if (!DEMO) {
      fetch(API).then((r) => r.json()).then((j) => {
        if (j && j.recAccepting === false) { $('go').disabled = true; $('err').textContent = 'いまは受け付けていません。'; }
        else if (j && j.recAccepting === undefined) { $('go').disabled = true; $('err').textContent = '受付の準備ができていません（先生に伝えてください）。'; }
      }).catch(() => {});
    }

    $('go').addEventListener('click', async () => {
      const sid = SP.normId($('sid').value), nm = $('nm').value.trim();
      $('err').textContent = '';
      if (!sid || !nm) { $('err').textContent = '学籍番号と氏名を入力してください。'; return; }
      if (!/^[0-9A-Z-]{4,16}$/.test(sid)) { $('err').textContent = '学籍番号は半角の英数字で入力してください。'; return; }
      if (!SP.canRecord()) { $('err').innerHTML = 'このブラウザでは録音できません。<b>Safari（iPhone）か Chrome（Android）</b>で開き直してください。'; return; }
      SP.store.set('lt-me', { sid, nm });
      Object.assign(st, { sid, name: nm, idx: 0 });
      // マイクの許可をここで先にもらう（1回録って捨てる）
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
      const i = st.idx, it = items[i], tk = st.takes[i], n = st.count[i] || 0;
      $('r-count').textContent = '問 ' + (i + 1) + ' / ' + items.length;
      $('r-dots').innerHTML = items.map((_, k) => '<span class="dot' + (st.takes[k] ? ' done' : '') + (k === i ? ' current' : '') + '"></span>').join('');
      $('r-ctx').textContent = it.ctx || ''; $('r-ctx').hidden = !it.ctx;
      $('r-text').textContent = it.text;
      $('r-note').textContent = it.note || ''; $('r-note').hidden = !it.note;
      $('btn-prev').hidden = i === 0;
      $('btn-next').textContent = (st.back || i === items.length - 1) ? '確認へ進む' : '次へ';
      setRecUI('idle');
      $('rec-timer').textContent = '最長 ' + SP.fmt(it.maxSec || 8);
      $('rec-left').textContent = '録音は1問 ' + MAX_TAKES + ' 回まで（最後の録音を提出）';
      if (tk) {
        $('r-recorder').hidden = true; $('r-take').hidden = false;
        $('take-audio').src = tk.url;
        requestAnimationFrame(() => SP.drawWave($('take-wave'), tk.samples));
        $('take-chip').className = 'chip ' + tk.q.level; $('take-chip').textContent = tk.q.text;
        const left = MAX_TAKES - n;
        $('btn-retake').disabled = left <= 0;
        $('btn-retake').textContent = left > 0 ? '録り直す（あと ' + left + ' 回）' : '録り直しはここまで';
      } else {
        $('r-recorder').hidden = false; $('r-take').hidden = true;
      }
    }

    function setRecUI(s) {
      $('btn-rec').classList.toggle('on', s === 'rec');
      $('btn-rec').setAttribute('aria-label', s === 'rec' ? '録音を止める' : '録音を始める');
      $('rec-label').textContent = s === 'rec' ? 'タップして停止' : s === 'wait' ? '準備中…' : 'タップして録音';
      $('btn-prev').disabled = s !== 'idle';
      $('btn-rec').disabled = s === 'wait';
    }

    let starting = false;
    async function startRec() {
      if (starting || rec.recording) return;   // 連打で2つ目のマイクを開かない
      starting = true;
      const max = items[st.idx].maxSec || 8;
      $('take-audio').pause();
      $('r-take').hidden = true; $('r-recorder').hidden = false;
      setRecUI('wait');
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
      catch (e) { setRecUI('idle'); $('rec-label').innerHTML = SP.MIC_HELP; }
      finally { starting = false; }
    }

    function stopRec() {
      if (!rec.recording) return;
      clearInterval(tick); tick = null;
      const x = rec.stop(), rate = rec.rate, i = st.idx;
      $('rec-meter').firstElementChild.style.width = '0%';
      const [a, b] = SP.trim(x, rate);
      const q = SP.assess(Math.max(0, (b - a) / rate - 0.24), SP.peak(x));
      const old = st.takes[i];
      if (old) URL.revokeObjectURL(old.url);
      const blob = SP.encodeWav(x, rate);
      st.takes[i] = { samples: x, blob, url: URL.createObjectURL(blob), dur: x.length / rate, peak: SP.peak(x), rate, q };
      st.count[i] = (st.count[i] || 0) + 1;
      st.uploaded.delete(i);
      render();
    }

    $('btn-rec').addEventListener('click', () => {
      if (rec.recording) { stopRec(); return; }
      if ((st.count[st.idx] || 0) >= MAX_TAKES) return;
      rec.prime();
      startRec();
    });
    $('btn-retake').addEventListener('click', () => {
      if ((st.count[st.idx] || 0) >= MAX_TAKES) return;
      rec.prime();
      startRec();
    });
    $('btn-next').addEventListener('click', () => {
      $('take-audio').pause();
      const next = items.findIndex((_, k) => k > st.idx && !st.takes[k]);
      if (st.back || st.idx === items.length - 1 || next < 0) { st.back = false; show('s-review'); renderReview(); }
      else { st.idx += 1; render(); }
    });
    $('btn-prev').addEventListener('click', () => { $('take-audio').pause(); if (st.idx > 0) { st.idx -= 1; st.back = false; render(); } });

    // ---------- 確認画面 ----------
    const player = new Audio();
    let playingIdx = -1;
    player.addEventListener('ended', () => { playingIdx = -1; renderReview(); });
    function renderReview() {
      const ol = $('review-list');
      ol.innerHTML = '';
      items.forEach((it, k) => {
        const t = st.takes[k];
        const li = document.createElement('li');
        li.innerHTML = '<span class="no">' + (k + 1) + '</span><span class="t">' + esc(it.text) + '</span>' +
          '<button class="chip-btn' + (playingIdx === k ? ' playing' : '') + '" type="button" data-play="' + k + '"' + (t ? '' : ' disabled') + '>' +
          (playingIdx === k ? '停止' : '再生') + '</button>' +
          '<span class="sub"><span>' + (t ? t.dur.toFixed(1) + ' 秒' : '未録音') + '</span>' +
          (t && t.q.level === 'warn' ? '<span class="warn">要確認</span>' : '') +
          ((st.count[k] || 0) < MAX_TAKES ? '<button class="linkish" type="button" data-retake="' + k + '">' + (t ? '録り直す' : '録音する') + '</button>' : '<span>録り直しはここまで</span>') +
          '</span>';
        ol.appendChild(li);
      });
      const missing = items.filter((_, k) => !st.takes[k]).length;
      $('btn-send').disabled = missing > 0 || st.submitted;
      $('btn-send').textContent = missing > 0 ? 'あと ' + missing + ' 問の録音が必要です' : 'この内容で提出する';
    }
    $('review-list').addEventListener('click', (e) => {
      const p = e.target.closest('[data-play]'), r = e.target.closest('[data-retake]');
      if (p) {
        const k = Number(p.dataset.play);
        if (playingIdx === k) { player.pause(); playingIdx = -1; }
        else if (st.takes[k]) { player.src = st.takes[k].url; player.play().catch(() => {}); playingIdx = k; }
        renderReview();
      } else if (r) {
        player.pause(); playingIdx = -1;
        st.idx = Number(r.dataset.retake); st.back = true;
        show('s-rec'); render();
      }
    });

    // ---------- 送信 ----------
    function toBase64(blob) {
      return new Promise((resolve, reject) => {
        const fr = new FileReader();
        fr.onload = () => resolve(String(fr.result).split(',')[1]);
        fr.onerror = () => reject(fr.error);
        fr.readAsDataURL(blob);
      });
    }
    async function post(body) {
      let last;
      for (let n = 0; n < 3; n++) {
        try {
          const r = await fetch(API, { method: 'POST', body: JSON.stringify(body) });
          const j = await r.json();
          if (j.ok) return j;
          throw Object.assign(new Error(j.error || 'error'), { server: true });
        } catch (e) {
          last = e;
          if (e.server) break;   // 受付側が断ったものは繰り返さない
          await new Promise((r) => setTimeout(r, 1500 * (n + 1)));
        }
      }
      throw last;
    }
    const SERVER_ERRORS = {
      closed: 'いまは受け付けていません。先生に伝えてください。',
      too_large: '録音が大きすぎます。その問題を短く録り直してください。',
      bad_request: '送信内容に不足があります。ページを開き直してください。',
      missing: '一部の録音が届いていません。「もう一度送信する」を押してください。',
    };

    async function send() {
      const total = items.length;
      $('btn-send').disabled = true; $('send-error').hidden = true; $('send-progress').hidden = false;
      if (!st.submissionId) st.submissionId = (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2, 12));
      const base = { testId: DATA.testId, testTitle: DATA.title, submissionId: st.submissionId, studentId: st.sid, name: st.name, startedAt: st.startedAt };
      const prog = (n, label) => { $('send-bar').style.width = (n / (total + 1) * 100) + '%'; $('send-label').textContent = label; };
      try {
        for (let k = 0; k < total; k++) {
          prog(k, '送信中 ' + (k + 1) + ' / ' + total);
          if (st.uploaded.has(k)) continue;
          const t = st.takes[k], it = items[k];
          if (DEMO) await new Promise((r) => setTimeout(r, 300));
          else {
            await post(Object.assign({}, base, {
              action: 'rec-upload', itemNo: k + 1, itemText: it.text, ctx: it.ctx || '', area: it.area || '', check: it.check || '',
              durationSec: +t.dur.toFixed(3), sampleRate: t.rate, peak: +t.peak.toFixed(4), takes: st.count[k] || 1, data: await toBase64(t.blob),
            }));
          }
          st.uploaded.add(k);
        }
        prog(total, '受付を確認しています…');
        const j = DEMO
          ? { receipt: 'DEMO', attempt: 1, received: total, receivedAt: new Date().toLocaleString('ja-JP') }
          : await post(Object.assign({}, base, { action: 'rec-finish', count: total, finishedAt: Date.now(), ua: navigator.userAgent }));
        prog(total + 1, '完了');
        st.submitted = true;
        $('d-receipt').textContent = j.receipt;
        $('d-name').textContent = st.name + '（' + st.sid + '）';
        $('d-count').textContent = j.received + ' / ' + total + ' 問';
        $('d-time').textContent = j.receivedAt;
        $('d-attempt').textContent = j.attempt + ' 回目の提出';
        $('d-demo').hidden = !DEMO;
        show('s-done');
      } catch (e) {
        $('send-error').textContent = (e.server && SERVER_ERRORS[e.message]) ||
          '送信できませんでした。電波のよい場所で「もう一度送信する」を押してください。送信済みの問題は送り直しません。';
        $('send-error').hidden = false;
        $('btn-send').disabled = false; $('btn-send').textContent = 'もう一度送信する';
      }
    }
    $('btn-send').addEventListener('click', send);
    $('again').addEventListener('click', () => { location.reload(); });

    window.addEventListener('beforeunload', (e) => {
      if (st.takes.some(Boolean) && !st.submitted) { e.preventDefault(); e.returnValue = ''; }
    });
  };
})();
