"""「話して練習」（lectureNN/speak.html）と「発音テスト」（lectureNN/record.html）を作る。build_web.py の main() から呼ぶ。

項目は教科書（~/Projects/books/english-phonetics/dist/英語音声学_改訂用.md）各章の「3. 発音練習」と付録E から取った。
  練習：お手本は各回の聞いて練習ページと同じ公開ライセンス録音（web/lectureNN/audio にあるものだけ）。録音の無い文はお手本なしで、
        強く読む部分の印（*…*）と「ここを意識」だけを出す。合成音声は使わない。
  練習の「お手本のあとに言う」：お手本が終わると自動で録音が始まり、言い終わると止まって自分の声が流れる。何回でも録り直せる。
  課題（練習ページの中）：TASK の項目は、納得した録音で「この録音に決定」→ 全部決めたら「提出する」。testId は lNN-task。
  テスト：お手本は流さず、綴りだけを出す（第5回の強勢・第6回の焦点を印で教えない）。録音するとその場で自動送信して次の問題へ（testId は lNN-speak）。
  見る点（check）は採点用に受付側へ送る。
評価は教科書 付録G.6 の 0（まだ難しい）・1（意識すればできる）・2（課題内で安定）。練習の自己評価と先生の採点で同じ尺度を使う。
部品：web/speak/core.js（録音・分析・描画）、practice.js、record.js、speak.css。受付は web/gas/Code.gs（rec-upload / rec-finish）。
"""
import hashlib, html, json, os, re

WEB = os.path.dirname(os.path.abspath(__file__))

LIC_URL = {"CC BY-SA 3.0": "https://creativecommons.org/licenses/by-sa/3.0/deed.ja",
           "CC BY-SA 4.0": "https://creativecommons.org/licenses/by-sa/4.0/deed.ja",
           "CC BY 4.0": "https://creativecommons.org/licenses/by/4.0/deed.ja",
           "CC0": "https://creativecommons.org/publicdomain/zero/1.0/deed.ja", "Public domain": ""}

AREA = {3: "重要な音素対立を保つ", 4: "母音挿入を必要に応じて抑える", 5: "語強勢と弱音節を対照させる",
        6: "文の卓立とリズム", "focus": "文脈に合う核を置く"}


def P(text, check, model=None, note="", ctx="", sec=None):
    """練習の1項目。text の *…* は強く読む部分・注目する文字（太字で出す）。model は音声キー（us_think など）"""
    return {"text": text, "check": check, "model": model, "note": note, "ctx": ctx, "maxSec": sec}


def T(text, check, note="", ctx="", sec=None, area=None):
    """テストの1問。text は綴りだけ（印を付けない）"""
    return {"text": text, "check": check, "note": note, "ctx": ctx, "maxSec": sec, "area": area}


PAIR = "2語を左から順に、間を少しあけて読む"

