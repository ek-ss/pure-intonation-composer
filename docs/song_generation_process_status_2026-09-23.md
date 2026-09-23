# 楽曲生成プロセスと実装状況（2026-09-23）

## 1. 目的と範囲

この文書は、CPS（Pure Intonation Composer）の**現在の楽曲生成プロセスの手順**と
**実装状況**を整理したスナップショットである。2026-09-23に、リポジトリの内容
（`main`、最新コミット `4ac58d6b` 2026-09-22、および作業ツリーの未コミット変更）
に基づいて作成した。

契約文書（`docs/` 内の各 contract、`status.md`）と矛盾する場合は契約文書が優先
される。本ドキュメントは現状の要約であり、規範（normative）文書ではない。

## 2. プロジェクト概要

CPS は rational tuning（純正律）のための決定論的作曲ワークベンチである。
CPS（Combination Product Set）や Euler–Fokker 素材を生成し、Johnson 和音グラフ
を移動しながら和声／ベース／メロディを作曲し、リズムを作り、WAV をレンダリング
し、MIDI／Scala／JSON をエクスポートする。すべての確率操作は同じ seed で同じ
出力を返す（決定論）。

リポジトリには2つの層が共存する。

1. **ブラウザワークベンチ層**（`backend/app/`）— Compose、Rhythm、Lattice Lab、
   Vital Pack、各 fractional composer など（development plan の G1–G18 機能群）。
   対話的な実験環境であり、プロセスローカル（再起動で状態消失）。
2. **SongProgram 生産層**（`backend/app/songprogram/`）— 契約・conformance pack・
   評価ゲートを備えた決定論的 full-song 生成パイプライン。**現在の楽曲生成の
   メイン軸はここ**（§4）。

## 3. リポジトリ構造

```text
CPS/
  backend/
    app/
      main.py                FastAPI アプリ（REST + WebSocket）
      songprogram/           SongProgram 生産パイプライン（§4 の各ステージ）
      composition/ rhythm/ audio/ exporters/ generators/ graphs/ ...
                           ワークベンチ用エンジン（G1–G18）
      static/                ブラウザワークベンチ（vanilla JS、ビルドなし）
    songprogram_conformance/
      schemas/               JSON Schema 契約（closed、自己ハッシュ）
      profiles/              生成／realization／exploration プロファイル
      fixtures/              golden / negative / boundary fixture、oracle
    tools/                   CLI エントリポイント（生成・評価 cohort）
    tests/                   pytest スイート
  docs/                      契約・計画・status（本ドキュメント）
  local_authority/           ローカル生成成果物と評価 authority（git 管理外）
```

`backend/build/lib/` はパッケージ生成物であり、実装状況の判定に使わない
（`docs/README.md` の Source Boundaries 参照）。

## 4. 現在の楽曲生成プロセス（メインパイプライン）

現在のメインの楽曲生成プロセスは **CompositionPlan 2.0 パイプライン**である。
広い乱択から偶然の曲を待つのではなく、時間階層を上から下へ生成する
（form → phrase → harmonic trajectory → motif）、その後 SongProgram へ
lowering し、compile → render → evaluate する。

### 4.0 エントリポイントとコマンド

単一曲（リポジトリルートから）:

```bash
backend/.venv/bin/python backend/tools/generate_composition_song.py \
  --seed 0 --piano-style mixed --output local_authority/composition_generation_v2_seed0
```

cohort（複数 seed、並列）:

```bash
backend/.venv/bin/python backend/tools/run_composition_generation_cohort.py \
  --seeds 24 --workers 8 --output local_authority/g1_new_generator_24_v1
```

入力（いずれも自己ハッシュの closed payload）:

| オプション | 既定値 | 内容 |
| --- | --- | --- |
| `--profile` | `profiles/composition_generation_v2.json` | Composition Generation Profile 2.0（form template、phrase 長、harmonic state、motif template） |
| `--realization-profile` | `profiles/composition_realization_v2_1.json` | Realization Profile 2.1（role mask、density、drum lane、texture subrole） |
| `--generation-manifest` | `profiles/full_song_generation_v1.json` | exploration generation manifest（lattice domain、chord reference 表、rhythm grid/density、tempo、tonal center、vector walk、production policy、trial timbre） |
| `--piano-style` | `mixed` | `mixed` / `ostinato` / `obbligato` / `none`（§4.4） |

