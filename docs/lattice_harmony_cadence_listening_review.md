# 格子音階の和声進行・カデンツと聴取経験のずれ：ピアノソロ診断

Status: **現行実装の整理＋聴感に関する仮説／次版の設計課題**。
実際に WAV を聴いて判定した結果ではない。主な対象は
`piano_solo_generation_spec.md` の v2/v3 と保存済み piano solo cohort。

## 1. まず「進行」と「カデンツ」の層を分ける

| 層 | 現行の情報 | そこからは言えないこと |
| --- | --- | --- |
| 形式 | section の `function`、長さ、`cadence_target`、phrase の slot | `cadence` という slot 名だけでは可聴の終止にならない |
| 計画 | phrase の `state_id`／`harmonic_function`／`root_degree_ordinal` と許可された transition | `home` という名前だけでは実音が主和音だと分からない |
| 実音化 | section `tonal_center`、bar の root anchor、`chord_intent.reference`、発音位置 | 格子 vector の差はそのまま T／S／D の機能ではない |
| 解決 | resolved chord の exact ratio、voice offset、進行 solver の声部配置 | 近い音高比で連結しても聴き手が「帰着」を認識するとは限らない |
| 演奏／聴取 | bass・旋律・強拍・長さ・前後の休み・音色と WAV | G1 スコアやカデンツ名だけでポップスらしさは確定しない |

ここでは「**計画上の終止**」= profile 上の terminal state 制約、
「**実音上の終止手掛かり**」= 直前と直後の root／構成音／声部／旋律の解決、
「**知覚上の終止**」= 試聴者が区切り・到着・未解決を感じること、と定義する。
三者の一致／不一致を分けて報告する。`arrival` は「次に到着する準備」
という `cadence_target` の値でもあり、実際の帰着した和音の保証ではない。

## 2. 現行 2D 格子での機能名と実音の対応

ピアノ専用の lattice は equave `2/1`、generator `[3/1, 5/1]`。
オクターブ同値で `3/1` は `3/2`（約 702 cents）、
`5/1` は `5/4`（約 386 cents）としても読める。
`composition_lowering.py` の `_FUNCTION_VECTOR` は
`home=(0,0)`、`departure=(1,0)`、`preparation=(0,1)`、
`arrival=(0,0)`、`return=(0,0)` で、section の tonal center に使う。
さらに bar 内の root は structural program の anchor 候補と
`root_degree_ordinal % 3`、section 固有の `root-mode` で選ばれる。

**注意すべきズレ**:

1. `departure` は格子上では概ね五度方向、`preparation` は長三度方向への
   center 移動であり、語義通りの **predominant／dominant** を自動的に意味しない。
   選んだ chord reference、直前直後の root と調的中心まで含めて初めて
   機能を判断できる。前案の `departure → predominant`、
   `preparation → dominant_tension` は**仮ラベル**であり、伴奏リズムを
   決める確定規則には使わない。
2. `home`／`arrival`／`return` は同じ center vector。実際の root anchor、
   chord intent と voicing が変わり得るため「同じ主和音へ帰った」ことには
   ならない。逆に異なる exact ratio の和音でも共通の調的中心は感じ得る。
3. chord reference は EDO の steps 又は JI の ratios だが、resolver は
   **格子上の exact ratio** に置く。12-EDO を選んだことは 12-EDO 音を
   そのまま発音したことを意味しない。`reduce_anchor_mod_equave` は
   極端な octave 漂移を抑えても、和声機能や cadence を補正しない。
4. 旋律の `passing`／`neighbor`／`scale_degree` は最近傍の格子点、
   `chord_member` も前音付近に re-octave される。終止直前の導音／
   傾向音が期待どおり解決するか、phrase 末音が到着和音の重要音を
   強拍で担うかは独立に検証が要る。

