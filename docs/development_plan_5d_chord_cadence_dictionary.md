# 5D格子和音辞書・安定度・カデンツ試験 Dev Plan

Status: **次期実装の仕様／未実装**。本計画では新規の独立プロジェクトとして
「5D Harmony Dictionary」を作る。既存の 5D コンパイラ権威、
Prime-Limit Explorer と SongProgram は参照するが、既存 golden／seed の
意味を上書きしない。最終成果は API・永続辞書・カデンツ試験・Web UI。

## 1. 方針と境界

- **新規作曲 profile の最低次元は 3D、辞書の対象は 5D**。
  現行 piano solo v1 の 2D `[3/1,5/1]` は歴史的な再現用として残し、
  次版 profile から選択肢として廃止する。full-song の現行 3D も保持。
  2D の SongProgram 0.2 構文や legacy golden を全面禁止する変更ではない。
- 二つの equave `2/1`（octave; 逆向き `1/2` と同じ同値類）と
  `3/1`（tritave; 逆向き `1/3` と同じ同値類）を**別 authority**として扱う。
  generator が equave そのものにならないよう、初期 5 軸は
  octave: `[3/1,5/1,7/1,11/1,13/1]`、
  tritave: `[2/1,5/1,7/1,11/1,13/1]`。
  異なる equave の pitch class／辞書 entry を暗黙に統合しない。
- 3音／4音和音について、12-EDO の既知の chord template との
  **類似度**と、tonic を指定した**文脈依存の安定度**を記録する。
  比率、5D vector、1D 軸への射影誤差、声部進行をそれぞれ保持する。
  射影／12-EDO 近似は検索 index。鳴らす音と最終の成否判定は
  元の exact ratio を使用する。
- 既存 5D GEN0-B fixture は後半3軸の bounds が `[0,0]` の
  形式・接続検証。11/13 軸を実際に動かす和音の辞書と音楽的評価は
  この新規プロジェクトで別途検証する。

## 2. 探索範囲：generator の equave 近似ループ

equave `E>1`、generator `g>1` の n 回移動について
`d_E(n,g)=min_{k∈Z}|1200 log2(g^n/E^k)|` cents とする。
`n>=1` で `d_E<=10` を満たす**最初の** `(n,k)` を
`loop_steps[g]` として記録し、正負両方向を同じ周期長で扱う。
0 が自明解になるので n=0 は含めない。境界判定は単位を
millicent に固定し、Decimal／有理数入力の再現可能な計算と
丸め規則を version で seal する。loop は**近似**であって
`g^n=E^k` という数学的な等式ではない。

参考として 10 cent 条件の初回 n（近似計算、実装の fixture では再計算）:

| equave | 軸順 | 初回 n |
| --- | --- | --- |
| `2/1` | 3, 5, 7, 11, 13 | 53, 59, 109, 37, 10 |
| `3/1` | 2, 5, 7, 11, 13 | 84, 157, 153, 104, 3 |

計算の停止上限は例えば `n<=256` の versioned policy とする。
その間に条件を満たさなければ `LOOP_NOT_FOUND_WITHIN_LIMIT` として
辞書生成を止め、勝手に半径を拡張しない。ループ点を超える探索はしないが、
**各軸を `[-n,n]` にした5D直積を列挙する意味ではない**。
初期の 1D index は各軸について `n=0..loop_steps[g]-1` の
equave-reduced pitch class を作り、負方向は等価表現として provenance を残す。
元比率の高さ、register、和音の構成音間差を失わない。
小さい差での pitch-class merge（<=10 cent）と loop の判定は別物。

5D の全直積／全和音列挙は行わない。候補 root／register／和声音数、
座標高さ（例: Σ|v_i|）、distinct pitch class、max span と
`maximum_domain_points`／GEN0-B の座標・配置予算を**生成前**に検査。
上限超過なら候補を分割・局所生成または明示的に拒否する。
loop 長は axis sampling の上限に使い、複数軸の同時変化は
小さな root 周辺の隣接候補に限定して、必要時だけ問い合わせる。

## 3. 12-EDO 参照、軸別辞書、5D 和音の射影

各軸 `g_j` の 1D point に `(n, original_ratio, reduced_ratio,
equave_exponent, absolute_cents, nearest_12edo_semitone,
signed_12edo_error_cents)` を保存する。12-EDO の丸めは
**絶対周波数の半音グリッド**で行い、`2/1` と `3/1` を混同しない。
tritave は約 1901.955 cents、12-EDO の 19 半音は 1900 cents。
周期を12 pitch class として畳み込むと 3/1 同値と整合しないため、
tritave 側も absolute cents と E=3 の位相を別々に保存する。

12-EDO template は 3音（major/minor/diminished/augmented/sus 等）と
4音（dominant7/major7/minor7/half-diminished 等）を versioned な
root-relative 半音集合として定義する。候補は root を固定して
音高の重複を排し、permutation／転回形の中で cent 残差が最小の対応を
求める。`tritave` での比較は root-relative **実際の音程幅**で行い、
1900 cents 近傍を機械的に 1200 cents と同一視しない。
どの template にも一定の誤差以内で合わないものは `other/unknown`。
template 名は類似性の診断であり JI 和音の同一性ではない。