### 4.1 Stage 1: CompositionPlan 2.0 生成（`composition_generation.py`）

profile + seed から `cps.composition-plan/2.0` を生成する。すべての選択は
`seed-domain-sha256-weighted/v1`（SHA-256(seed || domain) の U64 を重み合計で
mod した加重選択）により決定論的である。fallback・profile 修復・環境乱数は
禁止。4つのステージを持つ。

1. **Formal arc（Stage A）** — 順序付き form template を選択する。各 section は
   `function`、bar 数、energy target、density target、cadence target、
   foreground state を持つ（ラベルから推測しない）。先頭 function は
   `opening`、末尾は `closure` であり、隣接 function 対は遷移表
   （opening→statement|arrival、statement→preparation|arrival、
   preparation→arrival|return、arrival→statement|contrast|return|closure、
   contrast→preparation|return、return→preparation|closure）に従う。
   総長 16–64 bars。
   チェックイン済み template: A `intro-verse-build-drop-return-final-outro`
   （32 bars、weight 3）、B `intro-statement-arrival-contrast-build-final-outro`
   （28 bars、weight 2）。
2. **Phrase partition（Stage B）** — 各 section を gap/overlap なしで順序付き
   phrase に分割する（2/4 bar の phrase 長を function ごとに宣言）。各 phrase は
   `pickup/body/answer/cadence` の slot を持ち、末尾 slot は常に `cadence`。
   非末尾 phrase は cadence target `continuation`、末尾 phrase は section の
   cadence target を継承する。
3. **Harmonic trajectory（Stage C）** — 各 phrase にちょうど1つの harmonic state
   を割り当てる。先頭 phrase は `home`、以降は section function と phrase cadence
   target の両方が許す遷移から選択する。state は `home / departure /
   preparation / arrival / return` を区別し、旧生成器の「単一 harmony state が
   曲中コピーされる」問題を構造的に防ぐ。
4. **Motif lineage（Stage D）** — 最初の非 absent foreground phrase が
   `motif_000` を作成する。派生 event は対応する root の `source_event_id`、
   派生 occurrence は `source_phrase_id` を記録する。操作は
   `statement / recall / answer / rhythmic_displacement / fragmentation /
   cadential_release / rest`。`answer` は degree delta を反転、displacement は
   phrase 内に収まる符号付きオフセットのみ、fragmentation は root event の前半を
   保持、cadential release は末尾 source event を phrase 末端へ移動して degree 0
   に解決する。foreground state `recall` は不変 recall を選択できないため、
   宣言された return は常に非 identity の development を含む。

失敗コード（優先順）: `COMPOSITION_PROFILE_INVALID`、`COMPOSITION_SEED_INVALID`、
`COMPOSITION_PHRASE_PARTITION_UNAVAILABLE`、`COMPOSITION_HARMONIC_PATH_UNAVAILABLE`、
`COMPOSITION_MOTIF_TRANSFORM_UNAVAILABLE`。

### 4.2 Stage 2: SongProgram への lowering（`composition_lowering.py` + `composition_realization.py`）

CompositionPlan を、**structural sampler** が提供する lattice と production
authority 上に lowering する。

- bridge は structural sampler から drums / bass / harmony の material authority
  を要求する。その正確な core set を持たない候補は拒否され、最大 64 回連続の
  structural authority seed を試す（要求された composition seed と
  CompositionPlan は不変）。選択された structural seed と拒否 ordinal は
  receipt に記録される。
- motif lineage から直接、phrase 固有の melody intent と rhythm material を
  作成する。melody の duration は phrase 境界と harmony occurrence の bar
  境界の両方で束縛され、正確な chord-member binding を保持する。