# ---------------------------------------------------------------- 第3回 子音
L3 = {
    "lecture": "第3回", "topic": "子音", "view": "spec",
    "sections": [
        ("/θ/–/s/", "think と sink のような語対を、お手本と同じ順に録音します。声紋（スペクトログラム）で摩擦の強さと高さを見比べましょう。", [
            P("*th*ink", "舌先を上の前歯の先に軽く当て、すき間から息を出す [θ]。声紋では [s] ほど濃い雑音が出ない", "us_think", "/θɪŋk/"),
            P("*s*ink", "舌先を上の歯ぐきに近づける [s]。声紋では高いところ（4,000 Hz より上）に濃いざらざら", "us_sink", "/sɪŋk/"),
            P("fai*th*", "語末の th も [s] にしない。最後の弱い摩擦まで息を出す", "us_faith", "/feɪθ/"),
            P("fa*c*e", "語末の [s] は鋭く強い摩擦", "us_face", "/feɪs/"),
        ]),
        ("/f/–/θ/", "", [
            P("*f*ree", "下唇を上の前歯に当てる [f]。日本語の「フ」（両唇）にしない", "us_free", "/friː/"),
            P("*th*ree", "舌先と歯の [θ] から [r] へ。free と取り違えられないように", "us_three", "/θriː/"),
            P("*f*irst", "[f] は下唇と上の歯", "us_first", "/fɝːst/"),
            P("*th*irst", "[θ] は舌先と歯", "us_thirst", "/θɝːst/"),
        ]),
        ("/ð/–/z/", "", [
            P("*th*en", "舌先を歯に当てたまま声を出す [ð]", "us_then", "/ðen/"),
            P("*Z*en", "舌先は歯ぐき。[ð] より鋭い摩擦", "us_zen", "/zen/"),
            P("brea*th*e", "語末の [ð] は舌先と歯。前の [iː] は長め", "us_breathe", "/briːð/"),
            P("bree*z*e", "語末の [z] は歯ぐき", "us_breeze", "/briːz/"),
        ]),
        ("/b/–/v/", "", [
            P("*b*erry", "両唇を閉じてから開く [b]。声紋では一瞬の破裂のあとすぐ母音", "us_berry", "/ˈberi/"),
            P("*v*ery", "下唇を上の歯に軽く当てて声を出し続ける [v]。声紋では母音の前に弱い雑音が続く", "us_very", "/ˈveri/"),
            P("*b*oat", "[b] は唇を閉じる", "us_boat", "/boʊt/"),
            P("*v*ote", "[v] は下唇と上の歯", "us_vote", "/voʊt/"),
        ]),
        ("/s/–/ʃ/", "", [
            P("*s*ee", "[s] は舌先を歯ぐきに。唇は丸めない", "us_see", "/siː/"),
            P("*sh*e", "唇を少し丸め、舌を後ろに引く [ʃ]。声紋では雑音が [s] より低いところから始まる", "us_she", "/ʃiː/"),
            P("me*ss*", "語末の [s]", "us_mess", "/mes/"),
            P("me*sh*", "語末の [ʃ]。唇を丸める", "us_mesh", "/meʃ/"),
        ]),
        ("/l/–/r/", "", [
            P("*l*ight", "舌先を上の歯ぐきにつけたまま声を出す [l]", "us_light", "/laɪt/"),
            P("*r*ight", "舌先はどこにもつけず、少し奥に引いて唇を丸める [ɹ]。声紋では母音に入る前に3本目の横じま（第3フォルマント）が低い", "us_right", "/raɪt/"),
            P("*l*ip", "[l] は舌先をつける", "us_lip", "/lɪp/"),
            P("*r*ip", "[ɹ] は舌先をつけない", "us_rip", "/rɪp/"),
        ]),
        ("文の中で", "お手本の録音はありません。語だけのときと同じ口の形を、文の中でも保てるかを自分の録音で確かめます（教科書 3.4・3.11）。", [
            P("I *th*ink so.", "think の [θ] が [s] に戻らない", sec=8),
            P("They *th*ought about it.", "thought の [θ] を [s]・[f] にしない", sec=8),
            P("He went over the pa*th*.", "文末の [θ] まで息を出す", sec=8),
            P("Turn on the *r*ight *l*ight.", "right の [ɹ] と light の [l] を言い分ける", sec=8),
            P("We need a new *v*an.", "van の [v] を [b] にしない", sec=8),
        ]),
    ],
    "test": [
        T("think — sink", "think の [θ] と sink の [s] が別の音に聞こえる", PAIR),
        T("faith — face", "語末の [θ] と [s]", PAIR),
        T("free — three", "[f]（下唇と歯）と [θ]（舌先と歯）", PAIR),
        T("breathe — breeze", "語末の [ð] と [z]", PAIR),
        T("berry — very", "[b]（両唇の破裂）と [v]（唇と歯の摩擦）", PAIR),
        T("see — she", "[s] と [ʃ]", PAIR),
        T("light — right", "[l] と [ɹ]", PAIR),
        T("collect — correct", "語中の [l] と [ɹ]", PAIR),
        T("I think so.", "文の中でも think が [θ]（sink に聞こえない）"),
        T("Turn on the right light.", "right の [ɹ] と light の [l] を言い分ける"),
    ],
}

