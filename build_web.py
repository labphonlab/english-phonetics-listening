#!/usr/bin/env python3
"""受講者向け「聞いて練習」ページ（GitHub Pages: labphonlab/english-phonetics-listening）を作る。

公開ライセンスの音声（Wikimedia Commons／Lingua Libre：CC0・CC BY-SA・PD）だけを載せる。
深澤（2015）DB（fk_）と JIPA 付属音声（ga_・rp_）は公開しない（books/english-phonetics/teaching-platform/SOURCE_USE.md）。
音声は lecture03/audio/*.mp3（無音を切り −18 LUFS にそろえた mp3）を、タグを消してコピーする。

使い方: python3 web/build_web.py   → web/ の index.html・lecture03/ を作り直す
"""
import html, json, os, re, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
L3 = os.path.join(ROOT, "lecture03")
FOUND = json.load(open(os.path.join(L3, "_commons", "found.json")))

LIC_URL = {
    "CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/deed.ja",
    "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/deed.ja",
    "CC0": "https://creativecommons.org/publicdomain/zero/1.0/deed.ja",
    "Public domain": "",
}
# found.json（En-us-<語>.ogg）に無い録音の出典。キー → (Commons のファイル名, ライセンス, 話者)
EXTRA = {
    "gk_Ruth": ("LL-Q1860 (eng)-Grendelkhan-Ruth.wav", "CC0", "Grendelkhan"),
    "gk_selling": ("LL-Q1860 (eng)-Grendelkhan-selling.wav", "CC0", "Grendelkhan"),
    "us_zen": ("En-us-zen.ogg", "CC BY-SA 3.0", "Dvortygirl"),
    "us_close-verb": ("En-us-close-verb.ogg", "CC BY-SA 3.0", "Dvortygirl"),
    "vh_curb": ("LL-Q1860 (eng)-Vealhurl-curb.wav", "CC BY-SA 4.0", "Vealhurl"),
    "vh_swiss": ("LL-Q1860 (eng)-Vealhurl-Swiss.wav", "CC BY-SA 4.0", "Vealhurl"),
    "vh_volt": ("LL-Q1860 (eng)-Vealhurl-volt.wav", "CC BY-SA 4.0", "Vealhurl"),
    "vh_shelling": ("LL-Q1860 (eng)-Vealhurl-shelling.wav", "CC BY-SA 4.0", "Vealhurl"),
    "au_swish": ("En-au-swish.ogg", "CC BY-SA 4.0", "Commander Keane"),
}


def source(key):
    if key in EXTRA:
        return EXTRA[key]
    word = key[3:]
    v = FOUND[f"File:En-us-{word}.ogg"]
    artist = re.sub(r"<[^>]+>", "", v["artist"])
    artist = re.sub(r"No machine-readable author provided\. (\S+) assumed.*", r"\1", artist).strip()
    return (f"En-us-{word}.ogg", v["lic"], artist or "（記載なし）")


# 語 → (音声キー, 意味)
W = {
    "think": ("us_think", "考える"), "sink": ("us_sink", "沈む"), "thaw": ("us_thaw", "解ける"), "saw": ("us_saw", "見た"),
    "faith": ("us_faith", "信頼"), "face": ("us_face", "顔"),
    "free": ("us_free", "自由な"), "three": ("us_three", "3"), "first": ("us_first", "最初の"), "thirst": ("us_thirst", "渇き"),
    "roof": ("us_roof", "屋根"), "Ruth": ("gk_Ruth", "ルース（人名）"),
    "then": ("us_then", "そのとき"), "Zen": ("us_zen", "禅"), "breathe": ("us_breathe", "呼吸する"), "breeze": ("us_breeze", "そよ風"),
    "clothe": ("us_clothe", "服を着せる"), "close": ("us_close-verb", "閉める"),
    "berry": ("us_berry", "ベリー"), "very": ("us_very", "とても"), "boat": ("us_boat", "ボート"), "vote": ("us_vote", "投票"),
    "curb": ("vh_curb", "縁石"), "curve": ("us_curve", "曲線"),
    "see": ("us_see", "見る"), "she": ("us_she", "彼女"), "mess": ("us_mess", "散らかり"), "mesh": ("us_mesh", "網目"),
    "Swiss": ("vh_swiss", "スイスの"), "swish": ("au_swish", "ヒュッと振る"),
    "light": ("us_light", "光"), "right": ("us_right", "右"), "lip": ("us_lip", "唇"), "rip": ("us_rip", "裂く"),
    "lamb": ("us_lamb", "子羊"), "ram": ("us_ram", "雄羊"),
    "pass": ("us_pass", "峠"), "path": ("us_path", "小道"), "thought": ("us_thought", "考えた"), "fought": ("us_fought", "けんかした"),
    "bolt": ("us_bolt", "ボルト"), "volt": ("vh_volt", "ボルト（電圧）"), "shelling": ("vh_shelling", "殻をむく"), "selling": ("gk_selling", "売る"),
    "collect": ("us_collect", "集める"), "correct": ("us_correct", "訂正する"), "train": ("us_train", "列車"), "chain": ("us_chain", "鎖"),
    "playing": ("us_playing", "遊んでいる"), "praying": (None, "祈っている"), "play": ("us_play", "遊ぶ"), "pray": ("us_pray", "祈る"),
}

