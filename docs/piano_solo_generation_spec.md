# ピアノ独奏（2部構成）楽曲生成仕様 v1

Status: **設計案・未実装**。CompositionPlan 2.0、SongProgram 0.2、Project、
既存 G0 と exact-ratio authority の上に追加するピアノ専用探索契約。

## 1. 目的と対象

ピアノ**のみ**による楽曲生成を確立する。ドラム・ベース・テクスチャを排し、
2 つの独立トラック（コード進行パート＋主旋律パート）で構成される 2 部構成を
生成する。両トラックは同じピアノ音色を使う。

- **コード進行パート** (`trk_piano_chords`, role `harmony`): 和音進行を鳴らす。
  機械的に鳴らないよう、各 voice の onset を微妙にずらし（rolled chord）、
  休符を適切に挿入する。
- **主旋律パート** (`trk_piano_melody`, role `melody`): motif を再生しつつ、
  Arpeggiation・Scale runs・melodic figuration などで flowing な旋律を作る。

### 確定した設計判断

| 項目 | 選択 | 内容 |
| --- | --- | --- |
| Q1 2部構成の表現 | **B** | 2 つの独立トラック（コード＋旋律）、両方ピアノ音色 |
| Q2 1000seed の速度 | **A** | ピアノ専用高速パイプライン（2D 格子・小 bounds）＋ WAV skip |
| Q3 G0 無音時間 | **A** | PCM 1s 無音チェック＋coverage gate を撤廃、休符数ルールを新 G0 hard check に |

### 既存作業との関係

- symbolic（WAV skip）生成: `f79774ce`（`--skip-wav`、symbolic G0）
- 1000seed cohort＋clustering＋代表抽出: `a391cdfc`（`cluster_symbolic_songs.py` 等）
- cluster 可視化: `b311a474`（`visualize_symbolic_clusters.py`）
- 局所 fine-tuning 仕様: `08ba4d31`（`composition_seed_finetuning_spec.md`）

本仕様はこれらの上に、**ピアノ専用**の生成・検証・探索を追加する。
既存のフルバンド生成（`generate_composition_song.py`）は変更しない。

## 2. 2部構成（トラックとロール）

| Track | role | instrument | 内容 |
| --- | --- | --- | --- |
| `trk_piano_chords` | `harmony` | `piano_solo` | 和音進行（harmony_intent_cell）。rolled chord＋休符 |
| `trk_piano_melody` | `melody` | `piano_solo` | 主旋律（melody_intent）。motif＋figuration |

- 両トラックは同じ `piano_solo` 音色（GM program 0）。MIDI では 2 つのトラック。
- ドラム・ベース・テクスチャのトラックは存在しない（`active_roles = [harmony, melody]`）。
- 旋律は和声に厳密に束縛される（1 note span につきちょうど 1 つの active harmony
  occurrence、同一 section）。コードパートの resolved chord がその束縛対象。
- `piano_solo` 音色は既存 `trial_piano`（`piano_part.py`）の timbre を再利用し、
  role を `harmony`／`melody` に分けた 2 エントリとする。

## 3. 高速パイプライン（2D 格子・WAV skip）

既存フルバンドの 3D 格子 `[3/1,5/1,7/1]`・bounds `[-4,4]^3`（9^3=729 点）の
BnB 和声探索が速度と失敗率（`PROGRESSION_NO_PATH`）のボトルネック。
1000seed cohort では 292/1000 成功、失敗の 689 が `PROGRESSION_NO_PATH`。

ピアノ専用パイプラインは探索空間を縮小し、速度と成功率を同時に改善する。

- **格子**: 2D `[3/1, 5/1]`、equave `2/1`、bounds `[-2,2]^2`（5^2=25 点）。
  長音階・短音階の triad／7th は `[3/1,5/1]` で解決可能。
- **register**: `[-1200000, 3600000]` millicents（既存 piano_part と同一）。
- **WAV skip**: 1000seed 試験は `--skip-wav`（symbolic/MIDI のみ）。代表抽出の
  少数曲だけ WAV 化して試聴する。
- **目標**: seed あたり数秒〜数十秒、1000seed が現実的。`PROGRESSION_NO_PATH`
  失敗率を既存 70% から大幅に下げる（2D・小 bounds で探索空間が 1/29）。

## 4. コードパートのヒューマナイゼーション

機械的な同時発音・完全規則リズムを避け、人間的な演奏にする。全て seed 由来の
決定論的オフセット（再現可能）。

- **rolled chord**: 各和音の voice を onset 順に微小オフセット（例: voice0 `+0`,
  voice1 `+Δ`, voice2 `+2Δ`、Δ は seed 由来の 5〜20ms 相当 tick）。style brisé
  の破弦効果。`harmony_intent_cell` の voice 発音に per-voice onset offset を追加。
