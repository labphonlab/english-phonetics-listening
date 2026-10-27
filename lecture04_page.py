"""第4回（子音連続と音節）の「聞いて練習」ページと聞き取りテストを作る。build_web.py の main() から呼ぶ。

音声は ../lecture04/audio の公開ライセンス録音だけ（Commons の米音辞書形 us_、Lingua Libre の gk_・ll_）。
授業スライドの例文（深澤 2015、fk_）は公開しないので、このページは語だけを聞く。
テストの語対は、声の違いで当たらないよう同じ話者（Commons の Dvortygirl）の録音でそろえた。
"""
import html, json, os, re, shutil, subprocess

import test_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
L4 = os.path.join(ROOT, "lecture04")
FOUND = json.load(open(os.path.join(L4, "_commons", "found.json")))
LL = json.load(open(os.path.join(L4, "_commons", "ll_ch4_found.json")))
TEST_ID = "l04-clusters"

MEAN = {
    "street": "通り", "desk": "机", "button": "ボタン", "cotton": "綿", "written": "書かれた", "hidden": "隠れた", "kitten": "子猫",
    "gentle": "優しい", "title": "題名", "little": "小さい", "metal": "金属", "apple": "りんご", "settle": "落ち着く", "cattle": "牛",
    "bottle": "びん", "middle": "真ん中", "sudden": "突然の", "seven": "7", "lesson": "授業",
    "speak": "話す", "stop": "止まる", "sky": "空", "small": "小さい", "snow": "雪", "play": "遊ぶ", "tree": "木", "quick": "速い",
    "cute": "かわいい", "green": "緑", "blue": "青い", "try": "試す", "press": "押す", "brush": "ブラシ", "crash": "衝突",
    "grain": "穀物", "fried": "揚げた", "clear": "はっきりした", "place": "場所", "glad": "うれしい", "flight": "飛行（便）",
    "splendid": "見事な", "twins": "双子", "dwell": "住む", "square": "四角", "swift": "速い",
    "tie": "ネクタイ", "kick": "蹴る", "rye": "ライ麦", "loo": "トイレ（英）", "wick": "ろうそくの芯",
    "eat": "食べる", "treat": "もてなす", "jump": "跳ぶ", "milk": "牛乳", "act": "行為", "acts": "行為（複数）",
    "help": "助ける", "helped": "助けた", "texts": "文書（複数）", "bag": "かばん", "dog": "犬", "cat": "猫", "big": "大きい",
    "sixths": "6分の1（複数）", "strengths": "強み（複数）", "glimpsed": "ちらりと見た",
    "tea": "お茶", "pay": "払う", "pace": "歩調", "bush": "やぶ", "gain": "得る", "fight": "戦う", "top": "頂上", "no": "いいえ",
    "slow": "遅い", "low": "低い", "ask": "尋ねる", "asked": "尋ねた", "push": "押す", "pushed": "押した", "watch": "見る",
    "watched": "見た", "walk": "歩く", "walked": "歩いた", "miss": "逃す", "missed": "逃した", "book": "本", "books": "本（複数）",
    "plant": "植物", "plants": "植物（複数）", "gift": "贈り物", "gifts": "贈り物（複数）",
    "treated": "扱った", "started": "始めた", "needed": "必要とした", "wanted": "欲しがった",
}


def key(w):
    for p in ("us_", "gk_", "ll_"):
        k = p + w.lower()
        if os.path.exists(os.path.join(L4, "audio", k + ".mp3")):
            return k
    return None


def source(k):
    if k.startswith("us_"):
        v = FOUND[f"File:En-us-{k[3:]}.ogg"]
        f = f"En-us-{k[3:]}.ogg"
    else:
        v = LL[k]
        f = v["title"][len("File:"):]
    artist = re.sub(r"<[^>]+>", "", v["artist"])
    artist = re.sub(r"No machine-readable author provided\. (\S+) assumed.*", r"\1", artist).split("\n")[0]
    return f, v["lic"], artist.replace("Speaker: ", "").strip() or "（記載なし）"


USED = []


def btn(w):
    k = key(w)
    ja = html.escape(MEAN.get(w, ""))
    if not k:
        return f'<button class="w off" disabled><span class="en">{html.escape(w)}</span><span class="ja">{ja}</span><span class="na">録音なし</span></button>'
    if k not in USED:
        USED.append(k)
    return f'<button class="w" data-a="audio/{k}.mp3"><span class="en">{html.escape(w)}</span><span class="ja">{ja}</span></button>'


def row(words):
    return '<div class="row">' + "".join(btn(w) for w in words) + "</div>"


def pair(a, b):
    ka, kb = key(a), key(b)
    q = (f'<button class="q" data-pair="audio/{ka}.mp3|audio/{kb}.mp3" data-words="{a}|{b}" aria-label="{a} か {b} のどちらかが流れる">どっち？</button>'
         if ka and kb else "")
    return f'<div class="pair">{btn(a)}{btn(b)}{q}</div><p class="res" aria-live="polite"></p>'