# 3.1（スライド47）：対立ごとに語対
S31 = [
    ("/θ/–/s/", [("think", "sink"), ("thaw", "saw"), ("faith", "face")]),
    ("/f/–/θ/", [("free", "three"), ("first", "thirst"), ("roof", "Ruth")]),
    ("/ð/–/z/", [("then", "Zen"), ("breathe", "breeze"), ("clothe", "close")]),
    ("/b/–/v/", [("berry", "very"), ("boat", "vote"), ("curb", "curve")]),
    ("/s/–/ʃ/", [("see", "she"), ("mess", "mesh"), ("Swiss", "swish")]),
    ("/l/–/r/", [("light", "right"), ("lip", "rip"), ("lamb", "ram")]),
]
# 3.2（スライド48・49）：文の中の語対。8 はスライドの playing / praying に praying の録音が無いので、
# 音声のそろう play / pray の文に替えた（10/20 ユーザー指示「音声がない単語のペアは別のペアに変えても良い」）
S32 = [
    ("He went over the", "pass", "path", "."), ("They", "thought", "fought", "about it."),
    ("Did you say", "bolt", "volt", "?"), ("Who's", "shelling", "selling", "peas?"),
    ("He didn't", "collect", "correct", "the papers."), ("Look at the", "train", "chain", "."),
    ("Just look at the", "ram", "lamb", "in the field."), ("Let's", "play", "pray", "together."),
]
# 録音の話し方についての注記（語 → 注）
NOTE = {
    "curb": "curb は r を発音しない話し方の録音（curve とは別の話者）",
    "swish": "Swiss・swish は別の話者（swish はオーストラリア英語）",
    "volt": "volt は bolt と別の話者",
    "shelling": "shelling と selling は別の話者",
}

USED = []


def use(word):
    key = W[word][0]
    if key and key not in USED:
        USED.append(key)
    return key


def btn(word):
    key = use(word)
    mean = html.escape(W[word][1])
    w = html.escape(word)
    if not key:
        return f'<button class="w off" disabled><span class="en">{w}</span><span class="ja">{mean}</span><span class="na">録音なし</span></button>'
    return f'<button class="w" data-a="audio/{key}.mp3"><span class="en">{w}</span><span class="ja">{mean}</span></button>'


def quiz(a, b):
    ka, kb = W[a][0], W[b][0]
    if not (ka and kb):
        return ""
    return (f'<button class="q" data-pair="audio/{ka}.mp3|audio/{kb}.mp3" data-words="{html.escape(a)}|{html.escape(b)}" '
            f'aria-label="{html.escape(a)} か {html.escape(b)} のどちらかが流れる">どっち？</button>')


def pair(a, b):
    return f'<div class="pair">{btn(a)}{btn(b)}{quiz(a, b)}</div><p class="res" aria-live="polite"></p>'