- **休符挿入**: 和音の一部 voice を確率的に欠落（短休符）。小節内の無音時間を
  制御し、G0 の休符数ルール（§6）と整合させる。
- 旋律パートにも同様の微小 onset 揺らぎを適用可能（v1 はコードパート中心）。

## 5. 主旋律のフィギュレーション

旋律を `chord_member` のみから解放し、flowing な旋律表現を広げる。
SP0 `melodyPoint` の `relation` を enum 化し、compiler が各 relation を
格子比に解決する。

| relation | 解決方法 | 表現 |
| --- | --- | --- |
| `chord_member` | `exact_ratios[member]`（既存） | 和音音のアンカー |
| `passing` | 隣接和音音間の step 比を最近接格子点に解決 | 経過音（stepwise） |
| `neighbor` | 和音音の上下 step 比を最近接格子点に解決 | 装飾音（返り音） |
| `scale_degree` | 現行 key の diatonic 音階の格子点 | scale run |

- **Arpeggiation**: 同一 chord occurrence 内に `chord_member` 点を上/下順に
  複数配置（root→3rd→5th→octave 等）。新 relation 不要（順序で表現）。
- **Scale runs**: `scale_degree` 点を連続配置（上行/下行）。
- **double stop**: 同一 onset に `chord_member` 2 点（3度/6度）。
- 探索（sampling）は section の function/energy/density に基づき figure を選択。
  `passing`／`neighbor` は「最近接格子点」探索が必要（2D 格子では低コスト）。

## 6. G0 の修正（休符数ルール）

`assess_completed_song`（9 hard checks）をピアノ用に調整した
`assess_piano_solo` を新設する。Q3=A に従い無音時間指定を撤廃し、
休符数ルールを新 hard check にする。

| Check | 既存 | ピアノ専用 |
| --- | --- | --- |
| `bars_16_to_64` | 保持 | 保持 |
| `sections_3_to_8` | 保持 | 保持 |
| `every_section_realized` | 保持 | 保持 |
| `minimum_three_core_sounding_roles` | ≥3 | **`minimum_two_core_sounding_roles`**（harmony+melody） |
| `symbolic_coverage_at_least_8500_bp` | 保持 | **撤廃**（coverage gate） |
| `no_fully_silent_one_second_window` | 保持（PCM） | **撤廃**（無音時間指定） |
| `arrangement_development_passed` | 保持 | **撤廃**（2ロールでは厳しすぎる） |
| `polyphony_within_track_limits` | 保持 | 保持（2トラック合計で判定） |
| `non_identity_transformed_recall_across_sections` | 保持 | **撤廃**（ピアノでは満たしにくい） |
| `rest_count_rule`（新設） | — | 小節あたり休符 ≤ 四分、全休符禁止 |

- **`rest_count_rule`**: 各小節の無音時間（event が無い tick の合計）が四分音符
  1 分（= 1 beat）以下、かつ全小節無音（全休符）の小節が存在しない。
  symbolic（event 列）から判定し、PCM に依存しない。
- `--skip-wav` 生成でも全 check が評価可能（PCM 非依存）。
- `archive_eligible` は WAV 化＋PCM check 通過後にのみ true（既存と同一方針）。

## 7. 1000seed 試験＋clustering＋代表抽出

- **生成**: `run_piano_solo_cohort.py --seeds 1000 --workers N --skip-wav`
  → `local_authority/piano_solo_symbolic_1000/seed-NNNN/`（symbolic artifacts）。
- **clustering**: `cluster_symbolic_songs.py`（既存、`ROLES` に `piano` 含む）を
  ピアノ cohort に適用。form/和声/melody contour の symbolic 特徴でクラスタ化。
- **代表抽出**: `render_symbolic_cluster_representatives.py`（既存）で各 cluster の
  代表を 1 曲選び、WAV 化して試聴用にする（少数だけ WAV）。
- **可視化**: `visualize_symbolic_clusters.py`（既存）で coverage/分布を確認。
- 成功数・失敗率（`PROGRESSION_NO_PATH` 等）・cluster 数を cohort report に記録。

## 8. 実装計画

### 新規ファイル

1. `docs/piano_solo_generation_spec.md` — 本仕様。
2. `backend/app/songprogram/piano_solo.py` — ピアノ専用ロジック。
   - `build_piano_program(plan, lattice)`: 2トラック（harmony+melody）の SP0 program。
   - `humanize_chord_voices(...)`: rolled chord（per-voice onset offset）＋休符。
   - `melody_figuration(...)`: arpeggio/scale run/passing/neighbor/double stop。