**Realization Profile 2.1**（CLI の既定）で実装済みの第1 milestone:

- 各 section に決定論的加重 **role mask** を選択
- `density_q` を drums / bass / harmony の event 数へ変換（active density、
  metadata のみに留まらず）
- 必須 timing anchor を保持。melody 内部を thin しつつ最初の identity event と
  末尾 cadence event を保持
- section 固有の harmony rhythm material を作成（harmony density が聴覚的に
  効く）
- `energy_q` を `audible_velocity_q = 8500 + round(energy_q*1500/10000)` へ
  圧縮（直接振幅は 8500..10000 のみ変化。大規模対比は arrangement/density が
  主）
- `texture` track を8つの決定論的 functional subrole のいずれかに実現:
  `pad / noise_riser / fx_impact / transition_tail / arp / pluck / vocal_chop /
  counterline`（section function で条件付け: opening→pad/pluck、
  preparation→riser/arp、arrival→impact/chop/arp、closure→tail）
- 決定論的 reference path での multi-lane drums

現行 bridge の既知のギャップ（`composition_generation_profile_2_0.md` に
規範的事実として記載）:

- 全 section で4 role すべてを出力（2.0 path では function 固有の role mask
  未使用。2.1 で mask は適用される）
- `density_q` は 2.0 path では drum subdivision / onset 数を変えない
- 聴覚的対比の大部分は stepwise velocity 変化、3つの tonal-center prototype
  （`home/arrival/return→[0,0]`、`departure→[1,0]`、`preparation→[0,1]`）、
  motif event 変化に由来する
- role の entry/exit、kick/snare/clap/hat の分離と function 固有 drum pattern、
  section 内 energy ramp、filter/send automation、gradual outro は未実装

### 4.3 Stage 3: Structural Sampler + Broad-Prior Production

- `execute_structural_sampler`（Structural Sampler 1.1）— seed-addressed
  weighted table から `structural_program`（form、materials、roles、lattice、
  rhythm cell、recall/transform）を生成する。
- `execute_broad_prior_production` — production lowering（register preset、
  polyphony、drum map）を適用し SongProgram `program` を生成する。

### 4.4 Stage 4: Piano Part（未コミット作業）

`piano_part.py` が別トラック `trk_piano` を追加する（既定で有効）。

- `--piano-style`: `mixed`（既定）/ `ostinato` / `obbligato` / `none`
- `mixed`: statement/arrival/return section は2 bar の answering obbligato
  （先頭1 bar は rest）、それ以外は1 bar 繰り返し ostinato。obbligato section
  は偶数 bar 数を要求する。
- 両 pattern とも音高は active chord から解決する（melody の固定音高のコピー
  ではない）。各 section に独立した piano realization を持ち、専用の
  `trial_piano` reference timbre（決定論的合成 piano-like 音。アコースティック
  レコーディングではない）を使用する。
- SongProgram の role 語彙では pitched `texture` role として表現されるが、
  `trk_piano` の track ID は Project / MIDI / render 出力で独立した identity を
  保持する。
- evaluation MIDI は v1.1 の track override により piano track に GM program 0
  （acoustic piano）を割り当てる。
- piano 有効時、receipt は schema 1.3 になり `piano_style` を bind する。

### 4.5 Stage 5: Compilation（`compiler.py`）

`compile_sp0(program, CompilerIdentity)` → ArrangementProject 1.2（canonical
JSON、決定論的 ID: MaterialInstance、semantic address、Event ID）。bridge の
compiler identity は `composition-generation-v2/v1` + `fixture-resolver` +
catalog digest。

### 4.6 Stage 6: Reference Rendering（`renderer.py`）

GEN0-C の integer-only Q1.31 レンダラが決定論的 PCM32 stereo
`reference.wav` を生成する（`perceptual_preview.wav` としてもコピー）。
trial catalog（Q1.31 mono asset: drum fixture kit + role 別 additive timbre +
piano asset）とチェックイン済み render manifest を使用。

### 4.7 Stage 7: 評価と成果物

