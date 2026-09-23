# 格子音高を聴感上の表現にするための探索案

Status: 設計検討。生成・コンパイル契約の変更は別途版を設ける。和声構成の実装修正とは独立の検討。

## 現状と目的

格子上の整数ベクトルと exact ratio はすでに Project に残るが、確認時点の full-song の
`full_song_generation_v1.json` は equave `2/1` に対する 12 分割 3 形
`[0,4,7]`, `[0,3,7]`, `[0,5,7]` と、equave `3/1` に対する 19 分割の同じ 3 形を
参照する。現行 lowerer は構造サンプラーの和声 intent を一つ選んで使う。
8 seed の `none` コホートでは 88 件の resolved chord がすべて 3 声で、
voice-offset 配列は 8 形だった。root だけを動かしても和音の音程構造は大きく変わらない。
4 音参照自体は sampler の 2〜8 step 契約と resolver で表現可能だが、現行
full-song 候補表に 4 音形はない。別の和声実装作業とは、この候補表・voice count・
resolver の決定を境界として連携する。

melody は `chord_member` 関係と解決済み和音の target ordinal 0〜2 に固定され、
bass は section root、texture も root の直接ベクトルを主に使う。
非和声音の格子内選択はまだない。「12-EDO の形を JI で近似しただけ」の状態を
脱するには、和音そのものと、和音に対する各パートの振る舞いを別々に拡げる。

## 1. 和声を構成する候補群

`2/1` equave の現行 3・5・7 generator 格子で試せる候補:

| 系列 | exact ratio の例 | 聴感上の仮説 |
| --- | --- | --- |
| 倍音の切片 | `1/1, 5/4, 3/2, 7/4`（4:5:6:7） | 低次倍音を共有する一体感と、7/4 の独自の終止色 |
| 7-limit の近接領域 | `1/1, 8/7, 7/6, 3/2` 等から部分集合 | 8/7（約231¢）と 7/6（約267¢）の中立的な動き |
| 共通音を持つ隣接格子セル | 2〜3 音を固定し、残る声部を短い格子経路で移動 | 和音名の転回より、保持声部と色の変化を知覚させる |
| product-set / hexany | 選んだ 4 因子の 2 因子積から、equave 正規化した 6 音 | 一つの pitch collection の中で複数の和音と旋律を共有 |

これらは「必ず快い音程」という断定ではなく、**登録可能な候補群**とする。
基準の `12/19` 分割形も対照群に残す。`11/8`（約551¢）等の 11-limit 色は
generator `11/1` を含む **別の lattice domain** を明示した場合だけ試す。
現行 3・5・7 domain で 11-limit 音を近似して「11-limit」と呼ばない。
また `3/1` equave では 1200¢ 周期と同一視せず、その equave 長での正規化と
register の管理を別に行う。

12-EDO に nearest mapping したとき、`7/4` は約969¢、`8/7` は約231¢、
`7/6` は約267¢、`81/80` は約21.5¢。単に「12-EDO から何¢離れるか」を
最大化せず、持続時間・声部・前後の解決が聴こえる位置に置く。

## 2. 和声進行: 格子上の経路として扱う

各 phrase で `home → departure → arrival` を一つの固定コード名列に写す代わりに、
以下の経路型を seed と profile から選ぶ。

1. **common-tone orbit**: 保持音を明示し、他の声部だけ 7-limit 近傍を回り、
   phrase 終端で保持音へ戻す。
2. **spectral expansion / contraction**: 狭い倍音集合から 7/4 を含む開いた
   4 音配置へ広げ、解決時には声数または register を減らす。
3. **comma excursion**: `81/80` や `64/63` 程度の小さな差を持つ二つの経路を、
   一声部の遅い保持・ずれ・回帰として使う。短い音を無作為に散らさない。
4. **collection pivot**: hexany 等の集合を共有したまま中心となる subset を変え、
   bass と melody の帰着点で中心移動を明確にする。