軸別 1D 辞書は `[equave, generator, 3|4 voices, version]` を鍵に、
候補の相対指数 tuple／exact ratios、12-EDO 類似度、残差、
interval vector、純正な音程関係、採用の理由を持つ。
全 `C(n,4)` を許すのではなく max span、root からの高さ、
interval diversity、個数 cap を事前に適用して bounded streaming で作る。
同じ 12-EDO 近似に落ちる異なる exact chord は**一つに潰さず**、
canonical pitch-class key の配下に複数 variant として索引する。

任意の 5D chord `V=(v_1,...,v_m)`（m=3/4）を評価するときは:

1. root を指定し、各 tone の root-relative exact ratio と register を算出。
   root 不明なら複数 root 仮説を試し、root の不確実性を報告する。
2. **一つの共通軸** `j∈0..4` を選ぶ。各 tone をその軸の 1D list の
   最も近い point（必要なら equave lift を含む）に独立に対応付ける。
   各音ごとに別軸を選んで「一つの軸の和音」と称しない。
3. 軸の誤差は音高差の絶対値／RMS と最大誤差、重複による声数欠落、
   和音内 interval の崩れを記録。まず声数欠落・max-error gate、次に
   RMS 最小、同点なら max-error→軸順→辞書 key で決定論的に選ぶ。
   `projection_error_limit_cents`（初期は 25 cents の**仮値**）を超えたら
   `projection_unreliable` とし、辞書の分類を確定しない。
4. 選んだ axis key で候補を検索し、**元の exact 5D chord**を使って
   root-relative interval／12-EDO との類似度／安定度を再計算する。
   近似からの最終分類と exact 再評価を両方返し、食い違いを記録。
   射影不能な場合も bounded な on-demand exact 3/4音評価を試み、
   予算切れは失敗として返す。

これは 5D 和音を単一軸に**完全に同型写像する主張ではない**。
異なる軸の組合せで初めて出現する和音が索引から漏れる率を、
小さな全直積 fixture と on-demand exact baseline で測る。
最初の試験で recall が低ければ top-2 軸検索を導入する等、
辞書 index を改訂し、音を消して数字だけ合わせない。

## 4. 安定度 1 次元値と T／D／S 試験

候補仕様: `stability_q∈[0,10000]`（高いほど**指定した tonic に
対して**安定）。同じ chord でも tonic を変えれば値が変わる。
versioned scoring table で `R`: tonic に対する bass/root の近さ、
`C`: chord 内 exact interval の協和／roughness 代理量、
`V`: tonic 和音への最小声部移動、`F`: 12-EDO 参照への類似度を
**別々に** 0..1 で出力する。初期**較正用**の集約例は
`stability_q = round(10000 * (0.30 R + 0.30 C + 0.25 V + 0.15 F))`。
roughness proxy の interval table、評価対象 tonic chord、距離から
0..1 への写像、丸め、全重みは versioned profile に固定する。
ここでの 12-EDO 類似度の比重は仮値で、格子固有和音に不当に
低い値を与えないか別途測定する。導音相当の傾向音、次和音への
実際の解決、拍位置は別の `contextual_arrival_q` として記録し、
まだ無い次和音を単体和音辞書の score に混ぜない。
最初から「完全協和=常に tonic」と置かない。

`tonic`／`dominant`／`subdominant` の三分類を**スカラーだけで
必ず確定する保証はない**。同程度に安定した I と IV や、
root 同じで機能の異なる sus 和音があり得る。実験として
`stability_q >= T_high` → tonic 候補、
`stability_q <= D_low` → dominant 候補、
中間 → subdominant 候補、というしきい値を held-out seed で較正し、
`D_low < T_high` とする。候補決定後に root の tonic からの相対位置、
先行／後続和音と期待する解決方向で条件付ける。
不一致や低 margin は `ambiguous/other`（棄却でなく説明付き）とする。
最終 report には**しきい値のみの3分類**と**文脈付き分類**の両方、
混同行列、coverage、I/IV などの誤判定事例を残す。
しきい値だけで区別不能なら数値一本で三分類する前提を修正し、
複数特徴と cadence context を採用する。12-EDO label と G1 は教師の
代わりにせず、機能の比較用参照と短い聴取判定を使う。

## 5. カデンツ生成と試験

tonic root／equave／cadence 種別を指定し、辞書から
`T→D→T`、`T→S→D→T`、open な `…→D`、
格子固有の代替進行を 2～4 和音（3/4音混合可）で候補化。
生成器は chord stability の起伏、最後の着地、bass/root の
運動、声部連結（exact cents）、旋律の傾向音の解決、
拍節上の着地点、反復との接続を**独立に**診断する。
格子らしい代替候補を 12-EDO 型の一致度だけで排除しない。
進行が解決不能・音域外・`PROGRESSION_NO_PATH` なら原因を記録。

