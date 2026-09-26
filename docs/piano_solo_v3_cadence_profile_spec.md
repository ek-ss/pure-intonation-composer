# 5D辞書の実装確認とカデンツ駆動ピアノプロファイル v3 仕様案

Status: **実装監査（2026-09-27）→ 数値ブロッカー修正済み（2026-09-27）＋未実装の v3 策定**。
監査対象は commit `1738ad22` の 5D Harmony Dictionary。
作業ツリーにある piano v2 の compiler／lowering／profile 試作は
進行中の作業として扱い、本仕様の完成済み依存物には数えない。
既存 v1 の 2D seed と hash は履歴として再現可能に保つ。

> **修正記録（2026-09-27）**: 下記のブロッカー 1–4 を修正し、
> `authority`／`storage`／`dictionary`／`stability`／`projection`／`cadence`
> を **1.1.0** に version-up、両 equave の sealed file を再生成・`--check`
> byte parity 再照合済み。`_equave_cents` は `1200*log2(E)`（2/1=1200、
> 3/1≈1901.955）、`_interval_vector` は真の equave 円周で折返し、
> 声部移動・common tone・傾向音は実音 `root×ratio` で比較、単位は
> decicent（`*_dc`、1 dc=0.1 cent）、`plagal`→`predominant_chain`。
> 折返し境界・不変性・root 移動の基準値試験を追加（後述 §5-1）。
> 関連テスト 858 件通過。v3 の §2–§4 は未実装のまま。

## 1. [5D辞書計画](development_plan_5d_chord_cadence_dictionary.md)との照合

| 計画 | コード・成果物から確認したこと | v3 導入前の扱い |
| --- | --- | --- |
| 2/1・3/1 のループ／5D | `authority.py` に2つの5軸、bounded loop と軸別 pitch list | 実装あり。loop の単位表記を修正する |
| 3・4音辞書 | builder が equave ごとに10種の辞書を seal。`--check` は2ファイルとも再生成 byte parity 成立 | 実装あり。ただし tritave 13軸/4音は0 variant、`NOT_ENOUGH_AXIS_POINTS`。全軸／声数を使えると仮定しない |
| 任意5D和音 | `projection.py` は共通1軸へ射影し、元の比率で再評価、失敗時 on-demand 評価 | 実装あり。`measure_recall` は小標本の試験のみで、実曲の index recall／誤分類率は未較正 |
| 安定度と T/D/S | `stability.py` の4成分と仮閾値 7000/3000、`cadence.py` の候補生成／diagnostics | **音楽上の分類の検証は未了**。下記の数値誤りを修正して version を上げて再較正する |
| Web UI／API | `/harmony-dictionary` と5 API、pitch/chord 表、射影、cadence、Web Audio、session 保存 | 操作経路はあり。ピアノ SongProgram に cadence を渡す generation profile はまだ無い |

確認: `build_5d_chord_dictionary.py --check` は双方 OK。
関連テストは `authority`／`stability_cadence`／`projection` の **71 件**、
`axis`／`builder_api` の **37 件**が通過した（合計108件）。
これは現実の聴感や閾値の妥当性を認定する結果ではない。
API の試験呼び出しで `authentic` は両 equave とも3和音を返したが、
これは後述の数値修正前の動作例である。

### ブロッカー（実装を修正し、辞書／指標の version を更新する）

> 2026-09-27 に 1–4 すべて修正済み（上記の修正記録を参照）。
> 以下は監査時点の記録として残す。

1. `stability.py::_equave_cents` と `projection.py::_equave_cents` は
   `1200 * (equave.numerator/equave.denominator)` を返す。
   実際の equave 幅は **`1200*log2(equave)`** で、2/1 は1200 cents、
   3/1 は約1901.955 cents。現状はそれぞれ2400／3600を返す。
   circular root distance、voice-lift、軸への射影と gate が影響を受ける。
   `d(1/1,15/8;2/1)` など**折返し境界**、`d(1/1,3/2;3/1)`、
   transpose/equave-lift 不変性を基準値で追加試験する。
2. `cadence.py::_voice_leading_cents` は `(root_ratio, root_relative_ratios)`
   を受け取るが voice の比較に root を掛けていない。
   例えば同じ `[1/1,5/4,3/2]` を tonic と `3/2` root に置き直しても
   **移動 0 cents** と報告する。`diagnose_voice_leading`／
   `diagnose_tendency_resolution`／common tones も実音 `root × ratio` で
   再評価し、声部の一対一対応・移動上限を確認する。
3. `authority.py` の `distance_mc`／`tolerance_mc` は式が
   `1200*10=12000 units/octave` で、実際は **0.1 cent 単位**。
   「100 millicents = 10 cents」は正しい単位名ではない。
   loop の n 自体は10 cents 判定に相当するが、出力の単位を明記して
   field/version を修正し、既存 seal と混在させない。