# ---------------------------------------------------------------- 第4回 子音連続と音節
L4 = {
    "lecture": "第4回", "topic": "子音連続と音節", "view": "spec",
    "sections": [
        ("後ろから組み立てる", "母音に近い部分から言い、子音を1つずつ前に足します（教科書 3.4）。どれも1音節のまま。声紋で、子音の間に母音の横じまが入っていないかを見ます。", [
            P("eat", "まず母音と [t] だけ", "us_eat", "/iːt/"),
            P("*tr*eat", "[t] から舌を離さずに [r] へ。1音節", "us_treat", "/triːt/"),
            P("*str*eet", "[s][t][r] の間に母音を入れない（「ストゥリート」にしない）。1音節", "us_street", "/striːt/"),
        ]),
        ("語頭の子音連続", "", [
            P("*tr*y", "[t] と [r] の間に母音を入れない。1音節", "us_try", "/traɪ/"),
            P("*pl*ay", "[p] の唇の閉じと [l] の舌先を同時に準備。「プ」に母音を入れない", "us_play", "/pleɪ/"),
            P("*qu*ick", "[k] と唇の丸め [w] をほぼ同時に", "us_quick", "/kwɪk/"),
            P("*squ*are", "[s][k][w] の3つの子音の間に母音を入れない", "us_square", "/skwer/"),
            P("*spl*endid", "spl を一息に。2音節", "us_splendid", "/ˈsplendɪd/"),
            P("*fl*ight", "下唇と歯の [f] から [l] へ。1音節", "us_flight", "/flaɪt/"),
        ]),
        ("語末の子音連続と文法", "過去・複数の印になる子音を落とさず、母音も足しません（教科書 3.8・3.11）。", [
            P("help", "語末の [lp]", "us_help", "/help/"),
            P("hel*ped*", "-ed は [t]。「ヘルプド」にしない。1音節", "us_helped", "/helpt/"),
            P("ask", "語末の [sk]", "us_ask", "/æsk/"),
            P("as*ked*", "語末の [skt]。過去の [t] を落とさない", "us_asked", "/æskt/"),
            P("gift", "語末の [ft]", "us_gift", "/ɡɪft/"),
            P("gif*ts*", "複数の [s] まで。母音を足さない", "us_gifts", "/ɡɪfts/"),
            P("te*xts*", "語末の [ksts]。1音節。難しければ text から", "ll_texts", "/teksts/"),
        ]),
        ("音節主音的子音", "母音を入れず、鼻音や [l] が音節の中心になる形を試します（教科書 3.3）。", [
            P("butt*on*", "[t] のあと母音を入れず、そのまま鼻から [n] を出す形も試す。2音節", "us_button", "/ˈbʌtn̩/"),
            P("cott*on*", "[tn̩]：舌先を歯ぐきにつけたまま鼻へ", "us_cotton", "/ˈkɑːtn̩/"),
            P("litt*le*", "[t]（アメリカ英語では弾音 [ɾ]）のあと、舌先をつけたまま [l̩]", "us_little", "/ˈlɪtl̩/"),
            P("met*al*", "[tl̩]。「メタル」の「ル」の母音を入れない", "us_metal", "/ˈmetl̩/"),
        ]),
        ("文の中で", "お手本の録音はありません。目標の語、2語のまとまり、文全体の順に練習して録音します（教科書 3.1・3.2・3.5）。", [
            P("*Tr*y and do it.", "try を1音節で", sec=8),
            P("She *pr*e*ssed* the bell.", "pressed を1音節で、[st] を保つ", sec=8),
            P("He *cr*a*shed* his car.", "crashed を1音節で（[kræʃt]）", sec=8),
            P("Let's have a *qu*ick *dr*ink.", "quick の [kw]・drink の [dr] に母音を入れない", sec=8),
            P("She gave bir*th* to *tw*ins.", "birth to の [θt]、twins の [tw]", sec=8),
            P("*Thr*ee-*fifths* of them were bought for *gifts*.", "three・fifths・gifts の子音連続に母音を入れない", sec=10),
        ]),
    ],
    "test": [
        T("street", "1音節。s・t・r の間に母音を入れない"),
        T("splendid", "2音節。spl の間に母音を入れない"),
        T("texts", "1音節。語末の子音に母音を足さない"),
        T("asked", "1音節。過去の [t] が聞こえる"),
        T("helped", "1音節。-ed は [t]"),
        T("little", "2音節。2つ目は [l̩]（[ɾl̩] も可）。余分な母音を入れない"),
        T("She pressed the bell.", "pressed を1音節で、[t] を保つ"),
        T("He crashed his car.", "crashed を1音節で（[kræʃt]）"),
        T("Let's have a quick drink.", "quick の [kw]・drink の [dr] に母音を入れない"),
        T("Three-fifths of them were bought for gifts.", "three・fifths・gifts の子音連続に母音を入れない"),
    ],
}