候補評価には exact-ratio 一致、共通音、各声部の格子 L1 と cents 移動、
register・音域、低域の濁り、経路の帰着を**別の量**として保持する。
和声名、純正律誤差、12-EDO 類似度を一つの総合点にしない。
隣接和音だけでなく phrase 終端と次 section 冒頭を跨ぐ経路を評価する。

## 3. パートに与える格子内の自由度

現行の `melody_intent` は `relation: chord_member` のみで、compiler は
melody note 全体を覆う harmony occurrence がちょうど一つあることを要求する。
和声から外れる音を無言の例外として足さず、次の **明示的な関係と解決先**を
新しい契約で持たせる。`MELODY_HARMONY_CONFLICT` を欠けた和声に対する
音高の自動丸めで回避しない。

| role | 格子内で許す動き | 強い拘束 |
| --- | --- | --- |
| bass | root / common tone、弱拍から次 root への approach、短い neighbor | phrase 境界や強拍の到達を明示。低域での近接濁りと kick との衝突を制限 |
| melody | chord member、passing、neighbor、先取り、suspension と解決 | source vector、delta vector、active/target chord、解決時刻を保存。強拍の非和声音は持続・帰着を計画 |
| pad / texture | drone、保持共通音、ゆっくりした comma shift、集合内の異色音 | melody の register を塞がず、長い不協和の時間と音量を制御 |
| piano / counterline | 7-limit 色の応答、遅延解決、裏拍の短い lattice neighbor | foreground と同じ音域で同時に密集させない |

`passing` は単純な「格子座標距離 1」ではない。前後の chord / collection に
対する関係、cents 移動、音域、accent、解決方向を同時に持つ。
非和声音も exact ratio / vector / equave exponent で出力し、
`chord_index` と pitch provenance で周囲の和声との関係を追跡する。
許容する割合を全イベント一律にせず、phrase の pickup / body / cadence と
role によって変える。cadence の root、終端の共通音、motif identity は lock できる。

## 4. 試験と診断

まず同一 seed・同一 renderer / timbre・同じ最大 polyphony で次の対照を作る。

- 現行の 3 音 12/19 分割参照形。
- 7-limit 倍音集合＋common-tone orbit。最初は bass と harmony のみ変更。
- 前項に melody の passing / suspension を追加。
- collection pivot と、控えめな texture の comma excursion を追加。

`G0` / Native JI / PIL の成立、exact ratio と event provenance の検証を保つ。
G1 v1 は form や motif の診断であり、**格子音の知覚可能性を測る尺度ではない**。
12-EDO から 10¢ 以上離れた音のイベント数・distinct pitch class 数・声部時間比と
ギャップを Project の exact ratio から計算する独立診断を導入した。
この値は高いほど良いスコアではなく、探索に使用する場合だけ外部指定の目標比率へ
近づける（`docs/composition_g1_exploration.md`）。
追加の非権威的診断として、(a) 12-EDO から十分離れた音の実際の発音時間と
foreground 露出、(b) chord tone 以外の前後関係と解決率、(c) 7-limit 等の
pitch-collection 利用率、(d) 経路の共通音・移動量・帰着、(e) 低音域の粗さと
register 衝突を報告する。12-EDO との差だけで探索すると、意図のない外れ音へ
最適化してしまう。音声試聴は少数の対照ペアで方向性を確認し、G2 の大規模
ブラインド回答を各探索反復の前提にしない。

## 実装境界

和声構成側: 候補 collection、3/4 音 intent、voice offsets、進行経路と
`resolved_chords` の exact-ratio authority。別作業が担当する領域。

パート側: 新しい格子内関係を持つ melody / bass / texture intent、解決先・時間、
pitch provenance と validator。現在の `chord_member` だけの schema を
黙って拡張せず、version を上げて既存 Project と判別可能にする。

試験側: 同 seed の対応、ローカル WAV / MIDI の再現性、12-EDO 丸めがないこと、
G0/G1 と格子固有診断の並列レポート。和声構成の変更が揃ってから具体的な
candidate fixture を固定する。
