"""第6回（文の卓立とリズム）の「聞いて練習」ページと聞き取りテストを作る。build_web.py の main() から呼ぶ。

音声は ../lecture06/audio の公開ライセンス録音だけ：
  Commons の米音辞書形 us_（語・短い句。句は En-us-piece of cake.ogg など。大半が Dvortygirl）、
  Lingua Libre の ll_and・ll_to（Grendelkhan, CC0）、ja_sakura（Higa4, CC0）・ja_tokyo（Fukujinzuke, CC BY 4.0）。
授業スライドの文の録音（深澤 2015、fk_）は公開しない。Commons・Lingua Libre には教科書の例文（Give it to him など）の録音が無いので、
このページは「文」ではなく「短い句・語・機能語の単独形」の練習で組んだ（第6章 1.1・2.1・2.4・2.5・2.3 に対応）。
句の強弱は lecture06/tools/word_prosody.py（語ごとの長さ・F0）で確かめ、弱い語がはっきりしない句（how are you・I don't know・I love you）はテストに出さない。
テストは対（pair）の問題を作らず、1つの録音ごとの選択問題（pick）にした。語の強弱型の8語はすべて同じ話者（Dvortygirl）。
"""
import html, json, os, re, shutil, subprocess

import test_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
L6 = os.path.join(ROOT, "lecture06")
FOUND = json.load(open(os.path.join(L6, "_commons", "found.json")))
FOUND.update(json.load(open(os.path.join(L6, "_commons", "phrases_found.json"))))
LLQ = {p["title"]: p for p in json.load(open(os.path.join(L6, "_commons", "ll_query.json")))["query"]["pages"].values() if "imageinfo" in p}
LLKEY = {"ll_and": "File:LL-Q1860 (eng)-Grendelkhan-and.wav", "ll_to": "File:LL-Q1860 (eng)-Grendelkhan-to.wav",
         "ja_sakura": "File:LL-Q5287 (jpn)-Higa4-さくら.wav", "ja_tokyo": "File:LL-Q5287 (jpn)-Fukujinzuke-とうきょう.wav"}
TEST_ID = "l06-rhythm"

# 句：(音声キー, 表示〔大文字＝強く〕, 意味)
PH = {
    "piece_of_cake": ("PIECE of CAKE", "朝飯前"), "now_and_then": ("NOW and THEN", "ときどき"), "and_so_on": ("and SO ON", "など"),
    "at_least": ("at LEAST", "少なくとも"), "of_course": ("of COURSE", "もちろん"), "on_the_other_hand": ("on the OTHer HAND", "一方で"),
    "have_to": ("HAVE to", "〜しなければならない"), "how_are_you": ("HOW are YOU?", "元気？"), "I_dont_know": ("I DON'T KNOW", "わからない"),
    "I_love_you": ("I LOVE you", "愛してる"), "good_morning": ("good MORNing", "おはよう"), "good_afternoon": ("good afterNOON", "こんにちは"),
    "good_night": ("good NIGHT", "おやすみ"), "good_luck": ("good LUCK", "がんばって"),
}
MEAN = {"mother": "母", "teacher": "先生", "happy": "幸せな", "candle": "ろうそく", "around": "周りに", "believe": "信じる",
        "enjoy": "楽しむ", "today": "今日", "camera": "カメラ", "musician": "音楽家", "and": "〜と", "to": "〜へ"}
SHOW = {"mother": "MOther", "teacher": "TEAcher", "happy": "HAPpy", "candle": "CANdle", "around": "aROUND", "believe": "beLIEVE",
        "enjoy": "enJOY", "today": "toDAY", "camera": "CAMera", "musician": "muSIcian"}


def path(k):
    return os.path.join(L6, "audio", k + ".mp3")