- **G0 hard gate**（`song_validity.py`、`assess_completed_song`）— 凍結済み
  `cps.song-validity-assessment`。検査項目: 16–64 bars、3–8 sections、全
  section に realization、drums/bass/harmony/melody のうち3 role 以上が実際に
  発音、symbolic coverage ≥8500bp、完全無音1秒窓が0、arrangement development
  合格、polyphony が各 track 上限以内、同一 material の非 identity 変形 recall
  が複数 section に存在。全項目合格時のみ `archive_eligible=true`。
  （2026-09-19 の scope correction により、これは **G0 renderable skeleton
  gate** として扱い、曲としての知覚的成立性を保証しない。）
- **G1 features**（`composition_viability.py`、`extract_composition_viability`）—
  non-authoritative な feature report（formal arc consistency、phrase boundary
  strength、motif recurrence、harmonic motion、groove distribution、section
  contrast/continuity、part coordination、foreground presence、ending
  closure）。診断用であり、まだ reject には使わない。
- **Evaluation MIDI**（`midi_export.py`）— SMF type-0 の
  `evaluation_reference.mid`。480 PPQ、drums は channel 10、role 別 GM program
  hint、`cps-numeric/decimal-log2-rhe-v1` による per-note pitch bend（±2
  semitone）。hash-bound manifest を伴う。
- **Receipt**（`cps.composition-song-generation-receipt` v1.2/1.3）— seed、
  structural_seed、拒否 ordinal、profile/realization/plan/program/project/wav/
  midi/validity/G1 の各 hash、`archive_eligible`、artifact 名、
  `non_authoritative: true`。

seed ごとの成果物:

```text
seed-NNNN/
  composition_plan.json
  structural_program.json
  program.json
  project.json
  reference.wav / perceptual_preview.wav
  evaluation_reference.mid / evaluation_reference_midi.json
  song_validity.json
  g1_features.json
  receipt.json
```

## 5. 旧パイプライン（Exploration Profile / Broad Prior）

`run_fixture_generation_cohort.py` — 従来の full-song パイプライン。比較と
cohort 測定のために保持されている。

- exploration profile（`song-preview` / `full-song` v2）+ generation manifest
  から、seed-addressed の sealed authority を構築する（SHA-256 domain
  `cps.exploration-authority/v1`。worker 数とスケジューリングは選択 preimage
  に入らない）。
- structural sampler →（profile lowering: role ownership、arrangement plan v2
  の section role mask + `seeded-nonidentity-rotate-recall/v1` recall transform
  policy）→ broad-prior production → compile → render。
- cohort report: compile survival、重複率（program/project/audible/wav hash）、
  semantic admission（audible hash で先頭 seed が勝つ）、symbolic coverage、
  PCM continuity、arrangement、role/material/lattice exposure。
- `full_song_exploration_v2.json` は seed ごとに 28/32/40 bars を決定論的に
  選択し、recall transform の分母 `[2,3,4]` を seal する。

**なぜ新パイプラインが存在するか** — 12 seed full-song cohort の baseline
診断（`development_plan_composition_viability.md` §2）:

- 12 候補中 10 候補に melody event が1つもない（hard gate 合格 9 候補中 7 も
  同様）
- 全 12 候補で、section ごとの harmony pitch set は曲中ずっと1種類だけ
- 2,383 event 中、小節後半に onset を持つものは 99 件（415bp）だけ
- section role は独立抽選されるため、例えば seed 0 は
  `break > verse > verse > outro > build > verse > verse > break` のようになり、
  `outro` が中間に現れ、`build` の後に release がなくても現行 gate を通過する

根本原因（§3）: form が sequence ではなく独立ラベル抽選、material が phrase
ではなく1小節 cell、arrangement が role mask と音量差に限定、hard gate が
存在確認を意味評価として代用、現行 quality 指標（Native JI / PIL）が問題と
直交。

## 6. 評価ゲート G0–G3 とその状況

`development_plan_composition_viability.md`（2026-09-19 の development
decision）により、pipeline は4段階に分離される。

