# Piano v3 次工程 実装・検収状況

更新日: 2026-09-29。対象指示書: `piano_v3_next_work_instructions.md`。

## CadencePlan 実曲経路

`backend/tools/generate_piano_v3_cadence_trial.py` を追加し、実 `CompositionPlan` から `CadencePlan`、SongProgram 0.3、Project 1.3 sparse、MIDI、任意のPCMまで接続した。各seedは個別に保存し、生成・sparse検証・進行解決・PCMの失敗もcohortの分母とfailure reportに残す。`--skip-wav` のPCM表記は `not_evaluated`。

lowering／impact reportのslot barはsection-relativeに統一した。slot reportには辞書seal hash、sealed variant key/hash、absolute exact ratios、Project chord ratio/root vector照合結果を収録する。octave/tritaveの両方でProgram 0.3／Project 1.3 sparse schemaを検証する。

再現確認済みの採用候補:

| equave | seed | slots | Program hash | Project hash | WAV SHA-256 | PCM |
|---|---:|---:|---|---|---|---|
| 2/1 | 4 | 28 | `sha256:ebd5f9e1fc6bd1b89c17449a6c204de723c775fb3041efa3f4cb47ed215e06c8` | `sha256:c734f6aa8ee852eac982aa30d5e7c31ac99243b11738bbce0a6a129cd002e054` | `sha256:7c26b7816d45f9d24f3f3d0774f116a76cc80089a627c5a6298ea30dd6f644b4` | checked, 48 kHz, stereo, non-silent |
| 3/1 | 0 | 32 | `sha256:98a237f354201948d677a1cfb99deeafebe6f75cbcae87e03614b0afa91c171e` | `sha256:b641579ad5166c2a4497dbae603b38220d734cc132154fb2aacd54fff879a625` | `sha256:d5ebed02f5c67f167ecc89867b04a88ad5122cbe95b0ea4019ddb9a6563394c7` | checked, 48 kHz, stereo, non-silent |

同seedを再実行しPlan／Program／Project／WAV hashが一致した。octave seeds 0–3では `PROGRESSION_NO_PATH` が発生し、cohort reportの候補失敗に残る。seed 4は成功。tritave seeds 0/1は成功。これはseed失敗率の校正結果ではない。

## Navigation／profile seal

比較関数は `measure_navigation_coverage` と実際の `derive_lattice_navigation` を同一domain／policyで実行する。暫定 domain `[-1,2]^5` のoctaveは12-tone modulo navigationを50 cent以内で被覆し、vector選択も実装結果と一致する。tritaveはステップ1／5／11が未被覆（nearest error 55,140／51,318／60,672 millicents）で、実navigationも `GENERATION_12TET_COVERAGE_INSUFFICIENT` を返す。軸検索の0–23絶対参照被覆とは別指標として記録する。

よって両equaveのv3 profileは**unsealed**のまま。tritave navigation policy/domainの版付き解決、実生成での必要step／resource gate再検証が必要。

## Follow-up P0: fail-closed 照合と staged failure（2026-09-30）

`piano_v3_followup_work_instructions_2026-09-30.md` の P0 を実装した。

- `cadence_impact_report`（schema `cps.piano-cadence-impact-report` **1.1.0**）は slot ごとに position → binding → provenance → sounding の全チェーンを照合し、`mismatches` に型付きコードを記録する。`matched` は program と project の両方が与えられ全チェック通過時のみ。
  - position: `V3_RECON_NO_REALIZATION`／`V3_RECON_EXTRA_REALIZATION`／`V3_RECON_MATERIAL_KIND`／`V3_RECON_INTENT_MISSING`（program 側）、`V3_RECON_NO_OCCURRENCE`／`V3_RECON_EXTRA_OCCURRENCE`／`V3_RECON_CHORD_MISSING`（project 側）。bar は section-relative、section start は program form から導出。
  - binding: `V3_RECON_BINDING_SOURCE_KEY`／`DICTIONARY_HASH`／`VARIANT_HASH`／`VARIANT`（dictionary 供給時は sealed variant 全体比較）、`V3_RECON_VARIANT_LATTICE`／`VARIANT_RATIO`（置かれた声部が lattice・slot plan を実現するか）。
  - provenance: `V3_RECON_PROVENANCE_INTENT_HASH`。chord の `intent_hash` は program 内の intent（compiler は同一 variant の bar で chord を再利用するため位置外でも可）に解決し、その variant が slot の authority に binding-equivalent であること。
  - sounding: `V3_RECON_VOICE_COUNT`／`RATIO_MISMATCH`（絶対 exact ratio）／`ROOT_VECTOR_MISMATCH`（anchor＝root voice vector＋section tonal center）／`VOICE_VECTOR_MISMATCH`／`VOICE_LIFT_MISMATCH`（各声部の vector・equave lift）。
- `lower_cadence_plan` は form にない section を持つ slot で `LOWER_SECTION_MISSING`（黙って落とさない）。
- cohort CLI（`generate_piano_v3_cadence_trial.py`）は `V3TrialFailure`（stage＋code＋部分成果物）で失敗を段階記録する。stage: setup／plan／cadence／lowering／program_schema／compile／project_schema／reconciliation／midi／render／pcm。部分成果物は書き出すが cohort success にしない。`--skip-wav` は PCM `not_evaluated`。
- 検証: 対象4ファイル28 tests＋Ruff 通過、全スイート `940 passed, 1 skipped`。octave seed 4（28/28 matched）と tritave seed 0（32/32 matched）で Program／Project／WAV hash を再現（上記表と一致）。負case（occurrence移動、section境界、前section同一chord、intent ID swap、rootのみlift、単一声部lift）は各々型付き mismatch を返す。octave seeds 0–3 は stage=compile／`PROGRESSION_NO_PATH`、部分成果物4件を保持したまま cohort 分母に残る。

## 未完了・ブロック

- **正式GEN0-B sparse opcode／receipt**: 未実装。`sparse_charge_receipt` は矩形領域と宣言声部数のbounds-only判定のまま。production独立fixture、opcode再計算oracle、負数／cap／authority／register等のnegative casesを完了するまで、試行reportも `experimental_not_gen0b_opcode_receipt`。
- **T/D/S独立較正**: 未実施。独立試聴ラベル、固定held-out split、評価者記録が入力されていないため、`classification_threshold_calibrated=false` を維持し、しきい値・profileをsealしない。
- **paired listening／品質評価**: PCM形式・非無音・peak・hash検査のみ実施。音楽品質や外部試聴結果は推定していない。

## 検証

`backend` から以下を実行:

```sh
.venv/bin/python -m pytest -q tests/test_piano_v3_cadence.py tests/test_piano_v3_lowering.py tests/test_piano_v3_song_trial.py tests/test_piano_v3_cadence_generation.py
.venv/bin/ruff check app/songprogram/piano_v3.py tools/generate_piano_v3_cadence_trial.py tests/test_piano_v3_cadence.py tests/test_piano_v3_cadence_generation.py
```