def build_l3():
    out = []
    out.append('<section id="s31"><h2><span class="no">3.1</span>子音対立を聞き分けて発音する</h2>')
    out.append('<p class="lead">語をタップすると音声が流れます。<b>どっち？</b> を押すと2語のどちらかが流れるので、聞こえた方をタップしてください。</p>')
    notes = []
    for label, pairs in S31:
        out.append(f'<div class="card"><h3 class="ipa">{html.escape(label)}</h3>')
        for a, b in pairs:
            out.append(pair(a, b))
            notes += [NOTE[x] for x in (a, b) if x in NOTE]
        out.append("</div>")
    out.append('<div class="point"><b>ポイント</b>話し手は一方を選んで言う。聞き手は語と「手がかり」を書く。</div>')
    if notes:
        out.append('<ul class="notes">' + "".join(f"<li>{html.escape(n)}</li>" for n in notes) + "</ul>")
    out.append("</section>")

    out.append('<section id="s32"><h2><span class="no">3.2</span>文脈の中で子音を識別する</h2>')
    out.append('<p class="lead">授業では文の音声で練習しました。ここでは語の音声だけ聞けます。文の中に入れて自分で言ってみましょう。</p>')
    notes = []
    for i, (pre, a, b, post) in enumerate(S32, 1):
        sep = "" if post in (".", "?") else " "
        sent = (f'{html.escape(pre)} (<b class="ca">{html.escape(a)}</b> / <b class="cb">{html.escape(b)}</b>){sep}{html.escape(post)}')
        out.append(f'<div class="card"><p class="sent"><span class="n">{i}</span><i>{sent}</i></p>')
        out.append(pair(a, b))
        notes += [NOTE[x] for x in (a, b) if x in NOTE]
        out.append("</div>")
    out.append('<div class="point"><b>ポイント</b>誤答が多い対立は「接触・摩擦・側面の息・声帯振動のどれ？」を一文で記録。</div>')
    if notes:
        out.append('<ul class="notes">' + "".join(f"<li>{html.escape(n)}</li>" for n in notes) + "</ul>")
    out.append("</section>")
    return "\n".join(out)


def credits():
    rows = []
    for key in USED:
        f, lic, who = source(key)
        assert lic in LIC_URL, (key, lic)
        words = ", ".join(w for w, v in W.items() if v[0] == key)
        page = "https://commons.wikimedia.org/wiki/File:" + f.replace(" ", "_")
        lic_html = f'<a href="{LIC_URL[lic]}">{lic}</a>' if LIC_URL[lic] else lic
        rows.append(f'<tr><td>{html.escape(words)}</td><td><a href="{html.escape(page)}">{html.escape(who)}</a></td><td>{lic_html}</td></tr>')
    return "\n".join(rows)