| ゲート | 定義 | 状況 |
| --- | --- | --- |
| G0 technical validity（renderable skeleton gate） | compile、render、silence、register、polyphony | 実装済み（凍結 `cps.song-validity-assessment`）。旧「完成楽曲 hard gate」名は互換名のみに残し、意味は G0 相当 |
| G1 composition viability | phrase、groove、harmonic motion、formal arc、audible recall、part coordination、ending closure | feature report 実装済み（診断のみ）。hard gate 昇格には G2 校正が必要: false acceptance の95%上限 ≤10%、false rejection ≤15%、listener 内 weighted kappa ≥0.6、listener 間一致 ≥0.5 |
| G2 perceptual song recognition | genre を伏せた blind listening（30–45秒 preview + full-song 二段階、6問、yes/uncertain/no） | Web form 実装済み（`/api/blind-evaluation`、commit `f4691922`）。校正 cohort `g1_g2_calibration_v1`（blind_calibration + blind_holdout + ceiling reference + lineage split）進行中 |
| G3 genre fit | G0–G2 合格曲だけを typicality / idiomaticity / reference similarity で評価 | PIL Phase 5 は実装済みだが、**全指標は audit-only**。owner が外部 authority（listener cohort、calibration fixture set、acceptance policy、evidence summary）を昇格させるまで production 判断に使えない |

運用ルール:

- G1/G2 合格前に genre 指標で production 候補を選別しない。
- 昇格前は、G0 合格候補を `technical preview archive` へ置き、G2 で確認済みの
  候補だけを `recognized composition archive` へ入れる。
- G1 自動 gate を archive admission へ昇格させるには、current generator
  negative、破壊 negative、human-authored ceiling、新 generator を含む校正と、
  threshold/renderer/catalog/feature code/dataset split の hash 固定が必要。
  metric を最大化した adversarial search で新しい破綻が出た場合は昇格を撤回する。

## 7. 実装状況まとめ

### 実装済み（SongProgram 生産層）

- GEN0-A 厳密和音 resolver、GEN0-B progression + chord-member melody、
  GEN0-C integer renderer、GEN0-D search artifact / fingerprint
- Project 1.2 compiler（direct / drum / harmony / melody lowering）、standalone
  validator、LineageIndex
- 8種の typed mutation application、mutation 生成 lineage
- Structural Sampler 1.1 + production handoff
- SearchLoop13 契約（genre calibration、planner/patience authority、parallel
  scheduling、cancellation barrier）— runner の実装受け入れは独立 oracle owner
  が authoritative FixtureSuiteIndex をチェックインするまで意図的に保留
- PIL Phase 1–5（pitch projection、segmentation、chord similarity、voice
  matching、trajectory、genre Phase 5）— 全指標 audit-only
- 外部 PIL authority intake（read-only validator。値は owner 提供）
- GEN0 cohort gate（1,000 seed）— 仕様は閉じたが、production aggregation と
  実走は未実施
- CompositionPlan 2.0 生成、Realization 2.1 第1 milestone、song bridge、
  G1 feature report、blind evaluation Web form
- ACE-Step 1.5 genre reference authority（kawaii future bass synthetic v1 +
  negative cohort。2026-09-19 の owner 決定により唯一の承認済み外部 generator）

### 進行中（作業ツリーの未コミット変更、2026-09-22/23）

- full-song piano voice（`piano_part.py` + MIDI program override v1.1 +
  receipt 1.3）
- 5次元 lattice authority（gen0b_5d、connected_v2_5d fixture/oracle、
  `arrangement_project_1_3_5d` schema）

### ブロック / 保留

- SearchLoop13 runner の受け入れ（独立 oracle owner による authoritative
  FixtureSuiteIndex 待ち。production 側は expected root を合成してはならない）
- `pil.genre.*` の昇格（将来の CalibrationDecision version + 外部 listener
  evidence 待ち）
- GEN0 1,000 seed cohort gate の実走
- Realization 2.1 の後続 milestone: section 固有 bass pattern、拡張 harmony
  template、melody relation（approach/passing/neighbor）、composite energy
  curve、instrumented preview backend