ゴールデン試験は equave 両方の3/4音、12-EDO 近傍と格子固有音、
非ゼロの第4・第5軸、境界での無帰着、しきい値上下、
別 tonic で label が変わる例、同じ chord の文脈変更、
安定度上昇でも聴感上は未解決な例を含む。
最後の例では自動採用しない。少数の WAV を exact ratio で
render し、同 seed／同テンポ／同 register の 12-EDO 近似候補と
blind A/B で「帰着／緊張／曖昧」を確認する。
既存 [聴取ギャップの診断](lattice_harmony_cadence_listening_review.md)
の build→drop 境界も回帰試験に使う。

## 6. 保存、API、Web UI

`backend/app/harmony_dictionary/` に数学・projection・feature・cadence
の純粋関数、`backend/tools/build_5d_chord_dictionary.py` に
辞書 builder と read-only verifier を置く想定。
辞書は schema/version、equave、軸順、loop policy、12-EDO template 版、
stability profile hash、探索 cap、件数、失敗件数、項目の exact ratio／
vector／近似 error／provenance、全体 hash を保持し、equave 別に seal。
atomic write／再生成 byte parity／破損時 fail closed。
境界ごとに入力を限定した API の初期案:

| endpoint | 入力と出力 |
| --- | --- |
| `GET /api/harmony-dictionary/config` | 対応 equave、軸、辞書 version、上限 |
| `POST /api/harmony-dictionary/axis` | equave／軸 → loop と1D pitch・近似表（件数制限） |
| `POST /api/harmony-dictionary/chords` | equave／軸／声数／絞込 → 12-EDO template と安定度のページ結果 |
| `POST /api/harmony-dictionary/evaluate` | tonic／3または4個の5D vector＋register → 5軸誤差、選択軸、exact 再評価、ambiguous 理由 |
| `POST /api/harmony-dictionary/cadences` | tonic／目標終止／seed／制限 → 複数の進行、T/D/S 候補、安定度曲線、失敗 |

Web UI は既存 `/prime-limit-explorer` と同じ FastAPI の static workbench
方式で新規 `/harmony-dictionary` を追加。equave 切替、5軸それぞれの
loop・12-EDO 差の図、root 相対 chord と元の5D座標、候補軸の
射影誤差／音程、T/D/S のしきい値と曖昧件数、
stability 曲線、cadence タイムラインを表示する。
同じ chord／cadence の **exact ratio／12-EDO 参照**を別ボタンで
Web Audio 試聴し、音量を揃える。保存は JSON とし、音・座標・
profile hash を含めて再現可能にする。重い builder は request 内で
同期実行せず、構築済み辞書への read-only 検索か制限付き job にする。
軸／equave 変更時の stale request 排除、キーボード操作、長い表の
ページングと予算超過時の理由表示も UI の受入条件。

## 7. 実装マイルストーンと受入ゲート

1. **Authority と loop**: equave×generator 別の最初の 10 cent loop、
   5D 非ゼロ高次軸、算術・資源境界・同 seed 再現性。既存 v1 golden 不変。
2. **軸別辞書**: 3/4音、12-EDO template、bounded streaming、hash／
   read-only verifier、失敗数。全 axis に少なくとも複数の異なる和音。
3. **任意5Dの評価**: 5軸への共通軸射影、exact 再評価、小領域での
   全直積との recall／誤分類率を測定。25 cent 仮 gate は結果で較正。
4. **安定度／cadence**: held-out しきい値、unknown と混同行列、
   tonic 指定への感度、解決パターン、少数 WAV A/B。
5. **Web UI と統合**: 5 API、同一条件試聴、保存／再読込、
   5D→3D以上の新 piano profile への接続試験。

最終受入では 2/1・3/1 の双方について、各 generator の loop を
10 cent 以内で独立再計算した fixture、12-EDO 同名で異なる exact
chord の保存、単一共通軸に射影不能な反例、安定度の tonic 依存性、
unknown を含む三分類の混同行列、非ゼロ高次軸のカデンツ生成を確認する。
API の入力上限／hash 不一致／空辞書を失敗として検証し、ブラウザでは
equave 切替時の stale response、候補選択→exact/12-EDO 試聴→JSON 保存
→再読込の一連の操作を確認する。実際の比較音声の ratio と
画面の original vector が一致することを受入条件にする。

歌唱可能な範囲と生成速度の検証なしに 5D を piano に一斉投入しない。
特に `7^5` の直積は現行 GEN0-B の上限を超えるので、辞書の
索引と実曲コンパイルの探索予算は別に設ける。2D の新規使用停止は
新 profile の generation manifest の検査として実装し、既存の
2D song の再生・比較可能性を保持する。

既存の接続点: `backend/app/songprogram/compiler.py`、`resolver.py`、
`exploration_generation.py`、`backend/app/prime_explorer.py`、
`backend/app/main.py`、`backend/app/static/prime_limit_explorer.html`、
`docs/gen0b_5d_authority_contract.md`、
`docs/lattice_dimension_and_generator_policy.md`。