3. `backend/tools/generate_piano_solo.py` — ピアノ専用生成ツール
   （`--seed --profile --output --skip-wav`）。plan 生成→2トラック program→
   compile（高速格子+figuration+humanization）→`assess_piano_solo`→MIDI。
4. `backend/tools/run_piano_solo_cohort.py` — 1000seed cohort runner
   （`run_composition_generation_cohort.py` のピアノ版）。
5. `backend/songprogram_conformance/profiles/piano_solo.json` — ピアノ profile
   （2D 格子・小 bounds、harmony+melody の part coordination）。

### 変更ファイル

1. `backend/app/songprogram/compiler.py` — melody resolution を新 relation
   （passing/neighbor/scale_degree）に対応、harmony に per-voice onset offset。
2. `backend/app/songprogram/song_validity.py` — `assess_piano_solo` 新設
   （§6 の check 表）。
3. `backend/songprogram_conformance/schemas/song_program_0_2.schema.json` —
   `melodyPoint.relation` を enum 化（chord_member/passing/neighbor/scale_degree）、
   `scale_degree` 用の `degree` フィールド追加。

### テスト

1. `backend/tests/test_piano_solo.py` — 2トラック program の schema 検証、
   figuration の格子解決、humanization の決定論性、`assess_piano_solo` の
   休符数ルール（四分上限・全休符禁止）、2D 格子の `PROGRESSION_NO_PATH` 低減。

### 実装順序

1. **2トラック program＋高速格子**: `build_piano_program`＋`piano_solo.json`。
   単一 seed で compile→MIDI が通ることを確認（既存フルバンドと独立）。
2. **G0**: `assess_piano_solo`（休符数ルール）＋テスト。
3. **figuration**: SP0 schema 拡張→compiler の relation 解決→テスト。
4. **humanization**: per-voice onset offset＋休符→テスト。
5. **cohort**: `run_piano_solo_cohort.py` で 1000seed（WAV skip）→clustering→
   代表抽出（WAV）→可視化。

## 9. 調査: ピアノ主旋律表現の技法（実装への反映）

実装前にピアノ主旋律表現の技法を調査した。主要な技法と本仕様への反映:

- **Arpeggio（破弦）**: 和音の音を順に発音（上行/下行/上下）。style brisé
  （破弦様式）はピアノの代表的な伴奏・旋律技法。→ §5 の Arpeggiation、
  §4 の rolled chord（コードパートの破弦）。
- **Scale runs（音階回し）**: 音階を連続して上行/下行。フレーズ接続・装飾。
  → §5 の `scale_degree`（diatonic 音階の格子点）。
- **Passing tone（経過音）**: 2 つの和音音をつなぐ stepwise な非和音音。
  flowing な旋律の要。→ §5 の `passing`（最近接格子点）。
- **Neighbor tone（返り音）**: 和音音の上下 1 step に移って戻る装飾音。
  → §5 の `neighbor`（最近接格子点）。
- **Double stop（2音同時）**: 旋律に 3度/6度などの 2 音を同時に重ねる。
  → §5 の double stop（同一 onset に `chord_member` 2 点）。
- **Leap + stepwise resolution**: 跳躍後に同方向の stepwise で解決する
  古典的旋律原理。→ figuration の contour 制約（跳躍後の解決方向）。
- **Rhythmic figuration**: 裏拍・付点リズムによる律動変化。→ §4 の休符挿入、
  rhythm_cell の回転（既存 `rotate_rhythm`）。

これらは全て exact-ratio（格子比）で解決可能であり、JI/lattice-native の
音高体系と整合する。`passing`／`neighbor` の「最近接格子点」は 2D 格子では
低コスト（§3）。

## 10. リスクと未決事項

- **最近接格子点の解決コスト**: `passing`／`neighbor` は target 比に最も近い
  格子点を探索する。2D・小 bounds では低コストだが、bounds 拡大時は注意。
- **`PROGRESSION_NO_PATH` の残存**: 2D・小 bounds で大幅減を見込むが、
  0% とは限らない。cohort report で失敗率を必ず報告する。
- **2トラックの polyphony**: G0 の polyphony sweep はトラック単位。2 つの
  ピアノトラックの同時音数を `maximum_polyphony` で合計管理する。
- **SP0 schema 変更の保護**: `song_program_0_2.schema.json` は oracle 管理の
  保護ファイル。relation enum 化は契約変更として commit（oracle-maintainer 手順）。
- **代表抽出の WAV 化**: 1000seed は WAV skip だが、代表（少数）は WAV 化して
  試聴する。stock catalog の周波数 envelope に収まらない曲は preview と明記。



