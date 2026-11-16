# 英語音声学 聞いて練習

目白大学「英語音声学」の受講者向け、スマホで開く音声練習ページ。
https://labphonlab.github.io/english-phonetics-listening/

- 第3回（子音）：3.1 子音対立の語対、3.2 文脈の中の語対
- 第4回（子音連続と音節）：`lecture04_page.py`
- 第5回（語強勢）：`lecture05_page.py`。テストは「いちばん強いのはどの音節？」（選択肢問題）と名詞／動詞の対
- 第6回（文の卓立とリズム）：`lecture06_page.py`。公開ライセンスの文の録音が無いので、Commons の短い句（piece of cake・now and then など）・語・Lingua Libre の and/to（単独）・さくら/とうきょうで組んだ。テスト（l06-rhythm、17問）は選択肢問題のみ：語の強弱型 8（同じ話者 Dvortygirl）、句の中の弱い語 6・強い語 1、日本語の拍の数 2
- 聞き取りテスト（各回の test.html）：部品は `test_page.py`、送信先は `config.js`、受付は `gas/`
- 音声はすべて Wikimedia Commons（Lingua Libre を含む）の公開ライセンス録音（CC0・CC BY-SA・パブリックドメイン）。
  前後の無音を切り、音量をそろえて MP3 にした。CC BY-SA の録音を加工した音声は CC BY-SA で利用できる。出典はページ下部。
- 生成：`python3 build_web.py`（授業スライド作業フォルダの lectureNN/audio から公開可の音声だけをコピーする）
