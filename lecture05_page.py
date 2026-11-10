"""第5回（語強勢）の「聞いて練習」ページと聞き取りテストを作る。build_web.py の main() から呼ぶ。

音声は ../lecture05/audio の公開ライセンス録音だけ（Commons の米音辞書形 us_、Lingua Libre の ll_hotdog）。
授業スライドの深澤（2015）の音声（fk_）は公開しないので、fk_ だけにある語（photographic など）は「録音なし」にした。
テストの名詞／動詞の対は、声の違いで当たらないよう同じ話者（Commons の Dvortygirl、En-us-<語>-noun／-verb）でそろえた。
present は名詞形の録音が無いので、強勢型が名詞と同じ形容詞（present-adjective）で代用した。
強勢位置は CEPD 第18版の GA 表記に合わせ、テストに使う録音は tools/voiced_chunks.py（lecture05）で強勢側が長く・高く・強いことを確かめた。
employee は emPLOYee と読む話者も多く、録音もどちらとも決めにくいので、テストには出さない。
"""
import html, json, os, re, shutil, subprocess

import test_page

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "web")
L5 = os.path.join(ROOT, "lecture05")
FOUND = json.load(open(os.path.join(L5, "_commons", "found.json")))
LL = json.load(open(os.path.join(L5, "_commons", "ll_ch5_found.json")))
TEST_ID = "l05-stress"

MEAN = {
    "forward": "前方へ", "police": "警察", "prefer": "より好む", "table": "テーブル", "people": "人々", "happy": "幸せな",
    "doctor": "医者", "music": "音楽", "open": "開いた", "sister": "姉妹", "winter": "冬", "believe": "信じる", "forget": "忘れる",
    "begin": "始める", "enjoy": "楽しむ", "alone": "ひとりで", "awake": "目が覚めて",
    "average": "平均", "generous": "気前のよい", "comfortable": "快適な", "contribute": "貢献する", "important": "重要な",
    "recommend": "勧める", "introduce": "紹介する",
    "photograph": "写真", "photography": "写真術", "photographic": "写真の", "economy": "経済", "economic": "経済の",
    "nation": "国家", "national": "国の", "nationality": "国籍", "intellect": "知性", "intellectual": "知的な",
    "intelligence": "知能", "person": "人", "personification": "擬人化", "political": "政治の", "politician": "政治家",
    "benefit": "利益", "beneficent": "慈善心に富む",
    "employee": "従業員", "engineer": "技師", "electricity": "電気", "happiness": "幸福", "careless": "不注意な",
    "helpful": "役立つ", "slowly": "ゆっくり",
    "goldfish": "金魚", "newspaper": "新聞", "blackbird": "クロウタドリ", "hotdog": "ホットドッグ",
    "thirteen": "13", "afternoon": "午後", "Japanese": "日本の",
}
# 表示形：大文字＝主強勢のある音節（教科書・スライドの表示）
SHOW = {
    "forward": "FORward", "police": "poLICE", "prefer": "preFER", "table": "TAble", "people": "PEOple", "happy": "HAPpy",
    "doctor": "DOCtor", "music": "MUSic", "open": "OPen", "sister": "SISter", "winter": "WINter", "believe": "beLIEVE",
    "forget": "forGET", "begin": "beGIN", "enjoy": "enJOY", "alone": "aLONE", "awake": "aWAKE",
    "average": "AVerage", "generous": "GENerous", "comfortable": "COMfortable", "contribute": "conTRIBute",
    "important": "imPORtant", "recommend": "recomMEND", "introduce": "introDUCE",
    "photograph": "PHOtograph", "photography": "phoTOGraphy", "photographic": "photoGRAPHic", "economy": "eCONomy",
    "economic": "ecoNOMic", "nation": "NAtion", "national": "NAtional", "nationality": "natioNALity",
    "intellect": "INtellect", "intellectual": "intelLECtual", "intelligence": "inTELligence", "person": "PERson",
    "personification": "personifiCAtion", "political": "poLITical", "politician": "poliTIcian",
    "benefit": "BENefit", "beneficent": "beNEFicent",
    "employee": "employEE", "engineer": "engiNEER", "electricity": "elecTRICity", "happiness": "HAPpiness",
    "careless": "CAREless", "helpful": "HELPful", "slowly": "SLOWly",
    "goldfish": "GOLDfish", "newspaper": "NEWSpaper", "blackbird": "BLACKbird", "hotdog": "HOTdog",
    "thirteen": "thirTEEN", "afternoon": "afterNOON", "Japanese": "JapaNESE",
}


def key(w):
    for p in ("us_", "ll_"):
        k = p + w
        if os.path.exists(os.path.join(L5, "audio", k + ".mp3")):
            return k
    return None