def source(k):
    if k in LLKEY:
        t = LLKEY[k]; md = LLQ[t]["imageinfo"][0]["extmetadata"]
        lic = md.get("LicenseShortName", {}).get("value", "")
        who = t.split(")-")[1].rsplit("-", 1)[0]   # LL-Q1860 (eng)-<話者>-<語>.wav
        return t[len("File:"):], lic, who
    t = "File:En-us-" + {v.replace(" ", "_").replace("'", ""): v for v in
                         [x[len("File:En-us-"):-4] for x in FOUND]}[k[3:]] + ".ogg"
    v = FOUND[t]
    artist = re.sub(r"<[^>]+>", "", v["artist"])
    artist = re.sub(r"No machine-readable author provided\. (\S+) assumed.*", r"\1", artist).split("\n")[0]
    return t[len("File:"):], v["lic"], artist.strip() or "（記載なし）"


USED = []


def use(k):
    assert os.path.exists(path(k)), k
    if k not in USED:
        USED.append(k)


def btn(k, en, ja, cls="w"):
    use(k)
    return f'<button class="{cls}" data-a="audio/{k}.mp3"><span class="en">{html.escape(en)}</span><span class="ja">{html.escape(ja)}</span></button>'


def word(w):
    return btn("us_" + w, SHOW.get(w, w), MEAN.get(w, ""))


def phrase(p):
    return btn("us_" + p, PH[p][0], PH[p][1])


def row(items, cls="row"):
    return f'<div class="{cls}">' + "".join(items) + "</div>"


def body():
    o = []
    o.append('<section id="ph"><h2><span class="no">1</span>短い句の強弱</h2>')
    o.append('<p class="lead">句をタップすると音声が流れます。<b>大文字</b>が強く読まれる語、小文字が弱く読まれる語です。'
             '弱い語（of・and・at・to など）は短く、あいまいな母音 [ə] になりやすい。</p>')
    o.append('<div class="card"><h3>機能語が1つ入った句</h3>' + row([phrase(p) for p in ["piece_of_cake", "now_and_then", "and_so_on", "at_least", "of_course", "have_to"]], "row wide")
             + '<h3 class="mt">内容語が2つ以上ある句</h3>' + row([phrase(p) for p in ["on_the_other_hand", "how_are_you", "I_dont_know", "I_love_you"]], "row wide")
             + '<h3 class="mt">あいさつ：後ろの語が強い</h3>' + row([phrase(p) for p in ["good_morning", "good_afternoon", "good_night", "good_luck"]], "row wide")
             + '<p class="sub">大文字はこの録音でのふつうの読み方。how are you は HOW are YOU とも how ARE you とも言う。</p></div>')
    o.append('<div class="point"><b>ポイント</b>内容語が柱、機能語は軽く短く。全部の語を同じ強さで読まない。</div></section>')

    o.append('<section id="fw"><h2><span class="no">2</span>機能語：単独と句の中</h2>')
    o.append('<p class="lead">単独で読むと強い形（強形）、句の中では弱い形（弱形）になります。左右を聞き比べましょう。</p>')
    o.append('<div class="card"><p class="lab">and：単独 /ænd/ → 句の中 [ən]・[n]</p>'
             + row([btn("ll_and", "and（単独）", "〜と"), phrase("now_and_then"), phrase("and_so_on")], "row wide")
             + '<p class="lab">to：単独 /tuː/ → 句の中 [tə]</p>' + row([btn("ll_to", "to（単独）", "〜へ"), phrase("have_to")], "row wide")
             + '<p class="lab">of：句の中 [əv]</p>' + row([phrase("piece_of_cake"), phrase("of_course")], "row wide")
             + '<p class="sub">単独の and・to は別の話者（Lingua Libre）。弱形のしくみは第7章で。</p></div>')
    o.append('<div class="point"><b>ポイント</b>機能語は、ふつうは弱形。対比・訂正のときだけ強形になる。</div></section>')

    o.append('<section id="ft"><h2><span class="no">3</span>語の強弱型：●・ と ・●</h2>')
    o.append('<p class="lead">英語の語は「強い音節＋弱い音節」の型がとても多い。強い音節で手をたたいてみましょう。</p>')
    o.append('<div class="card"><h3>強弱型 ●・</h3>' + row([word(w) for w in ["mother", "teacher", "happy", "candle"]])
             + '<h3 class="mt">弱強の並び ・●</h3>' + row([word(w) for w in ["around", "believe", "enjoy", "today"]])
             + '<p class="sub">8語とも同じ話者。文の中のリズムの単位（フット）は、語の切れ目と一致するとは限らない。</p></div>')
    o.append('<div class="point"><b>ポイント</b>強い音節を柱にして、弱い音節は軽く短く。</div></section>')

    o.append('<section id="wk"><h2><span class="no">4</span>弱い音節の脱落・日本語のモーラ</h2>')
    o.append('<div class="card"><p class="lab">camera：辞書 /ˈkæm.ər.ə/ → [ˈkæm.rə]</p>' + row([word("camera"), word("musician")])
             + '<p class="sub">この camera の録音は、m のすぐあとに r が続く2音節（間に母音がない）。</p>'
             + '<p class="lab">日本語はモーラ（拍）で刻む</p>'
             + row([btn("ja_sakura", "さくら", "さ・く・ら（3拍）"), btn("ja_tokyo", "とうきょう", "と・う・きょ・う（4拍）")])
             + '<p class="sub">英語は強い音節の山、日本語はモーラの刻みが目立つ。どちらも「傾向」で、厳密に等間隔ではない。</p></div>')
    o.append('<div class="point"><b>ポイント</b>英語の弱い音節は短くなり、母音が弱まったり消えたりする。</div>')
    o.append('<p class="notes">授業スライドの文の例（Give it to him・Come to tea with John … など、深澤 2015 の音声）は、著作権の都合で授業中だけ再生します。'
             '公開ライセンスの文の録音が見つからなかったので、このページは句と語で練習します。</p></section>')
    return "\n".join(o)