例: 同じ tonic 基準の `(0,0) → (1,0) → (0,0)` なら根音の
五度上行→下行に相当し得るが、実際に V→I と聴こえるかは
五度先の和音に緊張音が含まれるか、低音・旋律・拍節位置と
帰着を支えるかに依存する。一方 `(0,1)` は長三度方向なので、
`preparation` という名前だけで V と表記しない。
参照する tonic が変われば同じ格子差でも調的意味は変わる。

## 3. 保存済み Project の確認（聴感評価ではない）

`local_authority/piano_solo_symbolic_1000/seed-0000`〜`seed-0099`
の Plan・Program・Project・G1 report から数えた診断。100 seed は
1,000 seed の全数ではなく、選択バイアスもあり得る。

- section 最終 phrase の `cadence_target=arrival` **171 件は全て**
  `harmonic_function=preparation`。profile の terminal 制約によるもので、
  **arrival は次 section に予定される**という読みが必要。
- `cadence_target=home` **300 件**の最終 state は `home` 155、
  `arrival` 45、`return` 100。いずれも plan 上は許容されるが、
  `home` という単一の状態に揃ってはいない。
- 上の 300 section のうち、最初と最後の harmony occurrence の
  `resolved_chord.exact_ratios` が完全一致したものは **81 件**。
  これは「主和音がない」証拠でも「終止に失敗した」判定でもない。
  転回形・octave・違う進行位置・到着後の和音を区別せず、
  **同一比率列か**だけを数えた極めて狭い proxy。
- build（`preparation` section）→drop（`arrival` section）の境界は
  **71 件**。直前と直後の resolved chord の `exact_ratios` の列が
  完全一致した境界は **11 件**（anchor vector も一致）。例えば seed 0 は
  build_a の最終 `preparation` から drop_a の最初の `arrival` に
  移るが、両側の比率列は `['1/1', '8/27', '3/2']`。
  section の音量・旋律・打鍵で「drop」は感じられ得るが、
  **和音そのものの変更による解決**はここでは起きていない。
  同じ列でも articulation／長さ／声部の実際の聴こえは要試聴。
- G1 の `home_return`（冒頭／末尾 section 全体の harmony 音高集合の
  完全一致）は **35/100 曲**。旋律と低音が帰着しても集合は一致しない
  場合があり、単体で聴感上の home return を否定できない。
- 100 seed の chord intents は **EDO 83／JI 17**。
  発音時間で重み付けした「最近傍 12-EDO から 10 cents 以上離れる
  note」の share は中央値 **4804/10000**（約 48%）。
  この露出量は「格子らしさの優劣」や「不協和度」を意味しない。

集計母数は曲ごと／section ごと／intent ごとで異なる。
聞こえの結論はこれらの数字からは出さず、WAV の盲検比較で確かめる。

## 4. なぜ plan が同じでも聴取が変わるか：検証する仮説

| 仮説 | 識別したい現象 | 観測する対象 |
| --- | --- | --- |
| 調的基準が伝わらない | 帰るべき中心が定まる前に格子 root が移る | intro／verse の bass・旋律の反復、着地点の滞在時間 |
| 機能名と実音が食い違う | `preparation` でも dominant 的な導音・解決がない | 直前 2 chord と到着 chord の root／共通音／傾向音 |
| 微分音差が機能の手掛かりを曖昧にする | 周知の長短三和音／7th との音程差が意図を隠す | exact ratio と 12-EDO 参照間の各 voice gap、解決方向、実聴 |
| 音域・配置に埋もれる | 低すぎる bass、高い和声、旋律との音域競合 | role 別実音域、最上和声声部と旋律の重なり |
| 終止位置が弱い | chord は帰着しても弱拍・短 gate で通過する | strong beat／duration／休み／次 section の一拍目 |
| 同じ循環が伝わらない | v3 cycle ID は一致しても和音形や bass が毎回大きく違う | root と打鍵 onset の反復率、実音和音の類似性 |