# ---------------------------------------------------------------- 第5回 語強勢
L5 = {
    "lecture": "第5回", "topic": "語強勢", "view": "pitch",
    "sections": [
        ("第1音節に強勢", "太字が強く読む音節。「高さ・強さ」の図で、強い音節が高く・強く・長くなっているかをお手本と比べます。", [
            P("*FOR*ward", "FOR を高く長く、-ward は弱く短く", "us_forward"),
            P("*TA*ble", "TA を強く、-ble は弱く", "us_table"),
            P("*HAP*py", "HAP を強く、-py は軽く", "us_happy"),
            P("*AV*erage", "AV を強く、後ろの2音節は弱く短く", "us_average"),
            P("*GEN*erous", "GEN を強く、-erous は弱く", "us_generous"),
            P("*COM*fortable", "COM のあとは弱く短く（3音節 /ˈkʌmftərbl/ で言う人も多い）", "us_comfortable"),
        ]),
        ("後ろの音節に強勢", "", [
            P("po*LICE*", "po は [pə] で弱く短く。LICE を高く長く", "us_police"),
            P("pre*FER*", "pre は弱く、FER を強く", "us_prefer"),
            P("be*LIEVE*", "be は [bɪ] で弱く", "us_believe"),
            P("im*POR*tant", "POR を強く、im- と -tant は弱く", "us_important"),
            P("con*TRIB*ute", "TRIB を強く。第1音節を強くしない", "us_contribute"),
            P("recom*MEND*", "rec- に第2強勢、MEND が主強勢", "us_recommend"),
            P("intro*DUCE*", "in- に第2強勢、DUCE が主強勢", "us_introduce"),
        ]),
        ("語族で強勢が移る", "接辞が付くと強勢の位置が移り、強くない母音は弱くなります（教科書 3.4・3.9）。", [
            P("*PHO*tograph", "PHO が強い。-to- は弱い [ə]", "us_photograph"),
            P("pho*TOG*raphy", "TOG が強い。pho- は弱い [fə]", "us_photography"),
            P("e*CON*omy", "CON が強い", "us_economy"),
            P("eco*NOM*ic", "NOM が強い。ec- に第2強勢", "us_economic"),
            P("*NA*tion", "NA が強い", "us_nation"),
            P("natio*NAL*ity", "NAL が強い。na- に第2強勢", "us_nationality"),
            P("po*LIT*ical", "LIT が強い", "us_political"),
            P("poli*TI*cian", "TI が強い。po- に第2強勢", "us_politician"),
        ]),
        ("名詞と動詞", "同じ綴りで、名詞は前、動詞は後ろの音節が強くなります（教科書 3.7）。", [
            P("*RE*cord", "名詞（記録）。RE を強く、-cord は弱く", "us_record-noun", "名詞：記録"),
            P("re*CORD*", "動詞（記録する）。re- は [rɪ] で弱く", "us_record-verb", "動詞：記録する"),
            P("*PER*mit", "名詞（許可証）", "us_permit-noun", "名詞：許可証"),
            P("per*MIT*", "動詞（許可する）", "us_permit-verb", "動詞：許可する"),
            P("*OB*ject", "名詞（物体）", "us_object-noun", "名詞：物体"),
            P("ob*JECT*", "動詞（反対する）", "us_object-verb", "動詞：反対する"),
            P("*IN*crease", "名詞（増加）", "us_increase-noun", "名詞：増加"),
            P("in*CREASE*", "動詞（増える）", "us_increase-verb", "動詞：増える"),
        ]),
        ("句と文の中で", "お手本の録音はありません。語の強勢を、短い句や文の中でも保ちます（教科書 3.2・3.7）。", [
            P("a *RE*cord — re*CORD* it", "名詞と動詞で強勢を切り替える", sec=8),
            P("a *PRE*sent — pre*SENT* it", "名詞と動詞で強勢を切り替える", sec=8),
            P("Where did you buy the *GOLD*fish?", "goldfish は複合語。GOLD を強く、fish は弱め", sec=8),
        ]),
    ],
    "test": [
        T("photograph", "第1音節 PHO が主強勢。-to- は弱い [ə]"),
        T("photography", "第2音節 TOG が主強勢。pho- は弱い"),
        T("photographic", "第3音節 GRAPH が主強勢（第1音節に第2強勢）"),
        T("economy", "第2音節 CON が主強勢"),
        T("economic", "第3音節 NOM が主強勢（第1音節に第2強勢）"),
        T("political", "第2音節 LIT が主強勢"),
        T("politician", "第3音節 TI が主強勢"),
        T("comfortable", "第1音節 COM。後ろは弱く短い"),
        T("important", "第2音節 POR が主強勢"),
        T("recommend", "第3音節 MEND が主強勢（第1音節に第2強勢）"),
        T("a record — record it", "名詞 REcord → 動詞 reCORD。動詞の re- は弱い", "名詞（記録）→ 動詞（記録する）の順に読む", sec=8),
        T("a present — present it", "名詞 PREsent → 動詞 preSENT", "名詞（贈り物）→ 動詞（贈る）の順に読む", sec=8),
    ],
}

