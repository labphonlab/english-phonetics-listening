/* 英語音声学「話して練習」（lectureNN/speak.html）と「発音テスト」（lectureNN/record.html）の共通部品。
 * 録音（加工しない 16bit WAV）、無音の切り落とし、16 kHz への変換、声紋（スペクトログラム）・声の高さ（F0）・強さの計算と描画。
 * 録音の部分は voice-submit（~/Projects/teaching/voice-submit）の仕組みを引き継いだ。
 * 練習ページの録音は端末の中だけで使い、どこにも送らない。
 */
(function () {
  'use strict';
  const SP = window.SP = {};
  SP.AR = 16000;                      // 分析用のサンプリング周波数（声紋は 0〜8,000 Hz を表示）
  SP.$ = (id) => document.getElementById(id);
  SP.store = {
    get(k) { try { return JSON.parse(localStorage.getItem(k)); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* 保存できない環境では無視 */ } },
  };
  SP.normId = (s) => String(s || '').replace(/[Ａ-Ｚａ-ｚ０-９]/g, (c) => String.fromCharCode(c.charCodeAt(0) - 0xFEE0))
    .replace(/\s+/g, '').toUpperCase();
  SP.esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  SP.fmt = (s) => { const t = Math.floor(s); return Math.floor(t / 60) + ':' + String(t % 60).padStart(2, '0'); };

  // ---------- アプリ内ブラウザ（LINE など）では録音できないことがある ----------
  SP.inAppNotice = function () {
    const ua = navigator.userAgent;
    if (/\bLine\//i.test(ua)) {
      const u = new URL(location.href);
      u.searchParams.set('openExternalBrowser', '1');
      return '<strong>LINEの中で開いています</strong>LINEの画面では録音できないことがあります。<a href="' + u.href + '">SafariやChromeで開き直す</a>';
    }
    if (/Instagram|FBAN|FBAV|MicroMessenger|Twitter/i.test(ua)) {
      return '<strong>アプリの中で開いています</strong>録音できない場合は、右上のメニューから「ブラウザで開く」を選んでください。';
    }
    return '';
  };
  SP.MIC_HELP = '<strong>マイクを使えませんでした</strong>' +
    'iPhone：アドレスバーの「ぁあ」→「Webサイトの設定」→「マイク」を「許可」にして、ページを読み込み直してください。<br>' +
    'Android：アドレスバー左のアイコン→「権限」→「マイク」を許可して、ページを読み込み直してください。';
  SP.canRecord = () => !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  SP.newId = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + '-' + Math.random().toString(36).slice(2, 12));
  SP.api = () => ((window.LISTENING_TEST_CONFIG || {}).apiUrl || '').trim();

  // ---------- 送信（聞き取りテストと同じ Apps Script。web/gas/Code.gs の rec-upload / rec-finish） ----------
  SP.toBase64 = (blob) => new Promise((resolve, reject) => {
    const fr = new FileReader();
    fr.onload = () => resolve(String(fr.result).split(',')[1]);
    fr.onerror = () => reject(fr.error);
    fr.readAsDataURL(blob);
  });
  SP.post = async function (body) {
    let last;
    for (let n = 0; n < 3; n++) {
      try {
        const r = await fetch(SP.api(), { method: 'POST', body: JSON.stringify(body) });
        const j = await r.json();
        if (j.ok) return j;
        throw Object.assign(new Error(j.error || 'error'), { server: true });
      } catch (e) {
        last = e;
        if (e.server && e.message !== 'missing') break;   // 受付側が断ったものは繰り返さない
        await new Promise((r) => setTimeout(r, 1500 * (n + 1)));
      }
    }
    throw last;
  };
  SP.SERVER_ERRORS = {
    closed: 'いまは受け付けていません。先生に伝えてください。',
    too_large: '録音が大きすぎます。その項目を短く録り直してください。',
    bad_request: '送信内容に不足があります。ページを開き直してください。',
    missing: '一部の録音が届いていません。もう一度送信してください。',
  };
  // 受付の状態（true＝受付中、false＝停止中、undefined＝受付側がまだ録音に対応していない）
  SP.recStatus = async function () {
    if (!SP.api()) return 'demo';
    try { const j = await (await fetch(SP.api())).json(); return j.recAccepting; } catch (e) { return null; }
  };

  // ---------- 端末内の保存（IndexedDB）。決定した録音を、提出するまで残す ----------
  SP.db = (function () {
    let p = null;
    function open() {
      if (!p) p = new Promise((res, rej) => {
        const rq = indexedDB.open('english-phonetics-speak', 1);
        rq.onupgradeneeded = () => rq.result.createObjectStore('kv');
        rq.onsuccess = () => res(rq.result);
        rq.onerror = () => rej(rq.error);
      });
      return p;
    }
    async function tx(mode, fn) {
      const db = await open();
      return new Promise((res, rej) => {
        const t = db.transaction('kv', mode), st = t.objectStore('kv'), rq = fn(st);
        t.oncomplete = () => res(rq && rq.result); t.onerror = () => rej(t.error);
      });
    }
    return {
      get: (k) => tx('readonly', (s) => s.get(k)).catch(() => undefined),
      put: (k, v) => tx('readwrite', (s) => s.put(v, k)).catch(() => undefined),
    };
  })();

  // ---------- 録音 ----------
  // 1回の録音ごとにマイクを開き、止めたら閉じる（iPhone で、マイクを開いたままだと再生音が小さくなるため）。
  // エコー除去・ノイズ抑制・自動音量調整は切る（分析に使えるよう、加工しない音を取る）。
  class Recorder {
    constructor() { this.ctx = null; this.stream = null; this.chunks = []; this.length = 0; this.level = 0; this.recording = false; this.live = false; this.onlive = null; this.onchunk = null; }
    get rate() { return this.ctx ? this.ctx.sampleRate : 48000; }
    get seconds() { return this.length / this.rate; }
    // タップの処理の中で（await より前に）呼ぶ。iPhone は利用者の操作の中でないと音声処理を始められない
    prime() {
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!this.ctx) this.ctx = new AC();
      if (this.ctx.state !== 'running') this.ctx.resume().catch(() => {});
    }
    async start() {
      this.prime();
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false },
      });
      if (this.ctx.state !== 'running') await this.ctx.resume();
      this.src = this.ctx.createMediaStreamSource(this.stream);
      this.proc = this.ctx.createScriptProcessor(2048, 1, 1);
      this.mute = this.ctx.createGain();
      this.mute.gain.value = 0;
      this.chunks = []; this.length = 0; this.level = 0; this.live = false; this.recording = true;
      this.proc.onaudioprocess = (e) => {
        if (!this.recording) return;
        const d = e.inputBuffer.getChannelData(0);
        let pk = 0;
        for (let i = 0; i < d.length; i++) { const v = Math.abs(d[i]); if (v > pk) pk = v; }
        this.level = pk;
        this.chunks.push(new Float32Array(d)); this.length += d.length;
        if (!this.live) { this.live = true; if (this.onlive) this.onlive(); }
        if (this.onchunk) this.onchunk(pk, d.length / this.ctx.sampleRate);
      };
      this.src.connect(this.proc); this.proc.connect(this.mute); this.mute.connect(this.ctx.destination);
    }
    stop() {
      this.recording = false;
      try { this.src.disconnect(); this.proc.disconnect(); this.mute.disconnect(); } catch (e) { /* 既に切れている */ }
      if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
      this.stream = null;
      const out = new Float32Array(this.length);
      let o = 0;
      for (const c of this.chunks) { out.set(c, o); o += c.length; }
      this.chunks = []; this.level = 0;
      return out;
    }
  }
  SP.Recorder = Recorder;

  // 話し終わりの検出：最初の 0.15 秒で雑音の大きさを測り、声が出たあと gap 秒静かになったら done() を呼ぶ
  SP.endDetector = function (done, gap) {
    let t = 0, noise = 0, n = 0, voiced = 0, quiet = 0, heard = false;
    return function (pk, dt) {
      t += dt;
      if (t < 0.15) { noise = Math.max(noise, pk); n++; return; }
      const thr = Math.max(0.02, noise * 4);
      if (pk > thr) { voiced += dt; quiet = 0; if (voiced > 0.08) heard = true; }
      else if (heard) { quiet += dt; if (quiet >= (gap || 0.9)) done(); }
    };
  };

  SP.peak = function (x) { let p = 0; for (let i = 0; i < x.length; i++) { const v = Math.abs(x[i]); if (v > p) p = v; } return p; };

  SP.encodeWav = function (samples, rate) {
    const buf = new ArrayBuffer(44 + samples.length * 2);
    const v = new DataView(buf);
    const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    str(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); str(8, 'WAVE');
    str(12, 'fmt '); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    str(36, 'data'); v.setUint32(40, samples.length * 2, true);
    let o = 44;
    for (let i = 0; i < samples.length; i++, o += 2) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(o, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return new Blob([buf], { type: 'audio/wav' });
  };

  // 録音の良し悪し（声の部分の長さ・最大振幅）。音割れ・小さすぎ・短すぎはその場で録り直しを促す
  SP.assess = function (voicedSec, peak) {
    if (voicedSec < 0.25) return { level: 'warn', text: '声がほとんど録れていません。もう一度録ってください。' };
    if (peak >= 0.99) return { level: 'warn', text: '音が割れています。スマホを少し離して録り直してください。' };
    if (peak < 0.03) return { level: 'warn', text: '音がとても小さいです。もう少し近くで録り直してください。' };
    return { level: 'ok', text: '録音できました。聞いて確かめてください。' };
  };

  // ---------- 前後の無音を切る ----------
  // 10 ms ごとのパワーで、最大から −40 dB と、雑音（下から1割の値）の3倍の大きい方をしきい値にする。
  // 語末の [θ] [f] のような弱い摩擦を落とさないよう、しきい値は低めにし、前後に 0.12 秒残す。
  SP.trim = function (x, rate) {
    const hop = Math.max(1, Math.round(rate * 0.01)), n = Math.floor(x.length / hop);
    if (n < 5) return [0, x.length];
    const e = new Float32Array(n);
    let mx = 0;
    for (let i = 0; i < n; i++) {
      let s = 0;
      for (let j = i * hop; j < (i + 1) * hop; j++) s += x[j] * x[j];
      e[i] = s / hop; if (e[i] > mx) mx = e[i];
    }
    const sorted = Array.from(e).sort((a, b) => a - b);
    const thr = Math.max(mx * 1e-4, sorted[Math.floor(n * 0.1)] * 3);
    let a = 0; while (a < n && e[a] < thr) a++;
    let b = n - 1; while (b > a && e[b] < thr) b--;
    if (a >= n) return [0, x.length];
    const pad = Math.round(0.12 * rate);
    return [Math.max(0, a * hop - pad), Math.min(x.length, (b + 1) * hop + pad)];
  };

  // ---------- サンプリング周波数の変換（窓付き sinc の低域通過つき） ----------
  SP.resample = function (x, rate, out) {
    if (rate === out) return x;
    const ratio = rate / out, fc = Math.min(1, 0.92 / ratio), half = Math.ceil(8 / fc);
    const n = Math.floor(x.length / ratio), y = new Float32Array(n);
    for (let k = 0; k < n; k++) {
      const t = k * ratio, c = Math.floor(t);
      let s = 0, ws = 0;
      for (let i = c - half + 1; i <= c + half; i++) {
        if (i < 0 || i >= x.length) continue;
        const d = t - i, a = Math.PI * fc * d;
        const h = (d === 0 ? 1 : Math.sin(a) / a) * (0.5 + 0.5 * Math.cos(Math.PI * d / (half + 1)));
        s += x[i] * h; ws += h;
      }
      y[k] = ws ? s / ws : 0;
    }
    return y;
  };

  // お手本（mp3）を読み込んで、[サンプル, サンプリング周波数] を返す
  SP.decodeUrl = async function (url) {
    const buf = await (await fetch(url)).arrayBuffer();
    const OAC = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const ctx = new OAC(1, 1, 44100);
    const ab = await new Promise((res, rej) => { const p = ctx.decodeAudioData(buf, res, rej); if (p && p.catch) p.catch(rej); });
    return [ab.getChannelData(0), ab.sampleRate];
  };

  // ---------- FFT（基数2） ----------
  function fft(re, im) {
    const n = re.length;
    for (let i = 1, j = 0; i < n; i++) {
      let bit = n >> 1;
      for (; j & bit; bit >>= 1) j ^= bit;
      j ^= bit;
      if (i < j) { let t = re[i]; re[i] = re[j]; re[j] = t; t = im[i]; im[i] = im[j]; im[j] = t; }
    }
    for (let len = 2; len <= n; len <<= 1) {
      const ang = -2 * Math.PI / len, wr = Math.cos(ang), wi = Math.sin(ang);
      for (let i = 0; i < n; i += len) {
        let cr = 1, ci = 0;
        for (let j = 0; j < len / 2; j++) {
          const a = i + j, b = a + len / 2;
          const tr = re[b] * cr - im[b] * ci, ti = re[b] * ci + im[b] * cr;
          re[b] = re[a] - tr; im[b] = im[a] - ti; re[a] += tr; im[a] += ti;
          const nr = cr * wr - ci * wi; ci = cr * wi + ci * wr; cr = nr;
        }
      }
    }
  }

  // ---------- 分析（16 kHz の信号に対して） ----------
  // 5 ms ごとに、強さ（25 ms 窓の RMS, dB）・声紋（8 ms ハン窓、0〜8 kHz、高域強調あり）を、
  // 10 ms ごとに声の高さ（YIN、70〜500 Hz）を求める。
  SP.analyze = function (x) {
    const fs = SP.AR, hop = 80, n = x.length, nf = Math.max(1, Math.floor(n / hop));
    const db = new Float32Array(nf);
    let dbMax = -200;
    for (let f = 0; f < nf; f++) {
      const c = f * hop + hop / 2, a = Math.max(0, c - 200), b = Math.min(n, c + 200);
      let s = 0;
      for (let i = a; i < b; i++) s += x[i] * x[i];
      db[f] = 10 * Math.log10(s / Math.max(1, b - a) + 1e-12);
      if (db[f] > dbMax) dbMax = db[f];
    }
    // 声の高さ（YIN）
    const f0 = new Float32Array(nf), W = 400, tmin = Math.floor(fs / 500), tmax = Math.ceil(fs / 70);
    const d = new Float32Array(tmax + 1);
    for (let f = 0; f < nf; f += 2) {
      if (db[f] < dbMax - 30) continue;
      const st = f * hop + hop / 2 - W / 2;
      if (st < 0 || st + W + tmax > n) continue;
      let cum = 0, best = -1;
      d[0] = 1;
      for (let t = 1; t <= tmax; t++) {
        let s = 0;
        for (let j = 0; j < W; j++) { const v = x[st + j] - x[st + j + t]; s += v * v; }
        cum += s;
        d[t] = cum > 0 ? s * t / cum : 1;
      }
      // しきい値 0.25 を最初に下回る谷。無ければ全体の最小（0.35 未満のときだけ有声とみなす）
      let gm = 9, gt = -1;
      for (let t = tmin; t < tmax; t++) {
        if (d[t] < 0.25) { while (t + 1 < tmax && d[t + 1] < d[t]) t++; best = t; break; }
        if (d[t] < gm) { gm = d[t]; gt = t; }
      }
      if (best < 0 && gm < 0.35) best = gt;
      if (best < 0) continue;
      const a = d[best - 1], b = d[best], c = d[best + 1], den = a - 2 * b + c;
      const tau = best + (den ? 0.5 * (a - c) / den : 0);
      f0[f] = fs / tau;
    }
    for (let f = 1; f < nf - 1; f += 2) if (f0[f - 1] && f0[f + 1]) f0[f] = (f0[f - 1] + f0[f + 1]) / 2;
    // 1オクターブの飛び（倍・半分の誤り）を直し、ごく短い有声区間（30 ms 未満）は捨てる
    const median = () => { const v = Array.from(f0).filter(Boolean).sort((p, q) => p - q); return v.length ? v[Math.floor(v.length / 2)] : 0; };
    let med = median();
    if (med) {
      for (let f = 0; f < nf; f++) {
        if (!f0[f]) continue;
        if (f0[f] > med * 1.7) f0[f] /= 2; else if (f0[f] < med * 0.6) f0[f] *= 2;
        if (f0[f] > med * 1.8 || f0[f] < med * 0.55) f0[f] = 0;
      }
      for (let f = 0; f < nf;) {
        if (!f0[f]) { f++; continue; }
        let g = f; while (g < nf && f0[g]) g++;
        if (g - f < 6) for (let k = f; k < g; k++) f0[k] = 0;
        f = g;
      }
      med = median();
    }
    // 声紋
    const N = 256, L = 128, bins = 128, spec = new Float32Array(nf * bins);
    const win = new Float32Array(L);
    for (let i = 0; i < L; i++) win[i] = 0.5 - 0.5 * Math.cos(2 * Math.PI * i / (L - 1));
    const re = new Float32Array(N), im = new Float32Array(N);
    let specMax = -200;
    for (let f = 0; f < nf; f++) {
      re.fill(0); im.fill(0);
      const st = f * hop + hop / 2 - L / 2;
      for (let i = 0; i < L; i++) {
        const k = st + i;
        if (k >= 1 && k < n) re[i] = (x[k] - 0.97 * x[k - 1]) * win[i];
      }
      fft(re, im);
      for (let b = 0; b < bins; b++) {
        const p = 10 * Math.log10(re[b] * re[b] + im[b] * im[b] + 1e-12);
        spec[f * bins + b] = p; if (p > specMax) specMax = p;
      }
    }
    return { fs, hop, nf, dur: n / fs, db, dbMax, f0, med, spec, specMax, bins, x };
  };

  // 録音（Float32, rate）から、無音を切った区間・その WAV・分析をまとめて作る
  SP.prepare = function (x, rate) {
    const [a, b] = SP.trim(x, rate);
    const cut = x.subarray(a, b);
    return { t0: a / rate, samples: cut, rate, an: SP.analyze(SP.resample(cut, rate, SP.AR)) };
  };

  // ---------- 描画 ----------
  function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }
  function rgb(hex) {
    const h = hex.replace('#', '');
    const v = h.length === 3 ? h.split('').map((c) => parseInt(c + c, 16)) : [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
    return v.some(isNaN) ? [128, 128, 128] : v;
  }
  function setup(canvas) {
    const dpr = window.devicePixelRatio || 1, w = canvas.clientWidth, h = canvas.clientHeight;
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(h * dpr);
    const g = canvas.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    return { g, w, h };
  }
  function label(g, text, x, y, align) {
    g.font = '600 11px -apple-system, "Hiragino Sans", sans-serif';
    g.textAlign = align || 'left'; g.textBaseline = 'top';
    g.fillStyle = css('--plot-sub') || '#666';
    g.fillText(text, x, y);
  }

  // 声紋：横が時間（total 秒を全幅）、縦が 0〜8,000 Hz。濃いほど強い
  SP.drawSpec = function (canvas, an, total) {
    const { g, w, h } = setup(canvas);
    const bg = rgb(css('--plot-bg') || '#ffffff'), ink = rgb(css('--plot-ink') || '#000000');
    g.fillStyle = 'rgb(' + bg.join(',') + ')'; g.fillRect(0, 0, w, h);
    const off = document.createElement('canvas');
    off.width = an.nf; off.height = an.bins;
    const og = off.getContext('2d'), img = og.createImageData(an.nf, an.bins), range = 55;
    for (let f = 0; f < an.nf; f++) {
      for (let b = 0; b < an.bins; b++) {
        let v = (an.spec[f * an.bins + b] - (an.specMax - range)) / range;
        v = v <= 0 ? 0 : Math.pow(Math.min(1, v), 1.3);
        const p = ((an.bins - 1 - b) * an.nf + f) * 4;
        img.data[p] = bg[0] + (ink[0] - bg[0]) * v; img.data[p + 1] = bg[1] + (ink[1] - bg[1]) * v;
        img.data[p + 2] = bg[2] + (ink[2] - bg[2]) * v; img.data[p + 3] = 255;
      }
    }
    og.putImageData(img, 0, 0);
    g.imageSmoothingEnabled = true;
    g.drawImage(off, 0, 0, an.nf, an.bins, 0, 0, w * Math.min(1, an.dur / total), h);
    g.strokeStyle = css('--plot-grid') || 'rgba(0,0,0,.15)'; g.lineWidth = 1; g.setLineDash([3, 4]);
    [2000, 4000, 6000].forEach((hz) => {
      const y = Math.round(h * (1 - hz / 8000)) + 0.5;
      g.beginPath(); g.moveTo(0, y); g.lineTo(w, y); g.stroke();
      label(g, (hz / 1000) + 'k', w - 3, y + 1, 'right');
    });
    g.setLineDash([]);
  };

  // 高さと強さ：上は声の高さ（その人のふだんの高さを中央にした半音の目盛り）、下は強さ（最大から 50 dB）
  SP.drawPitch = function (canvas, an, total) {
    const { g, w, h } = setup(canvas);
    g.fillStyle = css('--plot-bg') || '#fff'; g.fillRect(0, 0, w, h);
    const X = (f) => ((f * an.hop + an.hop / 2) / an.fs) / total * w;
    // 強さ（下 45%）
    const base = h, top = h * 0.55;
    g.beginPath(); g.moveTo(X(0), base);
    for (let f = 0; f < an.nf; f++) {
      const v = Math.max(0, Math.min(1, (an.db[f] - (an.dbMax - 50)) / 50));
      g.lineTo(X(f), base - v * (base - top));
    }
    g.lineTo(X(an.nf - 1), base); g.closePath();
    g.fillStyle = css('--plot-int') || 'rgba(0,0,0,.15)'; g.fill();
    // 中央の線（その人のふだんの高さ）
    const mid = h * 0.30, span = h * 0.26;   // ±10 半音
    g.strokeStyle = css('--plot-grid') || 'rgba(0,0,0,.15)'; g.setLineDash([3, 4]);
    g.beginPath(); g.moveTo(0, mid + 0.5); g.lineTo(w, mid + 0.5); g.stroke(); g.setLineDash([]);
    if (!an.med) { label(g, '声の高さを測れませんでした', 6, 4); label(g, '強さ', 6, h - 16); return; }
    g.strokeStyle = css('--plot-f0') || '#c33'; g.fillStyle = g.strokeStyle; g.lineWidth = 3; g.lineCap = 'round'; g.lineJoin = 'round';
    let on = false;
    g.beginPath();
    for (let f = 0; f < an.nf; f++) {
      if (!an.f0[f]) { on = false; continue; }
      const st = Math.max(-10, Math.min(10, 12 * Math.log2(an.f0[f] / an.med)));
      const x = X(f), y = mid - st / 10 * span;
      if (on) g.lineTo(x, y); else g.moveTo(x, y);
      on = true;
    }
    g.stroke();
    label(g, '高さ（F0）', 6, 4); label(g, '強さ', 6, h - 16);
    label(g, '点線＝' + Math.round(an.med) + ' Hz　上下 ±10 半音', w - 4, 4, 'right');
  };

  // 波形（オシログラム）：横は total 秒を全幅、縦はその録音の最大振幅にそろえる
  SP.drawOsc = function (canvas, an, total) {
    const { g, w, h } = setup(canvas);
    g.fillStyle = css('--plot-bg') || '#fff'; g.fillRect(0, 0, w, h);
    const x = an.x, n = x.length, ww = w * Math.min(1, an.dur / total), mid = h / 2;
    let pk = 0; for (let i = 0; i < n; i++) { const v = Math.abs(x[i]); if (v > pk) pk = v; }
    const k = pk > 0 ? 0.92 / pk : 1;
    g.strokeStyle = css('--plot-grid') || 'rgba(0,0,0,.15)'; g.beginPath(); g.moveTo(0, mid + 0.5); g.lineTo(w, mid + 0.5); g.stroke();
    g.fillStyle = css('--plot-ink') || '#000';
    for (let px = 0; px < ww; px++) {
      const a = Math.floor(px / ww * n), b = Math.max(a + 1, Math.floor((px + 1) / ww * n));
      let mn = 0, mx = 0;
      for (let i = a; i < b && i < n; i++) { const v = x[i]; if (v < mn) mn = v; if (v > mx) mx = v; }
      g.fillRect(px, mid - mx * k * mid, 1, Math.max(1, (mx - mn) * k * mid));
    }
    // 0.1 秒ごとの目盛り
    g.fillStyle = css('--plot-sub') || '#666';
    for (let t = 0.1; t < total; t += 0.1) g.fillRect(Math.round(t / total * w), h - (Math.round(t * 10) % 5 ? 4 : 8), 1, 8);
    label(g, '波形（音圧の変化）', 6, 4);
  };

  // 波形（テストの録音確認用）
  SP.drawWave = function (canvas, samples) {
    const { g, w, h } = setup(canvas);
    g.fillStyle = css('--plot-f0') || '#1f4fa8';
    const step = Math.max(1, Math.floor(samples.length / w)), mid = h / 2;
    for (let x = 0; x < w; x++) {
      let mn = 0, mx = 0;
      for (let i = x * step; i < x * step + step && i < samples.length; i++) { const v = samples[i]; if (v < mn) mn = v; if (v > mx) mx = v; }
      g.fillRect(x, mid - mx * mid * 0.95, 1, Math.max(1, (mx - mn) * mid * 0.95));
    }
  };
})();