CSS = """
:root{--bg:#F6F4EF;--card:#FFFFFF;--ink:#1B2238;--sub:#5B6573;--line:#E2DED5;--btn:#F2A93B;--btn-ink:#1B2238;--btn-on:#D98A12;
--a:#1F8A7D;--b:#D6452B;--band:#2B3A67;--band-ink:#FFFFFF;--hd:#8C3A26;--ok:#1F8A7D;--ng:#D6452B}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15181F;--card:#1F242E;--ink:#ECEEF2;--sub:#A3ABB8;--line:#323947;
--btn:#E9A23A;--btn-ink:#1B1B1B;--btn-on:#FFC266;--a:#4CC3B3;--b:#FF7A63;--band:#2B3A67;--hd:#B9584A}}
:root[data-theme="dark"]{--bg:#15181F;--card:#1F242E;--ink:#ECEEF2;--sub:#A3ABB8;--line:#323947;--btn:#E9A23A;--btn-ink:#1B1B1B;--btn-on:#FFC266;--a:#4CC3B3;--b:#FF7A63;--hd:#B9584A}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,"Hiragino Sans","Noto Sans JP","Segoe UI",sans-serif;
line-height:1.6;font-size:17px;padding-bottom:env(safe-area-inset-bottom)}
header{background:var(--hd);color:#fff;padding:calc(18px + env(safe-area-inset-top)) 16px 16px}
header p{margin:0;font-size:14px;opacity:.85}
header h1{margin:2px 0 0;font-size:24px;line-height:1.3}
nav{position:sticky;top:0;z-index:5;display:flex;gap:8px;padding:8px 16px;background:var(--bg);border-bottom:1px solid var(--line)}
nav a{flex:1;text-align:center;padding:8px 4px;border-radius:999px;border:1px solid var(--line);color:var(--ink);text-decoration:none;font-weight:600;font-size:15px;background:var(--card)}
main{max-width:640px;margin:0 auto;padding:0 16px}
section{padding-top:8px;scroll-margin-top:56px}
h2{font-size:21px;margin:22px 0 6px;line-height:1.35}
h2 .no{display:inline-block;margin-right:8px;color:var(--hd)}
.lead{color:var(--sub);font-size:15px;margin:0 0 12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;margin:0 0 12px}
h3.ipa{margin:0 0 8px;font-size:19px;color:var(--sub);font-family:"Arial Unicode MS","Lucida Grande","Noto Sans",sans-serif;font-weight:700}
.pair{display:grid;grid-template-columns:1fr 1fr auto;gap:8px;align-items:stretch}
.pair+.res{min-height:0;margin:2px 0 8px;font-size:15px;text-align:center}
.res:empty{margin:0 0 8px}
button{font:inherit;color:inherit;-webkit-tap-highlight-color:transparent;cursor:pointer;touch-action:manipulation}
.w{min-height:64px;border:0;border-radius:14px;background:var(--btn);color:var(--btn-ink);display:flex;flex-direction:column;align-items:center;justify-content:center;padding:6px 4px;
box-shadow:0 2px 0 rgba(0,0,0,.15);transition:transform .06s}
.w .en{font-size:21px;font-weight:700;line-height:1.15}
.w .en::before{content:"▶ ";font-size:13px;vertical-align:2px}
.w .ja{font-size:13px;line-height:1.3;opacity:.85}
.w .na{font-size:12px}
.w:active,.w.on{transform:translateY(1px);background:var(--btn-on)}
.w.off{background:var(--line);color:var(--sub);box-shadow:none}
.w.off .en::before{content:""}
.q{min-height:64px;width:64px;border:2px solid var(--btn);border-radius:14px;background:transparent;color:var(--ink);font-size:13px;font-weight:700;line-height:1.2;padding:4px}
.q:active,.q.on{background:var(--btn);color:var(--btn-ink)}
.pair.ask .w{outline:3px dashed var(--btn);outline-offset:2px}
.ok{color:var(--ok);font-weight:700}.ng{color:var(--ng);font-weight:700}
.sent{margin:0 0 10px;font-size:18px;line-height:1.5;display:flex;gap:10px}
.sent .n{font-weight:700;color:var(--sub);font-style:normal}
.ca{color:var(--a)}.cb{color:var(--b)}
.sub{font-size:14px;color:var(--sub);margin:6px 0 6px}
.point{background:var(--band);color:var(--band-ink);border-radius:12px;padding:12px 14px;font-size:15px;margin:4px 0 8px}
.point b{color:#F2A93B;margin-right:10px}
.notes{color:var(--sub);font-size:13px;padding-left:20px;margin:6px 0 0}
footer{max-width:640px;margin:28px auto 0;padding:0 16px 32px;color:var(--sub);font-size:13px}
footer h2{font-size:16px;color:var(--ink)}
footer table{width:100%;border-collapse:collapse;font-size:12.5px}
footer td{border-top:1px solid var(--line);padding:5px 4px;vertical-align:top}
footer a{color:inherit}
details summary{cursor:pointer;font-weight:600;color:var(--ink);padding:6px 0}
@media (max-width:360px){.w .en{font-size:18px}.q{width:54px}}
"""