# 練習ページで「どっち？」を付ける語対（テストと同じ。同じ話者でそろう対）
ONSET = [("try", "tie"), ("quick", "kick"), ("tree", "tea"), ("play", "pay"), ("place", "pace"), ("brush", "bush"),
         ("grain", "gain"), ("flight", "fight"), ("stop", "top"), ("snow", "no"), ("slow", "low")]
CODA = [("help", "helped"), ("ask", "asked"), ("push", "pushed"), ("watch", "watched"), ("walk", "walked"),
        ("miss", "missed"), ("book", "books"), ("act", "acts"), ("plant", "plants"), ("gift", "gifts")]
COUNT = [("street", 1), ("pushed", 1), ("asked", 1), ("walked", 1), ("watched", 1),
         ("treated", 2), ("started", 2), ("needed", 2), ("button", 2), ("little", 2)]


def body():
    o = []
    o.append('<section id="onset"><h2><span class="no">1</span>語頭の子音連続</h2>')
    o.append('<p class="lead">2つ・3つの子音の間に母音を入れず、一つの音節として聞く・言う。語をタップすると音声が流れます。</p>')
    o.append('<div class="card"><h3>3つの型</h3><p class="lab">/s/＋無声破裂音</p>' + row(["speak", "stop", "sky"])
             + '<p class="lab">/s/＋鼻音</p>' + row(["small", "snow"])
             + '<p class="lab">破裂音＋接近音</p>' + row(["play", "tree", "quick", "cute", "green", "blue"]) + "</div>")
    o.append('<div class="card"><h3>/r, l, w/ へ母音をはさまず移る</h3><p class="lab">/r/：舌先は触れない</p>' + row(["try", "press", "brush", "crash", "grain", "fried"])
             + '<p class="lab">/l/：舌先が歯茎に触れ、側面から息</p>' + row(["clear", "place", "blue", "glad", "flight", "splendid"])
             + '<p class="lab">/w/：唇を丸め、舌の後ろを上げる</p>' + row(["twins", "quick", "dwell", "square", "swift"]) + "</div>")
    o.append('<div class="card"><h3>後ろから組み立てる</h3>'
             + '<div class="chain">' + btn("rye") + '<span class="to">→</span>' + btn("try") + "</div>"
             + '<div class="chain">' + btn("loo") + '<span class="to">→</span>' + btn("blue") + "</div>"
             + '<div class="chain">' + btn("wick") + '<span class="to">→</span>' + btn("quick") + "</div>"
             + '<div class="chain">' + btn("eat") + '<span class="to">→</span>' + btn("treat") + '<span class="to">→</span>' + btn("street") + "</div>"
             + '<p class="sub">完成した形も1音節のまま。指で数えて確かめる。</p></div>')
    o.append('<div class="card"><h3>2つ目の子音を消すと、別の語になる</h3>'
             '<p class="sub"><b>どっち？</b> を押すと2語のどちらかが流れます。聞こえた方をタップ。</p>'
             + "".join(pair(a, b) for a, b in ONSET) + "</div>")
    o.append('<div class="point"><b>ポイント</b>母音を足す（トゥライ）のも、接近音を消す（tie）のも誤り。別々に確かめる。</div></section>')

    o.append('<section id="coda"><h2><span class="no">2</span>語末の子音連続</h2>')
    o.append('<p class="lead">最後の子音まで言い終えたら止める。母音を付け足さない。</p>')
    o.append('<div class="card"><h3>2子音で終わる語</h3>' + row(["desk", "jump", "milk", "act", "help"])
             + '<h3>1子音で終わる語も</h3>' + row(["bag", "dog", "cat", "big"]) + "</div>")
    o.append('<div class="card"><h3>語尾の子音が、数や時制を伝える</h3>'
             '<p class="sub">-s（複数）や -ed（過去）を落とすと、文法の情報も消える。</p>'
             + "".join(pair(a, b) for a, b in CODA) + "</div>")
    o.append('<div class="card"><h3>子音字・子音・音節の数は別</h3>' + row(["texts", "sixths", "strengths", "glimpsed"])
             + '<table class="t"><tr><th></th><th>子音</th><th>音節</th></tr>'
             '<tr><td>texts</td><td>/t k s t s/ 5</td><td>1</td></tr><tr><td>sixths</td><td>/s k s θ s/ 5</td><td>1</td></tr>'
             '<tr><td>strengths</td><td>/s t r ŋ (k) θ s/ 6〜7</td><td>1</td></tr><tr><td>glimpsed</td><td>/ɡ l m p s t/ 6</td><td>1</td></tr></table></div>')
    o.append('<div class="point"><b>ポイント</b>子音が多くても [ə] を足して音節を増やさない。</div></section>')

    o.append('<section id="syl"><h2><span class="no">3</span>音節を数える</h2>')
    o.append('<div class="card"><h3>-ed は音節を増やす？</h3><p class="lab">1音節のまま</p>' + row(["pushed", "asked", "walked", "watched", "helped"])
             + '<p class="lab">2音節になる（t・d の後）</p>' + row(["treated", "started", "needed", "wanted"]) + "</div>")
    o.append('<div class="card"><h3>音節主音的な /n/：[n̩]</h3><p class="sub">t・d の閉鎖を保ったまま、息を鼻へ。母音をはさまない。</p>'
             + row(["button", "sudden", "seven", "lesson", "cotton", "written", "kitten", "hidden"]) + "</div>")
    o.append('<div class="card"><h3>音節主音的な /l/：[l̩]</h3><p class="sub">舌先の接触を保ち、側面から息。「ル」の母音を足さない。</p>'
             + row(["little", "middle", "bottle", "gentle", "title", "metal", "settle", "cattle", "apple"]) + "</div>")
    o.append('<div class="point"><b>ポイント</b>button・little の2音節目は、n や l が中心になる。</div>')
    o.append('<p class="notes">授業スライドの例文（Try and do it. など）の音声は、著作権の都合で授業中だけ再生します。</p></section>')
    return "\n".join(o)