4. `cadence.py` の report は生成時に自ら割り当てた T/D/S slot を
   `truth` とする。これは独立した音楽的正解ラベルではない。
   `ClassificationThresholds(7000,3000)` も仮値であり held-out
   アノテーションによる較正は確認できない。三分類を arranger の
   確定入力とせず、`ambiguous` を保持する。なお現在の
   `plagal` template は `T→S→D→T` で、通常の `IV→I` という
   名称とは異なるため `predominant_chain` 等に改名する。

現行の通過テストには period の物理的な基準値や root 移動を含む
反例が不足する。修正時は scoring/projection/cadence の contract を
version-up し、sealed file／cache を再生成・再照合する。
このゲートを通る前の `stability_q` や候補の「tonic」ラベルを
ピアノ v3 の強制的な作曲判断に使わない。

## 2. v3 の入力・権威境界

- profile は `piano-solo-v3-octave`／`piano-solo-v3-tritave` の**別々の**
  sealed manifest を用意する。いずれも 5D で、軸は辞書の
  `AXES_BY_EQUAVE` に一致。`2/1:[3,5,7,11,13]` と
  `3/1:[2,5,7,11,13]`。新規生成で2Dを抽選しない。
- 親の composition seed、structural seed、Plan hash、辞書 file hash、
  stability-profile hash、閾値版、cadence algorithm ID、production
  catalog digest を receipt に記録。12-EDO 近似は**候補検索のみ**。
  Program と Project の演奏音は exact ratio。equave 間の比較で
  「同じコード名だから同じ tonic」とみなさない。
- SongProgram の 5D bounds は生成前に `product(axis_width)` と
  `× register_width` を計算し、現行 GEN0-B の coordinate 1024、
  placed 4096 と Program の `maximum_domain_points` を守る。
  `[-2,2]^5` (=3125) をそのまま通さない。5次元を指定しながら
  後ろの軸を常にゼロ固定にする profile も不可。最初は bounded な
  root／chord neighborhood を小さく選び、navigation の全12音
  被覆・通常音域での可解性を**実測**してから範囲を seal する。
- v2 の音域／跳躍／音量仕様は維持するが、v2 の実装中ファイルに
  v3 の意味を後付けしない。必要なら独立の v3 lowering と
  生成 CLI／receipt を作り、v1/v2 の hash・比較成果物を保つ。

## 3. Plan から cadence へ：曲全体の設計

v1/2 の `harmonic_trajectory` は phrase state 制約であり、
辞書の「T/D/S」や実音 chord への確定対応ではない。
v3 は `CompositionPlan` と辞書に束縛された**sealed `cadence_plan`** を
別に生成する。v1 Plan の既存 schema に未宣言 field を混ぜない。
`source_plan_hash`、equave、tonic ratio/vector、辞書 hash、
section ID、phrase ID、bar の開始／長さ、slot の `expectation`
（`stable`／`depart`／`prepare`／`arrive`／`open`）、
選んだ root vector と exact reference、前後への解決対象を保持。
profile の独立した `cadence_policy/v1` に equave ごとの辞書 hash、
使える 3/4 音の voice_count、`candidate_budget`（初期上限32）、
`max_changes_per_bar`（初期2）、section ごとの open/closed 配置、
2bar cycle の繰返し条件、project-level の音域・移動上限を seal する。
閾値は較正された profile hash を参照し、API の現行 default 値を
コピーして確定扱いしない。候補の抽選は `seed + section_id + slot_id +
cadence_policy_hash` による domain-separated hash で独立に行い、
一つの候補の失敗が別 section の選択乱数を変えない。

| Section | 4bar の初期設計例 | 実音への要求 |
| --- | --- | --- |
| intro | tonic を聴かせる反復／次へ開く | tonic の参照を確立。拍と音域を控えめに |
| verse／return | 2bar cycle ×2（同じ root/chord-change 骨格） | 伴奏 cell を反復、2周目は旋律 answer と末尾 1bar の小変形 |
| build | 前半は root/リズムの反復、最終 bar は `prepare/open` | build 内で完結する偽の着地を避け、drop の1拍目へ解決を渡す |
| drop／final | 最初の bar を `arrive`、既知の cycle を強く再提示 | build 最終→drop 冒頭の**実音**に root／voice／melody の動きがある |
| break | 簡略 cell、部分的な引用 | 対比を保ち、各 section に T/D/T を強要しない |
| outro | 最後の `final_arrival` と長めの保持 | 最終の melody／bass と一緒に着地 |

cadence は `closed(T→D→T)`、`predominant_chain(T→S→D→T)`、
`open(…→D)` と lattice-native な代替案を**候補**として扱う。
辞書のラベル単独では決めず、T は指定 tonic の root と実音の安定、
D は後続 T への解決、S は D への準備を**遷移で**検査する。
閾値を満たさない候補を一律に捨てず、根拠つき `ambiguous` とし
別候補へ進むか失敗として返す。tritave で辞書にない
13軸/4音を選ばない。別軸を混ぜる場合は projection error と
exact reevaluation を必ず残す。