JS = """
let cur=null;const cache={};
function aud(src){if(!cache[src]){cache[src]=new Audio(src);cache[src].preload="auto"}return cache[src]}
function play(src,el){if(cur){cur.pause();cur.currentTime=0}const a=aud(src);cur=a;a.currentTime=0;
 if(el){el.classList.add('on');a.onended=()=>el.classList.remove('on');setTimeout(()=>el.classList.remove('on'),1500)}
 a.play().catch(()=>{})}
document.addEventListener('click',e=>{
 const w=e.target.closest('.w[data-a]');const q=e.target.closest('.q');
 if(q){const pr=q.parentElement;const srcs=q.dataset.pair.split('|'),ws=q.dataset.words.split('|');
  if(pr.dataset.ans===undefined||pr.dataset.ans===''){pr.dataset.ans=Math.random()<.5?0:1}
  pr.classList.add('ask');pr.nextElementSibling.textContent='聞こえた方をタップ（もう一度：どっち？）';
  play(srcs[+pr.dataset.ans],q);return}
 if(w){const pr=w.parentElement;
  if(pr.classList.contains('ask')){const ws=pr.querySelector('.q').dataset.words.split('|');const i=[...pr.querySelectorAll('.w')].indexOf(w);
   const ok=i===+pr.dataset.ans;const r=pr.nextElementSibling;
   r.innerHTML=ok?'<span class="ok">○ 正解</span>：'+ws[pr.dataset.ans]:'<span class="ng">× 今のは</span> '+ws[pr.dataset.ans];
   pr.classList.remove('ask');pr.dataset.ans=''}
  play(w.dataset.a,w)}
});
"""

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="#8C3A26">
<title>子音を聞いて練習</title>
<style>{css}</style></head>
<body>
<header><p>英語音声学　第3回</p><h1>子音を聞いて練習</h1></header>
<nav><a href="#s31">3.1 語対</a><a href="#s32">3.2 文脈</a><a href="#credits">出典</a></nav>
<main>
{body}
</main>
<footer id="credits">
<h2>音声の出典</h2>
<p>音声はすべて Wikimedia Commons（Lingua Libre を含む）で公開されている録音です。授業用に、前後の無音を切り、音量をそろえ、MP3 に変換しました。CC BY-SA の録音を加工した音声は、同じライセンス（CC BY-SA）で利用できます。話者名から Commons の元ファイルに移れます。</p>
<details><summary>一覧を開く（{n} 件）</summary>
<table><tbody>
{credits}
</tbody></table></details>
<p>ページ：英語音声学（目白大学）授業資料</p>
</footer>
<script>{js}</script>
</body></html>
"""

INDEX = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>英語音声学 聞いて練習</title>
<style>
:root{--bg:#F6F4EF;--ink:#1B2238;--card:#fff;--line:#E2DED5}
@media (prefers-color-scheme:dark){:root{--bg:#15181F;--ink:#ECEEF2;--card:#1F242E;--line:#323947}}
body{margin:0;background:var(--bg);color:var(--ink);font-family:-apple-system,"Hiragino Sans","Noto Sans JP",sans-serif;padding:24px 16px;font-size:17px}
main{max-width:640px;margin:0 auto}a{display:block;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px;color:inherit;text-decoration:none;margin:10px 0;font-weight:600}
</style></head><body><main>
<h1>英語音声学　聞いて練習</h1>
<a href="lecture03/">第3回　子音（3.1 語対・3.2 文脈）</a>
</main></body></html>
"""


def main():
    body = build_l3()
    d = os.path.join(WEB, "lecture03")
    ad = os.path.join(d, "audio")
    if os.path.isdir(ad):
        shutil.rmtree(ad)
    os.makedirs(ad)
    for key in USED:
        src = os.path.join(L3, "audio", key + ".mp3")
        assert not key.startswith(("fk_", "ga_", "rp_")), key   # 公開不可の音声を載せない
        # ID3 タグなどのメタデータを消してコピー（音声データはそのまま）
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", src, "-map_metadata", "-1",
                        "-c:a", "copy", "-write_xing", "0", os.path.join(ad, key + ".mp3")], check=True)
    open(os.path.join(d, "index.html"), "w").write(
        PAGE.replace("{body}", body).replace("{credits}", credits()).replace("{n}", str(len(USED)))
        .replace("{css}", CSS).replace("{js}", JS))
    import test_page   # 聞き取りテスト（lecture03/test.html）
    open(os.path.join(d, "test.html"), "w").write(test_page.page(W, S31, S32))
    open(os.path.join(WEB, "index.html"), "w").write(INDEX)
    open(os.path.join(WEB, ".nojekyll"), "w").write("")
    print(len(USED), "files ->", ad)


if __name__ == "__main__":
    main()