def source(k):
    if k.startswith("us_"):
        f = f"En-us-{k[3:]}.ogg"
        v = FOUND["File:" + f]
    else:
        title = {"ll_hotdog": "File:LL-Q1860 (eng)-Wodencafe-hot dog.wav"}[k]
        v = LL[title]
        f = title[len("File:"):]
    artist = re.sub(r"<[^>]+>", "", v["artist"])
    artist = re.sub(r"No machine-readable author provided\. (\S+) assumed.*", r"\1", artist).split("\n")[0]
    return f, v["lic"], artist.replace("Speaker: ", "").strip() or "（記載なし）"


USED = []


def btn(w, label=None, ja=None, k=None):
    k = k or key(w)
    en = html.escape(label or SHOW.get(w, w))
    ja = html.escape(MEAN.get(w, "") if ja is None else ja)
    if not k:
        return f'<button class="w off" disabled><span class="en">{en}</span><span class="ja">{ja}</span><span class="na">録音なし</span></button>'
    if k not in USED:
        USED.append(k)
    return f'<button class="w" data-a="audio/{k}.mp3"><span class="en">{en}</span><span class="ja">{ja}</span></button>'


def row(words, cls="row"):
    return f'<div class="{cls}">' + "".join(btn(w) for w in words) + "</div>"


# 名詞／動詞の対：(語, 名詞の表示, 名詞の意味, 名詞の録音, 動詞の表示, 動詞の意味, 動詞の録音)。すべて Dvortygirl
NV = [("record", "REcord", "記録", "us_record-noun", "reCORD", "記録する", "us_record-verb"),
      ("present", "PREsent", "出席して（形容詞）", "us_present-adjective", "preSENT", "贈る", "us_present-verb1"),
      ("permit", "PERmit", "許可証", "us_permit-noun", "perMIT", "許可する", "us_permit-verb"),
      ("object", "OBject", "物体", "us_object-noun", "obJECT", "反対する", "us_object-verb"),
      ("protest", "PROtest", "抗議", "us_protest-noun", "proTEST", "抗議する", "us_protest-verb"),
      ("subject", "SUBject", "主題", "us_subject-noun", "subJECT", "従わせる", "us_subject-verb"),
      ("increase", "INcrease", "増加", "us_increase-noun", "inCREASE", "増える", "us_increase-verb")]


def nv_pair(p):
    w, nl, nj, nk, vl, vj, vk = p
    q = (f'<button class="q" data-pair="audio/{nk}.mp3|audio/{vk}.mp3" data-words="{nl}（名詞）|{vl}（動詞）" '
         f'aria-label="{nl} か {vl} のどちらかが流れる">どっち？</button>')
    return (f'<div class="pair">{btn(w, nl, "名詞：" + nj, nk)}{btn(w, vl, "動詞：" + vj, vk)}{q}</div>'
            '<p class="res" aria-live="polite"></p>')


def fam(title, words, note=""):
    o = f'<div class="fam"><p class="lab">{html.escape(title)}</p>' + row(words, "row wide")
    return o + (f'<p class="sub">{html.escape(note)}</p>' if note else "") + "</div>"