### CadencePlan の最小形（提案、現行 schema ではない）

```json
{
  "schema": "cps.piano-cadence-plan",
  "schema_version": "1.0.0",
  "source_plan_hash": "sha256:<64 hex>",
  "dictionary_hash": "sha256:<64 hex>",
  "stability_profile_hash": "sha256:<64 hex>",
  "equave": "2/1",
  "tonic": {"vector": [0, 0, 0, 0, 0], "ratio": "1/1"},
  "slots": [
    {"section_id": "sec_002", "phrase_id": "phr_004", "bar": 3,
     "expectation": "open", "source_chord_key": "<dictionary key>",
     "root_vector": [1, 0, 0, 0, 0], "resolve_into": "sec_003/0"},
    {"section_id": "sec_003", "phrase_id": "phr_005", "bar": 0,
     "expectation": "arrive", "source_chord_key": "<dictionary key>",
     "root_vector": [0, 0, 0, 0, 0], "resolve_into": null}
  ]
}
```

例は**境界2 slot の抜粋**。完成した plan は全 bar／harmony-change
区間を欠落なく覆い、辞書の variant ID と root／register／chord ratios
を確定する。`source_chord_key` は索引なので、同 key の exact variant
選択結果を別に seal する。closed/open と次 section 冒頭の関係が
矛盾する request は拒否し、抽選だけで無理やり解決しない。

## 4. Program／Project 化と聴感の確認

辞書に登録された chord の `ratios` を equave に整合する
SongProgram `chord_intent.reference` に結び、5D root anchor と
登録した actual variant の一致を検証する。候補になっただけで
compiler が同じ和音を出すとは限らない。GEN0-A/B の exact top-K
と path を通した後、**Project の `resolved_chords` を使い**
bar 別の予定と実音の root／chord／voice を照合する。
単一軸辞書から選んだ 3/4 音が狭い 5D domain に埋め込めない場合は
無断で 2D に戻さず typed failure とし、同 equave の別 variant を
既定の試行回数まで選ぶ。格子原音と 12-EDO 近似は両方記録するが
Project の ratio を12音へ丸めない。

前景旋律の motif は残し、build 最終の傾向音が drop 最初の
着地点へ移るかを監査する。和声変更の時間区間と同じ chord の
再打鍵は分け、裏拍の伴奏で melody を意図せず短縮しない。
home／arrival という旧 state 名や高い `stability_q` だけでは
完成した cadence の根拠にならない。

`cadence_impact_report` は少なくとも以下を Plan／Program／Project の
**三段**で記録する: 予定した T/D/S/unknown、選択した辞書 variant
の exact ratio／5D vector、射影誤差、実際の resolved ratio、
前後の root と同一声部の移動、melody の解決、拍節の着地、
開放／終止の一致、音域と候補の失敗理由。旧 [診断](lattice_harmony_cadence_listening_review.md)
にある build→drop の同一 chord 事例は別の cadence として検出する。
誤分類・`PROGRESSION_NO_PATH`・MIDI 音域外・音域制約超過を
候補母数から隠さない。WAV skip は symbolic `incomplete` とし、
PCM G0 を経ない archive admission を認めない。

## 5. 実装順と検収

1. **数値ブロッカーを修正**: equave の log2、root を含む声部移動、
   単位名、cadence 名を修正して新 version／seal を作る。
   物理的な境界値、tritave、root だけの変化をテストする。
2. **辞書／分類を較正**: 3/4音、両 equave の候補、unknown 件数、
   生成器から独立した期待ラベルと少数試聴で T/D/S の threshold を
   再決定。索引 recall と誤分類率を小規模 exact baseline で測る。
3. **5D profile を seal**: 2D を除外し、非ゼロ第4／第5軸の成功例、
   coordinate／placed 予算、音域／stock catalog、Plan の12音
   navigation と生成時間を確認する。
4. **cadence_plan と lowering**: 同 seed の反復・section 境界・
   melody binding、辞書 variant の clone-on-write と Project 差分、
   typed failure と resume／hash parity をテストする。
5. **比較試聴**: 同 seed／音色／テンポ／form で `2D v1 (historical)`、
   `5D 反復のみ`、`5D cadence 駆動`、`5D cadence＋伴奏機能切替`
   を比較。ただし次元の効果と cadence の効果は別々の paired 対照で
   読み、2D 対照を新しい生成候補には含めない。

8～16 seed の section 別に、build で期待が生じたか、
drop の最初に解決が聴こえたか、verse の反復が安定／退屈の
どちらに働いたか、格子和音の色が魅力かを短い A/B で記録。
G1 や stability の最大化だけで v3 を合格扱いしない。
受入条件は**両 equave の実曲で5軸が利用可能**、少なくとも
一つの非ゼロ高次軸を持つ Project が各 cohort に存在、
指定した閉／開 cadence が Plan と Project の双方で一致、
PCM 検査済みの試聴曲があること。生成成功率と失敗理由は
試聴選抜前の母数で報告する。