# ---------------------------------------------------------------- 第6回 文の卓立とリズム
FOC = "質問に答えるつもりで読む（No, … のように前置きは付けない）"
L6 = {
    "lecture": "第6回", "topic": "文の卓立とリズム", "view": "pitch",
    "sections": [
        ("句の強弱", "太字が強く読む語。弱い語（of・and・at・to など）は短く、あいまいな母音 [ə] になりやすい。図の長さと高さで、強い語と弱い語の差を見ます。", [
            P("*PIECE* of *CAKE*", "of は [əv] で弱く短く", "us_piece_of_cake", "朝飯前"),
            P("*NOW* and *THEN*", "and は [ən] で弱く短く", "us_now_and_then", "ときどき"),
            P("of *COURSE*", "of は弱く、COURSE を強く", "us_of_course", "もちろん"),
            P("at *LEAST*", "at は [ət] で弱く", "us_at_least", "少なくとも"),
            P("*HAVE* to", "to は [tə] で弱く", "us_have_to", "〜しなければならない"),
            P("good *MORN*ing", "後ろの語が強い", "us_good_morning", "おはよう"),
            P("good *NIGHT*", "後ろの語が強い", "us_good_night", "おやすみ"),
        ]),
        ("強い語を保って文を伸ばす", "お手本の録音はありません。強い語（太字）を同じように保ったまま、間の弱い語を詰めます。秒数がどれだけ伸びたかも見ましょう（教科書 3.1）。", [
            P("*COME*.", "まず1語", sec=6),
            P("*COME* to *TEA*.", "to は [tə] で詰める", sec=6),
            P("*COME* to *TEA* with *JOHN*.", "to・with を詰める", sec=8),
            P("*COME* to *TEA* with *JOHN* and *MAR*y at *TEN*.", "to・with・and・at を短く。音節の数ほどは長くならない", sec=10),
            P("*THANK* you.", "you は弱く", sec=6),
            P("*THANK* you *VER*y *MUCH*.", "強い語の間を詰める", sec=8),
            P("*THANK* you *VER*y *MUCH* for *EV*erything.", "for は [fər] で弱く", sec=10),
        ]),
        ("弱い音節を詰める", "お手本の録音はありません。弱い語を一つずつ同じ長さで読まず、強い語の間に収めます（教科書 3.2・3.10）。", [
            P("I *WANT* to *KNOW*.", "to は [tə]", sec=8),
            P("I *WANT*ed him to *KNOW*.", "him は [ɪm]、to は [tə] で詰める", sec=8),
            P("*SEE* you *LAT*er.", "you は弱く", sec=8),
            P("*SEE* you in the after*NOON*.", "you in the を詰める", sec=8),
        ]),
        ("焦点を移す", "お手本の録音はありません。同じ文で、質問に合わせて目立たせる語を一つだけ変えます（教科書 3.3・3.9）。「高さ・強さ」の図で、その語に高さの山が来ているかを見ます。", [
            P("*I* sent the report yesterday.", "I だけを高く・強く。あとは低めに平らに", ctx="Q: Who sent the report yesterday?", sec=8),
            P("I *SENT* the report yesterday.", "sent に山を置く", ctx="Q: Did you lose the report yesterday?", sec=8),
            P("I sent the re*PORT* yesterday.", "report の PORT に山を置く", ctx="Q: Did you send the letter yesterday?", sec=8),
            P("I sent the report *YES*terday.", "yesterday の YES に山を置く", ctx="Q: Did you send the report today?", sec=8),
        ]),
    ],
    "test": [
        T("Come to tea with John and Mary at ten.", "COME・TEA・JOHN・MARY・TEN が柱。to・and・at は弱形で短い。全部の語を同じ強さで読まない"),
        T("Thank you very much for everything.", "THANK・VERY・MUCH・EVerything が強く、you・for は弱い"),
        T("I wanted him to know.", "WANTed・KNOW が強く、him・to は弱く詰める"),
        T("I think that he wants us to leave.", "THINK・WANTS・LEAVE が柱。that・he・us・to は弱く詰める"),
        T("Why won't you wait until Friday?", "WHY・WAIT・FRIday が柱。弱い音節を引き延ばさない"),
        T("She consoled the weeping child.", "conSOLED・WEEPing・CHILD が柱"),
        T("I sent the report yesterday.", "焦点は I（I を最も目立たせる）", FOC, "Q: Did Mary send the report yesterday?", area="focus"),
        T("I sent the report yesterday.", "焦点は SENT", FOC, "Q: Did you write the report yesterday?", area="focus"),
        T("I sent the report yesterday.", "焦点は rePORT", FOC, "Q: Did you send the letter yesterday?", area="focus"),
        T("I sent the report yesterday.", "焦点は YESterday", FOC, "Q: Did you send the report today?", area="focus"),
    ],
}

# 課題（練習ページから提出する項目）。表示の * を除いた綴りで指定する。採点の負担を考えて各回 10〜12 項目
L3["task"] = ["think", "sink", "three", "free", "breathe", "very", "berry", "she", "light", "right", "Turn on the right light."]
L4["task"] = ["street", "square", "splendid", "helped", "asked", "texts", "button", "little", "She pressed the bell.", "Let's have a quick drink."]
L5["task"] = ["COMfortable", "imPORtant", "recomMEND", "PHOtograph", "phoTOGraphy", "eCONomy", "ecoNOMic", "poLITical", "poliTIcian",
              "REcord", "reCORD", "a PREsent — preSENT it"]
L6["task"] = ["PIECE of CAKE", "NOW and THEN", "of COURSE", "good MORNing", "COME to TEA with JOHN and MARy at TEN.",
              "THANK you VERy MUCH for EVerything.", "I WANTed him to KNOW.",
              "I sent the report yesterday.|Q: Who sent the report yesterday?", "I SENT the report yesterday.|Q: Did you lose the report yesterday?",
              "I sent the rePORT yesterday.|Q: Did you send the letter yesterday?", "I sent the report YESterday.|Q: Did you send the report today?"]

LECTURES = {3: L3, 4: L4, 5: L5, 6: L6}


# ---------------------------------------------------------------- HTML
def mark(text):
    """*…* を太字に（ほかは HTML エスケープ）"""
    out = []
    for i, part in enumerate(text.split("*")):
        out.append(f'<b class="st">{html.escape(part)}</b>' if i % 2 else html.escape(part))
    assert text.count("*") % 2 == 0, text
    return "".join(out)


def ver(name):
    return hashlib.md5(open(os.path.join(WEB, "speak", name), "rb").read()).hexdigest()[:8]