def body():
    o = []
    o.append('<section id="two"><h2><span class="no">1</span>二音節語の強勢位置</h2>')
    o.append('<p class="lead">語をタップすると音声が流れます。<b>大文字</b>が強勢のある音節。'
             '強勢のある音節は、長く・はっきり・高さの変化をともなって聞こえます。</p>')
    o.append('<div class="card"><h3>第1音節が強い（名詞に多い）</h3>'
             + row(["table", "people", "happy", "doctor", "music", "open", "sister", "winter", "forward"])
             + '<h3 class="mt">第2音節が強い（動詞・形容詞に多い）</h3>'
             + row(["police", "prefer", "believe", "forget", "begin", "enjoy", "alone", "awake"]) + "</div>")
    o.append('<div class="card"><h3>三音節以上の語</h3><p class="lab">第1音節</p>' + row(["average", "generous", "comfortable"])
             + '<p class="lab">第2音節</p>' + row(["contribute", "important"])
             + '<p class="lab">第3音節（第1音節に弱い強勢）</p>' + row(["recommend", "introduce"])
             + '<p class="sub">強勢のない音節は短く、母音があいまいな [ə] になりやすい。</p></div>')
    o.append('<div class="point"><b>ポイント</b>つづりの長さでは決まらない。辞書の強勢記号と音声で確かめる。</div></section>')

    o.append('<section id="nv"><h2><span class="no">2</span>名詞と動詞で強勢が変わる語</h2>')
    o.append('<p class="lead">つづりは同じでも、名詞は前、動詞は後ろが強い。<b>どっち？</b> を押すと名詞・動詞のどちらかが流れるので、聞こえた方をタップしてください。</p>')
    o.append('<div class="card">' + "".join(nv_pair(p) for p in NV) + "</div>")
    o.append('<ul class="notes"><li>7対とも同じ話者の録音。present は名詞の録音が無いので、強勢型が同じ形容詞（出席して）を使った</li>'
             '<li>強勢が動くと母音も変わる：REcord /ˈrek.ə˞d/ と reCORD /rɪˈkɔːrd/ では re の母音が違う</li></ul>')
    o.append('<div class="point"><b>ポイント</b>強勢の位置が品詞を示す。母音の質と長さも一緒に変わる。</div></section>')

    o.append('<section id="fam"><h2><span class="no">3</span>語族：同じ語根でも強勢が動く</h2>')
    o.append('<p class="lead">接尾辞が付くと、主強勢の位置が移ることがあります。縦に並べて聞き比べましょう。</p>')
    o.append('<div class="card">'
             + fam("photograph の語族", ["photograph", "photography", "photographic"], "photographic は授業中だけ再生（公開できる録音が無い）")
             + fam("economy の語族", ["economy", "economic"], "economic は別の話者")
             + fam("nation の語族", ["nation", "national", "nationality"], "nationality は別の話者")
             + fam("intellect の語族", ["intellect", "intellectual", "intelligence"])
             + fam("politics の語族", ["political", "politician"], "politician は別の話者")
             + fam("person・benefit の語族", ["person", "personification", "benefit", "beneficent"], "personification・beneficent は別の話者")
             + "</div>")
    o.append('<div class="point"><b>ポイント</b>強勢が移ると、強勢を失った音節の母音は [ə] などに弱まる。</div></section>')

    o.append('<section id="aff"><h2><span class="no">4</span>接辞から強勢を予測する</h2>')
    o.append('<div class="card"><p class="lab">-ee・-eer：接尾辞そのものが強い</p>' + row(["employee", "engineer"])
             + '<p class="lab">-ic・-ity：直前の音節が強い</p>' + row(["economic", "electricity", "photographic"])
             + '<p class="lab">-ness・-less・-ful・-ly：語幹の強勢をそのまま保つ</p>' + row(["happiness", "careless", "helpful", "slowly"])
             + '<p class="sub">employee は emPLOYee と読む人も多い。接辞は強勢の有力な手がかりだが、最後は辞書で確かめる。</p></div>')
    o.append('<div class="card"><h3>複合語は前が強い</h3>' + row(["goldfish", "newspaper", "blackbird", "hotdog"])
             + '<p class="sub">GOLDfish（金魚）と gold FISH（金色の魚）のように、句は後ろの語が強い。</p>'
             + '<h3 class="mt">文の中で強勢が前へ移る語</h3>' + row(["thirteen", "afternoon", "Japanese"])
             + '<p class="sub">単独では後ろが強いが、THIRteen MEN・JAPanese FOOD のように後ろに強い語が続くと、前へ移ることがある。</p></div>')
    o.append('<div class="point"><b>ポイント</b>接辞で候補を絞り、辞書と音声で確かめる。</div>')
    o.append('<p class="notes">授業スライドの例（深澤 2015 の語・二語表現・文）の音声は、著作権の都合で授業中だけ再生します。</p></section>')
    return "\n".join(o)


EXTRA_CSS = """
h3{margin:0 0 8px;font-size:17px}h3.mt{margin-top:14px}
.lab{margin:10px 0 6px;font-size:14px;color:var(--sub);font-weight:600}
.row{display:grid;grid-template-columns:repeat(auto-fill,minmax(100px,1fr));gap:8px;margin-bottom:6px}
.row.wide{grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
.row .w{min-height:58px;padding:6px 2px}.row .w .en{font-size:17px;white-space:nowrap}.row .w .en::before{font-size:11px}
.fam{border-top:1px solid var(--line);padding-top:4px;margin-top:6px}.fam:first-child{border-top:0;margin-top:0;padding-top:0}
.fam .sub{margin:0 0 6px;font-size:13px}
.sub{font-size:14px;color:var(--sub);margin:4px 0 10px}
.pair .w .en{font-size:19px}.pair .w .ja{font-size:12px}
nav{gap:6px;overflow-x:auto;padding:8px 12px}nav a{flex:1 0 auto;padding:8px 10px;font-size:14px}
"""

LIC_URL = {"CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/deed.ja",
           "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/deed.ja",
           "CC0": "https://creativecommons.org/publicdomain/zero/1.0/deed.ja", "Public domain": ""}


def credits():
    rows = []
    for k in USED:
        f, lic, who = source(k)
        words = k[3:]
        page = "https://commons.wikimedia.org/wiki/File:" + f.replace(" ", "_")
        url = LIC_URL[lic]
        lic_html = f'<a href="{url}">{lic}</a>' if url else lic
        rows.append(f'<tr><td>{html.escape(words)}</td><td><a href="{html.escape(page)}">{html.escape(who)}</a></td><td>{lic_html}</td></tr>')
    return "\n".join(rows)