- G1 hard gate 昇格（G2 校正結果待ち）

### テスト baseline

- 537 tests passing（backend + conformance、2026-09-13 時点の記録）。以降
  blind evaluation、piano part、5D authority のテストが追加されている
- ruff / mypy pass。conformance oracle + read-only fixture guard

## 8. 現在の cohort 証拠（`local_authority/`、git 管理外）

| ディレクトリ | 内容 |
| --- | --- |
| `mock_full_song_12seed_v1` / `_recall_fix_v1` / `100seed_v1` | 旧 full-song パイプライン cohort。recall 修正の効果: compile survival 12/12 維持、重複0件維持、変形 recall 0/12→12/12、GEN0 完成楽曲成立率 0/12→9/12、`performance_conclusion` が `viable_song_comparison_available` へ変化 |
| `g1_new_generator_24_v1` | 新 CompositionPlan 2.0 generator の 24/24 成功 cohort |
| `g1_g2_calibration_v1` | blind calibration / holdout 割り当て、ceiling reference manifest、lineage split |
| `g1_destructive_negatives_v1` | 6種の破壊 negative control: desync_bass、flatten_dynamics、middle_silence、remove_foreground、remove_groove、truncate_ending |
| `kawaii_future_bass_synthetic_v1` / `_negative_synthetic_v1` | ACE-Step 1.5 の positive / negative reference cohort（genre authority） |
| `composition_generation_v2_seed0` 等 | 単一曲 bridge 出力 |

## 9. 主要コマンド（リポジトリルートから）

```bash
# 単一曲（新パイプライン）
backend/.venv/bin/python backend/tools/generate_composition_song.py \
  --seed 0 --output local_authority/x

# cohort（新パイプライン）
backend/.venv/bin/python backend/tools/run_composition_generation_cohort.py \
  --seeds 24 --workers 8 --output local_authority/x

# 旧 full-song cohort
backend/.venv/bin/python backend/tools/run_fixture_generation_cohort.py \
  --profile full-song --seeds 12 --workers 8 --output local_authority/x

# G1 baseline 診断
backend/.venv/bin/python backend/tools/audit_composition_viability.py \
  --cohort local_authority/x --output /tmp/y.json

# mock 評価 + hard gate（旧パイプライン）
backend/.venv/bin/python backend/tools/run_mock_sample_archive_trial.py \
  --cohort local_authority/x

# 3指標の性能集計
backend/.venv/bin/python backend/tools/analyze_three_metric_performance.py \
  --report local_authority/x/mock_sample_archive_report.json \
  --output local_authority/x/three_metric_performance_report.json

# 検証
cd backend && pytest && ruff check . && mypy app
```

## 10. 参照文書

- `docs/status.md` — canonical implementation status（最終監査 2026-08-08。
  SongProgram ストリームはこれより新しい）
- `docs/song_program_implementation_status_2026-09-02.md` — SongProgram 状況
  （2026-09-12/13/14/15/17 の continuation 含む）
- `docs/development_plan_composition_viability.md` — G0–G3 再設計決定
  （2026-09-19）
- `docs/composition_generation_profile_2_0.md` — CompositionPlan 2.0 契約
  （implemented）
- `docs/composition_realization_profile_2_1.md` — Realization 2.1 契約
  （第1 milestone implemented、後続は design）
- `docs/exploration_cohort_profile_v1.md` — 旧パイプラインの authority /
  admission / report 契約
- `docs/full_song_generation_and_metric_comparison_ja.md` — full-song 生成・
  hard gate・指標比較手順（2026-09-19 scope correction 付き）
- `docs/music_generator_authority_decision_2026-09-19.json` — 外部 generator
  採用決定（ACE-Step 1.5 のみ）
- `docs/non_ace_music_generator_candidates_2026-09-19.md` — 他 generator 候補
  （すべて license/terms review 保留）
- `docs/development_plan.md` — ワークベンチ層の active roadmap（G1–G18）