HEAD = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="robots" content="noindex">
<meta name="theme-color" content="{color}">
<title>{title}</title>
<link rel="stylesheet" href="../speak/speak.css?v={vcss}">
</head>"""

PLOTS_ON = """ <div class="tabs" id="tabs"><button type="button" data-view="wave">波形</button><button type="button" data-view="spec">声紋</button><button type="button" data-view="pitch">高さ（F0）・強さ</button></div>
 <div class="plot" id="row-model"><div class="lab"><span>お手本</span><span id="d-model"></span></div><div class="cv"><canvas id="c-model"></canvas><div class="ph" id="ph-model" hidden></div></div></div>
 <div class="plot"><div class="lab"><span>あなた</span><span id="d-self"></span></div><div class="cv"><canvas id="c-self"></canvas><div class="ph" id="ph-self" hidden></div></div></div>
 <p class="legend" id="legend"></p>"""
PLOTS_OFF = """ <p class="sub" id="d-self2"></p>
 <div hidden><div id="ph-model"></div><div id="ph-self"></div></div>"""

PRACTICE = HEAD + """
<body>
<header><p>英語音声学　{lecture}</p><h1>{title}</h1></header>
<main>
<div class="banner" id="inapp" hidden></div>
<div id="list-view">
 <div class="card">
  <p>項目をタップすると練習画面が開きます。<b>「お手本のあとに言う」</b>を押すと、お手本が流れ、終わると自動で録音が始まります。言い終わると録音が止まり、自分の声が流れます。<b>何回でも</b>録り直せます。<b>比べる</b>でお手本と自分の声を続けて聞きましょう。{intro2}</p>
  <p class="sub">録音はこのスマホの中だけで使います。送信するのは、課題で「決定」して「提出する」を押した録音だけです。静かな場所で、スマホを口から20 cmほど離して録音してください。</p>
  <p class="summary" id="summary"></p>
 </div>
 <div class="card task" id="task" hidden>
  <h2 style="margin-top:0"><span class="no">課題</span>{tasktitle}</h2>
  <p>「課題」の印がある <b>{ntask}</b> 項目を、納得いくまで練習してください。各項目で<b>「この録音に決定」</b>を押し、全部決めたらここで<b>提出</b>します。決定した録音はこのスマホに残るので、何日かに分けてもかまいません。</p>
  <div class="banner" id="t-demo" hidden>送信先が未設定のため、いまはお試し表示です（録音は送られません）。</div>
  <p class="taskprog" id="t-prog"></p>
  <div class="bar"><i id="t-bar"></i></div>
  <button class="btn2 block" id="t-next" type="button">次の未決定の課題へ →</button>
  <p class="sent" id="t-sent" hidden></p>
  <label for="sid">学籍番号</label>
  <input id="sid" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="例：24A0001">
  <label for="nm">氏名</label>
  <input id="nm" autocomplete="name" placeholder="例：目白 花子">
  <p class="err" id="t-err"></p>
  <button class="main" id="t-send" type="button">提出する</button>
  <div id="t-progress" hidden><div class="bar"><i id="t-sbar"></i></div><p class="sub" id="t-label"></p></div>
 </div>
 <div id="list"></div>
 <p class="sub"><a href="{otherhref}" style="color:inherit;font-weight:700">{othername}</a>　｜　<a href="index.html" style="color:inherit">聞いて練習（{lecture}）へ</a></p>
</div>
<div id="item-view" hidden>
 <div class="topbar"><button class="linkish" id="i-back" type="button">← 一覧</button><span class="count" id="i-count"></span></div>
 <p class="secname" id="i-sec"></p>
 <div class="card prompt"><p class="ctx" id="i-ctx" hidden></p><div class="text" id="i-text" lang="en"></div><p class="note" id="i-note" hidden></p></div>
 <div class="check" id="i-check" hidden></div>
 <button class="repeat" id="b-repeat" type="button"><i>▶ ●</i><span>お手本のあとに言う（自動で録音）</span></button>
 <div class="ctrl">
  <button id="b-model" type="button"><i>▶</i><span>お手本</span></button>
  <button id="b-rec" class="rec" type="button"><i>●</i><span>録音</span></button>
  <button id="b-self" type="button" disabled><i>▶</i><span>自分</span></button>
  <button id="b-both" type="button" disabled><i>⇄</i><span>比べる</span></button>
 </div>
 <div class="meter" id="meter"><i></i></div>
 <p class="msg" id="rec-msg" aria-live="polite"></p>
 <div class="card decide" id="decide" hidden>
  <p class="dlab">課題：提出する録音</p>
  <p id="dec-state"></p>
  <div class="row2"><button class="btn2 primary" id="b-decide" type="button">この録音に決定</button><button class="btn2" id="b-dplay" type="button" hidden>▶ 決定した録音</button></div>
  <p class="sub" id="dec-rest"></p>
  <button class="linkish" id="b-dnext" type="button">次の未決定の課題へ →</button>
 </div>
{plots}
 <div class="card rate"><p>自己評価</p><div id="rate">
  <button type="button" data-v="0"><b>0</b><span>まだ難しい</span></button>
  <button type="button" data-v="1"><b>1</b><span>意識すればできる</span></button>
  <button type="button" data-v="2"><b>2</b><span>安定してできる</span></button></div></div>
 <div class="navrow"><button id="i-prev" type="button">← 前へ</button><button id="i-next" type="button">次へ →</button></div>