EXTRA_CSS = """
h3{margin:0 0 8px;font-size:17px}
.lab{margin:10px 0 6px;font-size:14px;color:var(--sub);font-weight:600}
.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin-bottom:6px}
.row .w{min-height:58px;padding:6px 2px}.row .w .en{font-size:17px;white-space:nowrap}.row .w .en::before{font-size:11px}
.chain{display:flex;align-items:center;gap:6px;margin-bottom:8px}.chain .w{flex:1;min-height:58px}.chain .w .en{font-size:18px}
.to{font-size:20px;color:var(--sub);font-weight:700}
.sub{font-size:14px;color:var(--sub);margin:4px 0 10px}
table.t{width:100%;border-collapse:collapse;font-size:15px;margin-top:8px}table.t td,table.t th{border-top:1px solid var(--line);padding:6px 4px;text-align:left}
"""


def credits():
    rows = []
    for k in USED:
        f, lic, who = source(k)
        words = k[3:]
        page = "https://commons.wikimedia.org/wiki/File:" + f.replace(" ", "_")
        url = {"CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/deed.ja",
               "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/deed.ja",
               "CC0": "https://creativecommons.org/publicdomain/zero/1.0/deed.ja", "Public domain": ""}[lic]
        lic_html = f'<a href="{url}">{lic}</a>' if url else lic
        rows.append(f'<tr><td>{html.escape(words)}</td><td><a href="{html.escape(page)}">{html.escape(who)}</a></td><td>{lic_html}</td></tr>')
    return "\n".join(rows)


def test_items():
    its = []
    for a, b in ONSET:
        its.append({"kind": "pair", "sec": "語頭", "contrast": "2つ目の子音", "a": a, "b": b})
    for a, b in CODA:
        its.append({"kind": "pair", "sec": "語尾", "contrast": "語尾の子音", "a": a, "b": b})
    for it in its:
        for s in ("a", "b"):
            k = key(it[s])
            assert k and k.startswith("us_"), it[s]
            it[s + "Src"] = f"audio/{k}.mp3"
            it[s + "Ja"] = MEAN[it[s]]
    for w, n in COUNT:
        k = key(w)
        assert k, w
        its.append({"kind": "count", "sec": "音節", "contrast": "音節の数", "word": w, "src": f"audio/{k}.mp3",
                    "opts": ["1音節", "2音節"], "ans": f"{n}音節"})
    for it in its:
        for s in ("aSrc", "bSrc", "src"):
            if s in it and it[s][len("audio/"):-4] not in USED:
                USED.append(it[s][len("audio/"):-4])
    return its


def build(PAGE, CSS, JS):
    USED.clear()
    b = body()
    its = test_items()
    d = os.path.join(WEB, "lecture04")
    ad = os.path.join(d, "audio")
    if os.path.isdir(ad):
        shutil.rmtree(ad)
    os.makedirs(ad)
    for k in USED:
        assert not k.startswith(("fk_", "ga_", "rp_")), k   # 公開不可の音声を載せない
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", os.path.join(L4, "audio", k + ".mp3"),
                        "-map_metadata", "-1", "-c:a", "copy", "-write_xing", "0", os.path.join(ad, k + ".mp3")], check=True)
    page = (PAGE.replace("英語音声学　第3回", "英語音声学　第4回").replace("子音を聞いて練習", "子音連続と音節を聞いて練習")
            .replace('<a href="#s31">3.1 語対</a><a href="#s32">3.2 文脈</a>', '<a href="#onset">語頭</a><a href="#coda">語末</a><a href="#syl">音節</a>')
            .replace("{body}", b).replace("{credits}", credits()).replace("{n}", str(len(USED)))
            .replace("{css}", CSS + EXTRA_CSS).replace("{js}", JS))
    assert "第4回" in page and "#onset" in page
    open(os.path.join(d, "index.html"), "w").write(page)
    intro = "流れた英単語はどちらか（2つ目の子音・語尾の子音）、また何音節に聞こえるかを選びます。"
    open(os.path.join(d, "test.html"), "w").write(test_page.render(its, TEST_ID, "第4回", "子音連続と音節のテスト", intro))
    print("lecture04:", len(USED), "files,", len(its), "test items")