EXTRA_CSS = """
h3{margin:0 0 8px;font-size:17px}h3.mt{margin-top:14px}
.lab{margin:10px 0 6px;font-size:14px;color:var(--sub);font-weight:600}
.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin-bottom:6px}
.row.wide{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
.row .w{min-height:58px;padding:6px 2px}.row .w .en{font-size:17px;white-space:nowrap}.row .w .en::before{font-size:11px}
.row.wide .w .en{white-space:normal;font-size:16px;line-height:1.2}
.sub{font-size:14px;color:var(--sub);margin:4px 0 10px}
nav{gap:6px;overflow-x:auto;padding:8px 12px}nav a{flex:1 0 auto;padding:8px 10px;font-size:14px}
"""

LIC_URL = {"CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/deed.ja",
           "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/deed.ja",
           "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/deed.ja",
           "CC0": "https://creativecommons.org/publicdomain/zero/1.0/deed.ja", "Public domain": ""}


def credits():
    rows = []
    for k in USED:
        f, lic, who = source(k)
        assert lic in LIC_URL, (k, lic)
        label = PH[k[3:]][0].lower() if k[3:] in PH else {"ll_and": "and", "ll_to": "to", "ja_sakura": "さくら", "ja_tokyo": "とうきょう"}.get(k, k[3:])
        page = "https://commons.wikimedia.org/wiki/File:" + f.replace(" ", "_")
        url = LIC_URL[lic]
        lic_html = f'<a href="{url}">{lic}</a>' if url else lic
        rows.append(f'<tr><td>{html.escape(label)}</td><td><a href="{html.escape(page)}">{html.escape(who)}</a></td><td>{lic_html}</td></tr>')
    return "\n".join(rows)