</div>
</main>
<footer id="credits">
<h2>お手本の音声の出典</h2>
<p>お手本は Wikimedia Commons（Lingua Libre を含む）で公開されている録音です。授業用に前後の無音を切り、音量をそろえて MP3 にしました。CC BY-SA の録音を加工した音声は、同じライセンスで利用できます。話者名から Commons の元ファイルに移れます。</p>
<details><summary>一覧を開く（{n} 件）</summary>
<table><tbody>
{credits}
</tbody></table></details>
<p>ページ：英語音声学（目白大学）授業資料</p>
</footer>
<script src="../config.js"></script>
<script src="../speak/core.js?v={vcore}"></script>
<script src="../speak/practice.js?v={vjs}"></script>
<script>SP.practice({data});</script>
</body></html>
"""

RECORD = HEAD + """
<body class="test">
<header><p>英語音声学　{lecture}</p><h1>{title}</h1></header>
<main>
<div class="banner" id="demo" hidden>送信先が未設定のため、いまはお試し表示です（録音は送られません）。</div>
<div class="banner" id="inapp" hidden></div>

<section id="s-start">
 <div class="card">
  <p>画面に出る英語を、1問ずつ録音します。全 <b>{total}</b> 問。お手本は流れません。<b>録音を止めると、その場で自動的に先生に送信</b>され、次の問題に進みます（聞き直し・録り直しはしません）。</p>
  <ul class="tips sub">
   <li>静かな部屋で、スマホを口から20 cmほど離して録音してください。</li>
   <li>ふだんの速さで、はっきり1回読みます。話し終わると録音は自動でも止まります。</li>
   <li>声が録れていないときだけ、その問題をもう一度録音できます。</li>
   <li>「マイクの使用」をたずねられたら「許可」を押してください。最後の「提出しました」が出るまでページを閉じないでください。</li>
  </ul>
 </div>
 <div class="card">
  <label for="sid">学籍番号</label>
  <input id="sid" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" placeholder="例：24A0001">
  <label for="nm">氏名</label>
  <input id="nm" autocomplete="name" placeholder="例：目白 花子">
  <p class="err" id="err"></p>
  <button class="main" id="go" type="button">マイクを使って始める</button>
 </div>
</section>

<section id="s-rec" hidden>
 <div class="progress"><span id="r-count"></span><span id="who"></span></div>
 <div class="progress"><span class="sub" id="up-state"></span><div class="dots" id="r-dots" aria-hidden="true"></div></div>
 <div class="card prompt">
  <p class="sub" style="margin:0 0 6px">次の英語を読んでください</p>
  <p class="ctx" id="r-ctx" lang="en" hidden></p>
  <div class="text" id="r-text" lang="en"></div>
  <p class="note" id="r-note" hidden></p>
 </div>
 <div class="recorder">
  <button class="rec-btn" id="btn-rec" type="button" aria-label="録音を始める"><span></span></button>
  <div class="rec-label" id="rec-label">タップして録音</div>
  <div class="timer" id="rec-timer"></div>
  <div class="meter" id="rec-meter"><i></i></div>
 </div>
 <p class="msg" id="r-msg" aria-live="polite"></p>
</section>

<section id="s-send" hidden>
 <div class="card">
  <h2 style="margin-top:0">送信しています</h2>
  <div class="bar"><i id="send-bar"></i></div>
  <p class="sub" id="send-label"></p>
  <button class="main" id="resend" type="button" hidden>もう一度送信する</button>
 </div>
</section>

<section id="s-done" hidden>
 <div class="card receipt">
  <div class="check-mark" aria-hidden="true">✓</div>
  <h2 style="margin:0">提出しました</h2>
  <p class="sub" style="margin:8px 0 0">受付番号</p>
  <p class="code" id="d-receipt"></p>
 </div>
 <div class="card"><dl class="meta">
  <dt>氏名</dt><dd id="d-name"></dd><dt>受信</dt><dd id="d-count"></dd><dt>日時</dt><dd id="d-time"></dd><dt>回</dt><dd id="d-attempt"></dd>
 </dl></div>
 <p class="sub">念のため、この画面をスクリーンショットで保存してください。もう一度受けると、新しい提出として受け付けます（採点は最後の提出）。</p>
 <div class="banner" id="d-demo" hidden>お試し表示のため、実際には送信していません。</div>
 <button class="main ghost" id="again" type="button">はじめにもどる</button>