# テスト：(語, 音節の区切り, 強い音節の番号 0 始まり)。区切りは辞書の分綴に近いつづりの区切り
TWO = [("table", "ta|ble", 0), ("people", "peo|ple", 0), ("happy", "hap|py", 0), ("doctor", "doc|tor", 0),
       ("sister", "sis|ter", 0), ("forward", "for|ward", 0), ("police", "po|lice", 1), ("prefer", "pre|fer", 1),
       ("believe", "be|lieve", 1), ("forget", "for|get", 1), ("begin", "be|gin", 1), ("enjoy", "en|joy", 1)]
MANY = [("average", "av|er|age", 0), ("generous", "gen|er|ous", 0), ("comfortable", "com|for|ta|ble", 0),
        ("photograph", "pho|to|graph", 0), ("happiness", "hap|pi|ness", 0), ("contribute", "con|trib|ute", 1),
        ("important", "im|por|tant", 1), ("economy", "e|con|o|my", 1), ("photography", "pho|tog|ra|phy", 1),
        ("recommend", "rec|om|mend", 2), ("engineer", "en|gi|neer", 2), ("nationality", "na|tion|al|i|ty", 2)]
ORD = "①②③④⑤"


def test_items():
    its = []
    for sec, lst in (("2音節", TWO), ("3音節以上", MANY)):
        for w, syl, n in lst:
            k = key(w)
            assert k and k.startswith("us_"), w
            parts = syl.split("|")
            assert "".join(parts) == w and len(set(parts)) == len(parts) and SHOW[w].lower() == w.lower(), w
            its.append({"kind": "pick", "sec": sec, "contrast": "強い音節", "word": w, "src": f"audio/{k}.mp3",
                        "ask": "いちばん強いのはどの音節？", "opts": parts,
                        "optJa": [f"第{i + 1}音節" for i in range(len(parts))], "ans": parts[n]})
    for w, nl, nj, nk, vl, vj, vk in NV:
        assert FOUND[f"File:En-us-{nk[3:]}.ogg"]["artist"] == FOUND[f"File:En-us-{vk[3:]}.ogg"]["artist"], w   # 同じ話者
        its.append({"kind": "pair", "sec": "名詞と動詞", "contrast": "強勢の位置", "a": nl, "b": vl,
                    "aSrc": f"audio/{nk}.mp3", "bSrc": f"audio/{vk}.mp3", "aJa": "名詞：" + nj, "bJa": "動詞：" + vj})
    for it in its:
        for s in ("aSrc", "bSrc", "src"):
            if s in it and it[s][len("audio/"):-4] not in USED:
                USED.append(it[s][len("audio/"):-4])
    return its


def build(PAGE, CSS, JS):
    USED.clear()
    b = body()
    its = test_items()
    d = os.path.join(WEB, "lecture05")
    ad = os.path.join(d, "audio")
    if os.path.isdir(ad):
        shutil.rmtree(ad)
    os.makedirs(ad)
    for k in USED:
        assert k.startswith(("us_", "ll_")) and not k.startswith(("fk_", "ga_", "rp_")), k   # 公開不可の音声を載せない
        subprocess.run(["ffmpeg", "-nostdin", "-loglevel", "error", "-y", "-i", os.path.join(L5, "audio", k + ".mp3"),
                        "-map_metadata", "-1", "-c:a", "copy", "-write_xing", "0", os.path.join(ad, k + ".mp3")], check=True)
    page = (PAGE.replace("英語音声学　第3回", "英語音声学　第5回").replace("子音を聞いて練習", "語強勢を聞いて練習")
            .replace('<a href="#s31">3.1 語対</a><a href="#s32">3.2 文脈</a>',
                     '<a href="#two">2音節</a><a href="#nv">品詞</a><a href="#fam">語族</a><a href="#aff">接辞</a>')
            .replace("{body}", b).replace("{credits}", credits()).replace("{n}", str(len(USED)))
            .replace("{css}", CSS + EXTRA_CSS).replace("{js}", JS))
    assert "第5回" in page and "#nv" in page and "fk_" not in page
    open(os.path.join(d, "index.html"), "w").write(page)
    intro = "流れた英単語で、いちばん強いのはどの音節か（二音節語・三音節以上の語）、また名詞と動詞のどちらの読み方かを選びます。"
    t = test_page.render(its, TEST_ID, "第5回", "語強勢の聞き取りテスト", intro)
    assert "fk_" not in t
    open(os.path.join(d, "test.html"), "w").write(t)
    print("lecture05:", len(USED), "files,", len(its), "test items")