格子差そのものを「悪い音」とみなさない。JI の和音内比や独特の
近接和音が魅力となる場合もある。必要なのは、**どの区間では
既知のポップス機能を聴かせたいか、どこで格子固有の色を聴かせたいか**
という配置の意図である。v3 の反復は中心の学習には役立ち得るが、
誤って dominant と呼んだ和音を反復しても帰着の弱さは直らない。

## 5. 次版の和声・カデンツ記述案

phrase／cycle に `harmonic_function` と別の**期待する聴覚効果**
（`stable`, `departure`, `tension`, `arrival`, `open`）を付ける。
さらに cadence は `continuation`, `open`, `section_arrival`,
`final_arrival` の**境界イベント**として扱い、直前 bar、到着 bar、
次 section 冒頭を一つの検査窓にする。終止ターゲットは最後の
state 名だけでなく以下を明記する:

1. tonic の参照（絶対の `tonal_center` vector と equave、root anchor）と
   曲中の再提示位置。機能名は参照中心に対する根音と構成音を検査してから付ける。
2. 到着前の chord と bass の相対 root／exact ratio、
   到着 chord の許容する reference family、共通音・声部移動の条件。
   12-EDO に射影したローマ数字は**補助ラベル**に留め、ずれの cents を併記。
3. melody の到着音とその直前の傾向音の方向・強拍位置・保持時間、
   左手（harmony 内 bass）の着地と右手旋律の同時性。
4. `open` なら着地を遅らせ、次 section で初めて解決する条件。
   build 最終の `arrival` ターゲットを build 内で解決済みと誤記しない。
5. 必要に応じて **hybrid**: 安定／着地の区間は 12-EDO 参照に近い
   格子和音で機能を示し、経過／発展では格子固有の和音を増やす。
   ただし格子露出量を無条件最大化したり、exact ratio を MIDI の
   12 音へ丸めたりしない。

この契約は既存の Plan／SongProgram schema に未実装。
`v2 harmonic_role` の自動割当は検証されるまでは `unknown` を許し、
伴奏パターンの強制選択にも使わない。`harmonic_motion_q` は section ごとの
和声音高集合の種類と冒頭／末尾の同一性に依存し、**cadence の音楽的
解決そのものを測る値ではない**。新しい cadence 診断を別 report にする。

## 6. 聴取との突き合わせ方

1. 同じ seed／テンポ／ピアノ音色／音量で 8～16 曲を固定し、
   `home`、`arrival`、`open`、v3 の cycle 再帰が異なる断片を選ぶ。
   Project・receipt・catalog hash と、その位置の Plan states、
   resolved chords、exact ratio、bass／melody の到着音を記録する。
2. **文脈つき**で境界の前後 2 小節以上を再生。単独和音だけで
   「ドミナントか」と尋ねない。A/B は音量とテンポを合わせ、
   ローマ数字・state 名を隠し、順序を入れ替える。
3. 各断片について「どこが tonic に聴こえるか」「境界で解決／継続／
   未解決のどれを感じるか」「着地点を予測できるか」「格子特有の色は
   魅力か違和感か」を記録し、迷った回答も保持する。
4. 同 seed の差分を一つずつ作る: root／reference だけ変更、
   voicing／音域だけ変更、melody の着地だけ変更、beat／gate だけ変更。
   12-EDO に近い参照と格子固有の参照の比較も、進行・編成・mix は固定。
   `PROGRESSION_NO_PATH` 等の不成立を含めて報告する。
5. 「plan=home だが聴感=未解決」の事例を保存し、どの音高／時間／音域の
   修正で解決と感じたかを確認してから重みを調整する。被験者全員が
   同じ T／S／D 解釈を持つとは仮定しない。G2 大規模評価を前提にしない。

関連実装: `backend/app/songprogram/composition_generation.py`（terminal state）、
`composition_lowering.py`（section center／bar root／harmony rhythm）、
`compiler.py`／`resolver.py`（exact ratio・進行選択）、
`composition_viability.py`（G1）、`lattice_pitch_diagnostic.py`（12-EDO 差）。