# テスト
WEAK = [("piece_of_cake", "of"), ("now_and_then", "and"), ("and_so_on", "and"), ("at_least", "at"), ("of_course", "of"), ("have_to", "to")]
STRONG = [("on_the_other_hand", "hand")]
FOOT = [("mother", 0), ("teacher", 0), ("happy", 0), ("candle", 0), ("around", 1), ("believe", 1), ("enjoy", 1), ("today", 1)]
OPT_FOOT = ["●・", "・●"]


def test_items():
    its = []
    for w, n in FOOT:
        k = "us_" + w; use(k)
        assert "Dvortygirl" in FOUND[f"File:En-us-{w}.ogg"]["artist"], w   # 8語とも同じ話者
        its.append({"kind": "pick", "sec": "語の強弱型", "contrast": "強弱の型", "word": w, "src": f"audio/{k}.mp3",
                    "ask": "強弱型（●・）？ 弱強の並び（・●）？", "opts": OPT_FOOT, "optJa": ["前が強い", "後ろが強い"], "ans": OPT_FOOT[n]})
    for p, ans in WEAK:
        k = "us_" + p; use(k)
        words = [x for x in p.split("_")]
        assert ans in words, p
        its.append({"kind": "pick", "sec": "句の中の弱い語", "contrast": "弱い語", "word": " ".join(words), "src": f"audio/{k}.mp3",
                    "ask": "弱く読まれている語はどれ？", "opts": words, "optJa": ["" for _ in words], "ans": ans})
    for p, ans in STRONG:
        k = "us_" + p; use(k)
        words = p.split("_")
        its.append({"kind": "pick", "sec": "句の中の強い語", "contrast": "いちばん強い語", "word": " ".join(words), "src": f"audio/{k}.mp3",
                    "ask": "いちばん強く読まれている語はどれ？", "opts": words, "optJa": ["" for _ in words], "ans": ans})
    for k, w, n in [("ja_sakura", "さくら", "3"), ("ja_tokyo", "とうきょう", "4")]:
        use(k)
        its.append({"kind": "pick", "sec": "日本語のモーラ", "contrast": "拍の数", "word": w, "src": f"audio/{k}.mp3",
                    "ask": "日本語で何拍？", "opts": ["2", "3", "4", "5"], "optJa": ["拍"] * 4, "ans": n})
    return its


def build(PAGE, CSS, JS):
    USED.clear()
    b = body()
    its = test_items()
    d = os.path.join(WEB, "lecture06")
    ad = os.path.join(d, "audio")
    if os.path.isdir(ad):
        shutil.rmtree(ad)
    os.makedirs(ad)
    for k in USED:
        assert k.startswith(("us_", "ll_", "ja_")) and not k.startswith(("fk_", "ga_", "rp_")), k   # 公開不可の音声を載せない
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", path(k),
                        "-map_metadata", "-1", "-c:a", "copy", "-write_xing", "0", os.path.join(ad, k + ".mp3")], check=True)
    page = (PAGE.replace("英語音声学　第3回", "英語音声学　第6回").replace("子音を聞いて練習", "文の卓立とリズムを聞いて練習")
            .replace('<a href="#s31">3.1 語対</a><a href="#s32">3.2 文脈</a>',
                     '<a href="#ph">句の強弱</a><a href="#fw">機能語</a><a href="#ft">強弱型</a><a href="#wk">脱落・モーラ</a>')
            .replace("{body}", b).replace("{credits}", credits()).replace("{n}", str(len(USED)))
            .replace("{css}", CSS + EXTRA_CSS).replace("{js}", JS))
    assert "第6回" in page and "#ft" in page and "fk_" not in page
    open(os.path.join(d, "index.html"), "w").write(page)
    intro = "流れた語・句を聞いて、強弱の型（●・か・●か）、句の中で弱く（または強く）読まれている語、日本語の拍の数を選びます。"
    t = test_page.render(its, TEST_ID, "第6回", "文の卓立とリズムの聞き取りテスト", intro)
    assert "fk_" not in t
    open(os.path.join(d, "test.html"), "w").write(t)
    print("lecture06:", len(USED), "files,", len(its), "test items")