</section>
</main>
<script src="../config.js"></script>
<script src="../speak/core.js?v={vcore}"></script>
<script src="../speak/record.js?v={vjs}"></script>
<script>SP.record({data});</script>
</body></html>
"""


def fill(tpl, **kw):
    for k, v in kw.items():
        tpl = tpl.replace("{" + k + "}", str(v))
    assert not re.search(r"\{[a-z]+\}", tpl.replace("{data}", "")), re.findall(r"\{[a-z]+\}", tpl)
    return tpl


def credit_rows(keys, source):
    rows = []
    for k in keys:
        f, lic, who = source(k)
        assert lic in LIC_URL, (k, lic)
        page = "https://commons.wikimedia.org/wiki/File:" + f.replace(" ", "_")
        lic_html = f'<a href="{LIC_URL[lic]}">{lic}</a>' if LIC_URL[lic] else lic
        rows.append(f'<tr><td>{html.escape(k.split("_", 1)[1].replace("_", " "))}</td>'
                    f'<td><a href="{html.escape(page)}">{html.escape(who)}</a></td><td>{lic_html}</td></tr>')
    return "\n".join(rows)


def build(no, source):
    L = LECTURES[no]
    d = os.path.join(WEB, f"lecture{no:02d}")
    sections, used, ids = [], [], set()
    # 課題の指定は表示の綴り（大文字・小文字を含む）で照合。焦点の文は「文|質問」
    task_keys = {t.replace("*", "") for t in L["task"]}
    found = set()
    for si, (title, lead, its) in enumerate(L["sections"]):
        out = []
        for it in its:
            k = it["model"]
            if k:
                assert not k.startswith(("fk_", "ga_", "rp_")), k   # 公開不可の音声を使わない
                assert os.path.exists(os.path.join(d, "audio", k + ".mp3")), (no, k)   # 聞いて練習ページで公開済みの録音だけ
                if k not in used:
                    used.append(k)
            plain = it["text"].replace("*", "")
            iid = re.sub(r"[^a-z0-9]+", "-", (it["ctx"] + " " + plain).lower()).strip("-") + ("-" + hashlib.md5(it["note"].encode()).hexdigest()[:4] if it["note"].endswith(("名詞", "動詞")) or "：" in it["note"] else "")
            assert iid not in ids, iid
            ids.add(iid)
            tkey = it["text"].replace("*", "") if not it["ctx"] else it["text"].replace("*", "") + "|" + it["ctx"]
            is_task = tkey in task_keys
            if is_task:
                found.add(tkey)
            out.append({"id": iid, "html": mark(it["text"]), "text": plain, "note": it["note"], "ctx": it["ctx"],
                        "check": it["check"], "model": f"audio/{k}.mp3" if k else None, "task": is_task,
                        "area": AREA["focus" if it["ctx"].startswith("Q:") else no],
                        "maxSec": it["maxSec"] or (6 if " " not in plain.strip() else 8)})
        sections.append({"title": title, "lead": lead, "items": out})
    assert found == task_keys, (no, task_keys - found)
    tasktitle = f'{L["lecture"]} {L["topic"]}の発音課題'
    data = {"page": f"l{no:02d}", "view": L["view"], "sections": sections,
            "task": {"testId": f"l{no:02d}-task", "title": tasktitle}}
    # 図を出さない版（speak.html）と、波形・声紋・F0 を出す音声分析つきの版（analyze.html）。課題の決定・自己評価は両方で共有
    for fname, analysis in (("speak.html", False), ("analyze.html", True)):
        title = f'{L["topic"]}を話して練習' + ("（音声分析つき）" if analysis else "")
        other = ("speak.html", "図を出さない練習ページへ →") if analysis else ("analyze.html", "音声分析（波形・声紋・F0）つきで練習する →")
        page = fill(PRACTICE, color="#1F6F64", title=title, lecture=L["lecture"], vcss=ver("speak.css"), vcore=ver("core.js"),
                    vjs=ver("practice.js"), n=len(used), credits=credit_rows(used, source), tasktitle=tasktitle, ntask=len(task_keys),
                    plots=PLOTS_ON if analysis else PLOTS_OFF, otherhref=other[0], othername=other[1],
                    intro2="波形・声紋・声の高さ（F0）と強さの図で、お手本と自分の声を同じ時間目盛りで見比べられます。" if analysis else "")
        page = page.replace("{data}", json.dumps(dict(data, analysis=analysis), ensure_ascii=False))
        assert "fk_" not in page
        open(os.path.join(d, fname), "w").write(page)

    tests = []
    for i, it in enumerate(L["test"]):
        assert "*" not in it["text"], it["text"]
        sec = it["maxSec"] or (5 if " " not in it["text"] else (7 if "—" in it["text"] else 10))
        tests.append({"text": it["text"], "note": it["note"], "ctx": it["ctx"], "check": it["check"],
                      "area": AREA[it["area"] or no], "maxSec": sec})
    ttitle = f'{L["topic"]}の発音テスト'
    data = {"testId": f"l{no:02d}-speak", "title": f'{L["lecture"]} {ttitle}', "items": tests}
    page = fill(RECORD, color="#2B3A67", title=ttitle, lecture=L["lecture"], vcss=ver("speak.css"), vcore=ver("core.js"),
                vjs=ver("record.js"), total=len(tests))
    page = page.replace("{data}", json.dumps(data, ensure_ascii=False))
    open(os.path.join(d, "record.html"), "w").write(page)
    print(f"lecture{no:02d}: speak {sum(len(s['items']) for s in sections)} items ({len(used)} models, task {len(task_keys)}), record {len(tests)} items")
