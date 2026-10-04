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

## Follow-up P1-2: 版付き register-lift 候補 policy（2026-09-30）

`piano_v3_followup_work_instructions_2026-09-30.md` の P1-2（bounded な候補置換＋版付き選択 policy）を実装した。octave seeds 0–3 の `PROGRESSION_NO_PATH`（voice crossing）を解消する。

**重要な区別**: seeds 0–3 を実際に修復するのは **crossing edge-matching policy**（`crossing_match="non_crossing"`）であり、register-lift ではない。canonical edge matching（歴史的な単一最低コスト pairing）の下では、bounded register-lift だけでは seeds 0–3 を修復しない（`PROGRESSION_NO_PATH` のまま）。これは「lift-only recovery」を主張しないための測定済み blocker である。

- `sparse_variant.py` に**版付き register-lift policy**（`cps.register-lift-policy` **1.0.0**、`piano-v3-register-lift/v1`）を追加: `build_register_lift_policy(allow_lifts, max_lift, max_variants)` と fail-closed な `validate_register_lift_policy`（`REGISTER_LIFT_POLICY_*` 型付きコード）。cadence policy に**加えない独立の版付きオブジェクト**なので、無効時は `policy_hash`／cadence plan／seed4・tritave0 の hash が不変。
- `sparse_core_variants(lattice, intent, anchor, anchor_exponent, dictionary_authorities, policy)`: exact core（voice 0 は anchor に固定）を常に先頭に置き、`allow_lifts` 時に非 root 声部を ±1..max_lift equave だけシフトし、intent の pair-error／span／spacing／complexity 制約を満たすものだけ残す。**pair error は絶対値で測る**（`exact_sparse_core` と同一の契約: canonical_steps は絶対参照ステップ、pair-error budget も絶対）。whole-equave lift は絶対 pair error を 1 equave 分だけ増やす: octave lift は 1,200,000 mc、tritave lift は 1,901,955 mc（**いずれも** 120,000 budget を大幅超過し**除外**）。equave 剰余で測る（旧実装）と tritave lift が budget 内に「見えて」しまうため、絶対値で測ることで SongProgram 0.3 の絶対 eligibility 意味を保持する。`policy=None`／`allow_lifts=False` は `[exact]` を返し旧経路と byte 一致。
- `compiler.py::compile_sp0` は `register_lift_policy`（core 生成）と `crossing_match`（edge matching）の**独立した 2 つの版付き policy** を受け、0.3 で `crossing_match="non_crossing"` の場合のみ**別版の progression query**（`schema_version` **2.1.0**、`algorithm` `gen0-progression-noncrossing/v1`、`crossing_match` const `"non_crossing"`）を出力する。既定 `canonical` は**新 field なし**の元 2.0 query を出力するため、0.1/0.2 と既定 0.3 は歴史的 edge 意味と hash を厳密に保持（1.2/2.0 schema は `crossing_match` を禁止）。専用 2.1 schema（`progression_query_2_1.schema.json`）は**実際の compiler 契約に合わせる**: `budget_profile` は `gen0-progression-exact-v1`（compiler が実際に出力する v1 profile。2.0 schema の `-v2` とは別）、occurrence `maximum_polyphony` は 1–**64**（piano track の上限。2.0 schema の ≤8 とは別）。compiler 側は変更せず、schema 側を実契約に合わせる。
- `resolver.py`: `resolve_progression` が query の `schema_version`／`algorithm`／`crossing_match` を検証し、2.1 のみ `gen0-progression-noncrossing/v1`＋`crossing_match="non_crossing"` を要求（`_matching` が crossing しない pairing のみ順位付けし、`crossing_policy="forbid"` で使える edge を返す）。1.2/2.0 では `crossing_match` の存在自体を拒否（schema の `additionalProperties: false` に一致）し、歴史的な単一最低コスト pairing を維持。query 契約の一部（resolver パラメータではない）であり、0.3-only。
- `piano_v3.py::cadence_impact_report`（schema **1.2.0**）は `register_lift_policy` を受け、lift 有効時に slot ごとに bounded 候補集合を再計算し、chord を位置対応（exact_ratios＋equave_exponents＋vectors）で照合する。**絶対 pair-error budget を超過する chord は候補にならないため、決して matched にしない**（fail-closed: 違反 chord を黙認・relabel しない）。選択候補 index と声部別 lift delta を chord entry（`register_lift_candidate`／`register_lift_deltas`）に記録。sealed binding 照合（source key／dictionary hash／variant hash）は不変。
- cohort CLI に `--register-lift`／`--max-lift`／`--max-variants`（候補生成）と `--crossing`（edge matching）を追加。解決済み policy と `crossing_match` を全 report（`cps.piano-v3-cadence-trial-report` **1.1.0**）と failure（`cps.piano-v3-cadence-trial-failure` **1.1.0**）に記録する。

検証:
- **無効（既定: canonical matching + 無 lift）**: octave seed 4 と tritave seed 0 が上記表の Program／Project／WAV hash を byte 一致で再現。legacy 0.1/0.2 と既定 0.3 経路は不変。
- **crossing policy 有効**（`crossing_match="non_crossing"`、lift 無効）: octave seeds 0–3 が**全て成功**（従来 `PROGRESSION_NO_PATH`）。crossing policy 単独が修復する（lift 不要）。
- **lift 単独（canonical matching）**（`allow_lifts=True, max_lift=1, max_variants=8`、`crossing_match="canonical"`）: octave seeds 0–3 は**全て失敗**（`PROGRESSION_NO_PATH`）。lift-only recovery を否定する測定済み blocker。
- **tritave lift 除外**: tritave（3/1）intent の +1 lift は絶対 pair error 1,901,955 mc > 120,000 budget のため候補から除外（exact core のみ）。octave lift（1,200,000 mc）も同様に超過するため、register-lift は候補を一切生み出さない（機構は存在するが絶対 budget が全 lift を除外）。impact report は違反 chord を matched にしない。
- 対象テスト passed（v3/sparse/compiler/resolver/progression-crossing）＋Ruff＋`git diff --check` クリーン。新規負case: policy の cap／不正フィールド／hash mismatch、`sparse_core_variants` の無効=exact-only／bounded／決定論、lift 対応 report（絶対 budget 超過 chord は matched にしない・exact core は受容・決定論）、crossing policy の seed 解消＋lift 単独の非修復、end-to-end の documented hash 再現。
- **2.1 schema 検証**（`test_songprogram_progression_crossing.py`）: `generate_one` 実行中に実際に compiler が出力した 2.1 query を `Draft202012Validator`＋ローカル `Registry` で全 field 検証（octave0・tritave0 opt-in query が 0 error）。負case: budget_profile 不正（`-v2`）、polyphony 上限超過（65）、`crossing_match` 欠落／値不正、旧 algorithm。1.2/2.0 は新 field を引き続き拒否。

## Cadence 実曲 cohort と象徴特徴クラスタ（2026-10-01）

`generate_piano_v3_cadence_trial.py --crossing --skip-wav` を両 equave の同一 seed 0–5 で実行。各 cohort は6件成功／0件失敗、全 slot の Program／Project 照合が成立した。`--skip-wav` の6件ずつは PCM `not_evaluated`。`cluster_piano_v3_cadence.py --clusters 3` は sealed dictionary と実成果物を照合し、決定論的な再コンパイル・MIDI再出力まで確認した成功曲だけをクラスタに入れる。失敗と検証失敗は分母に残す。距離は実音の absolute ratio による register／chord span、cadence slot、音符 onset 等の**象徴的な比較**で、T/D/S の独立聴覚ラベルや品質評点ではない。

| equave | cohort | cluster report（`cadence-symbolic-distance/v3`） | 代表 seed | report hash |
|---|---|---|---|---|
| 2/1 | `local_authority/piano_v3_cadence_octave_crossing_20261001/` | `local_authority/piano_v3_cadence_octave_crossing_clusters_v3_20261001.json` | 0, 1, 4 | `sha256:89ddfe09217932caff3e78ed306ab69bb9303ceec783e4e697b67a3a81d17d47` |
| 3/1 | `local_authority/piano_v3_cadence_tritave_crossing_20261001/` | `local_authority/piano_v3_cadence_tritave_crossing_clusters_v3_20261001.json` | 0, 1, 4 | `sha256:54d2c6aa86d498218b34e8e277916d65ebf6c297b63150a3f6cc53799953803c` |

代表の WAV は両 equave とも seed 0 が `local_authority/piano_v3_cadence_{octave,tritave}_rep_wav_20261001/seed-0/reference.wav`、seed 1/4 が `local_authority/piano_v3_cadence_{octave,tritave}_reps_1_4_wav_20261001/seed-{1,4}/reference.wav`。全6件の基本 PCM 検査は `checked`（形式・非無音・hash）だが試聴品質の評価ではない。クラスタは非 authoritative な小標本の探索結果で、両 profile は unsealed のまま。

## 100-seed 実測・クラスタ検収（2026-10-02）

両 equave を同一 seed **0–99**、`--crossing --skip-wav`、register lift 無効で**逐次**生成した。`--seeds` には100個の整数を指定（`--seeds 100` は seed 100 の1件だけ）。cohort outcome・seedディレクトリ・クラスタ行・所属の全てが0–99を重複なく覆い、各 equave 100/100生成成功、100/100検証成功、生成／検証失敗0件。前回のseed 0–5のProgram／Project／Plan／cadence policy hashも一致する。`--skip-wav` の200件はPCM `not_evaluated`、WAV生成速度や聴覚品質は測っていない。

| equave | 生成wall / 1 seed / throughput | クラスタwall（100件の再コンパイル・MIDI検証含む） | 8 medoid seed | report hash |
|---|---|---|---|---|
| 2/1 | 457.209 s / 4.572 s / 787 seed/h | 94.931 s | 0, 4, 6, 15, 36, 47, 69, 91 | `sha256:668029857919ad62ceb97a9d89820f90cbe659e76399f9dd98f0efbce4154125` |
| 3/1 | 257.452 s / 2.575 s / 1,398 seed/h | 44.703 s | 0, 6, 53, 55, 62, 64, 66, 70 | `sha256:747fadfc9a616c92c790e6586f4c066fb9121a75773c842c1dee70f01cbda562` |

生成の合計wallは714.661秒、クラスタ込み全4処理は854.295秒（約14分14秒）。Apple M4／Python 3.13.5／単一プロセス・逐次での**各1回の観測値**であり、無負荷・cold/warm条件を制御した比較ではない。実行中に別の回帰テストが重なる時間帯もあり、equave間の差をアルゴリズムだけに帰属しない。生成時間にはseedごとの辞書seal検査等、クラスタ時間には成果物検査・決定論的Project再コンパイル・MIDI再出力が含まれる。

- 生成成果物: `local_authority/piano_v3_cadence_{octave,tritave}_100seed_crossing_20261002/`。クラスタ: `local_authority/piano_v3_cadence_{octave,tritave}_100seed_crossing_clusters_v3_20261002.json`（`cadence-symbolic-distance/v3`）。計測の各処理ログ・wall／CPU／peak RSS: `local_authority/piano_v3_cadence_100seed_crossing_run_20261002/run_summary.json` と同階層のtiming／stderrログ。
- verifier が200件のseed集合・hash・特徴行・クラスタ所属・report hash、代表16件の実Project再コンパイル／MIDI再出力、計測ログとの整合を独立確認した。クラスタツールにcohort reportと実ディレクトリの全seed照合・パス照合を追加し、既存100-seedクラスタreportのbyte一致を再確認した。出力は非authoritativeで、両profileはunsealed。

## 実験用 style profile（restrained／driving）と pilot（2026-10-03）

`style_profile.py`（`cps.style-profile` **1.0.0**）を追加し、v3 cadence trial の**実現音**を変える版付き・hash 束縛の**実験用制御設定**を2つ用意した。ラベルは中立的（`restrained`／`driving`）で、T/D/S の聴覚主張をせず、seal もしない。sealed harmony dictionary と cadence plan の dictionary binding は不変（各 slot は引き続き sealed variant に binding し、変わるのは**どの** variant が選ばれるか＝harmony progression と、tempo／velocity／gate／rhythm の実現）。

- **profile body**（float 無しの canonical 符号化に適合）: `tempo_milli_bpm`（30k–300k）、role 別 `velocity_scale_q`（0–10k）／`gate_scale_q`（1–10k）、role 別 rhythm steps（`at_tick`／`duration_ticks`／`accent_q`、harmony は `mapping` zip|cycle）、cadence の `voice_leading_cap_millicents`（整数 millicent、0<x≤1.2M）＋`candidate_budget`（1–256）。`validate_style_profile` は fail-closed（`STYLE_PROFILE_*` 型付きコード、hash 再計算で改ざん検出）。`build_style_profile`／`load_style_profile`／`apply_style_profile`（clone-on-write、入力非変更）。
- **2 つの対照 profile**: `restrained`（72 BPM、harmony 1 小節持続 gate 10k・soft、melody 分散、cap 250c tight→滑らか progression、budget 16）／`driving`（150 BPM、harmony 4 回 staccato 再打 gate 5k・loud、melody 集約、cap 800c loose→変化 progression、budget 32）。melody-harmony 契約（compiler: melody note は harmony occurrence の時間内に収まり、より短い）を満たすため、melody onset を harmony onset に整列し melody note を harmony より短くする。
- **適用経路**: `build_cadence_policy` に `voice_leading_cap_cents`／`candidate_budget`（既定 400.0/32 で baseline byte 一致）を追加。generator の `generate_one` は millicent→cent 変換して policy を組み、lowering 後に `apply_style_profile`（clock tempo、role 別 velocity/gate、role 別 rhythm steps＋harmony mapping）を適用。trial report／failure は **1.2.0** で `style_profile`（body or null）＋`style_profile_hash`（hash or null）を記録。CLI に `--style {restrained,driving}` と `--style-profile <json>`（排他、未指定=baseline）。
- **cluster validator**（`cluster_piano_v3_cadence.py`）: `TRIAL_REPORT_VERSIONS=("1.1.0","1.2.0")`（1.1.0 は style 無しの旧 report、baseline 扱い）。success ごとに style profile を再検証（hash 再計算＋body 検証）し、sealed 辞書・profile から cadence policy と Program を再導出して保存成果物との byte 一致を要求する。別の有効 profile への差し替え、style field の消去、profile の再hashも負caseで拒否。**混在 style の cohort は fail-closed**（`mixed style profiles in cohort`）。全 baseline cohort は style field を一切持たないため、pre-style 1.1.0 report と **byte 一致**を維持。styled cohort は row ごと＋top-level で `style_profile_hash`＋`style_profile_status=experimental_unsealed` を記録。

検証:
- **baseline 不変**: style 未指定で octave seed4／tritave seed0 の Program／Project hash が上記表と byte 一致（`style_profile`/`style_profile_hash` は null）。既存 100-seed クラスタ report（octave `66802985…`／tritave `747fadfc…`）を再実行し **byte 一致**を確認（100/100 検証成功、validation failure 0）。
- **pilot**（両 equave・同一 seed **0–5**、`--crossing --skip-wav`、style 3 種）: 各 cohort **6/6 成功・0 失敗**（計 36/36）。`--skip-wav` の 36 件は PCM `not_evaluated`。成果物は `local_authority/piano_v3_style_pilot_20261003/{2_1,3_1}_{baseline,restrained,driving}/`、クラスタ report は同階層 `*_clusters.json`（各 6/6 検証成功、report hash は style ごとに相異）。
- **実現音の差異**（seed0 の Project、両 equave で同一）: tempo 120→**72**(restrained)/**150**(driving) BPM、harmony velocity 125→**22**/**90**(accent 79–101)、harmony duration 1920→1920/**240**、harmony 密度 96→96/**384**（4 倍再打）、melody velocity 100→**30**/**103**、melody duration 240→**544**/**80**。cadence progression も sealed variant の選択・順序が style ごとに相異（voice-leading cap／budget の効果）。
- **混在 cohort**: baseline+restrained を混ぜた合成 cohort は `mixed style profiles in cohort: 2 distinct` で fail-closed。
- **テスト**: `test_style_profile.py` はprofile検証／hash／適用／built-in／float-free と、zipの複数和音・重なり・旋律の和音外はみ出し・旋律step超過の負caseを検証。生成級では実現機能差異・baseline安定・styled provenance・改ざんを、cluster級では混在style・別styleへの差替え・style field消去・旧1.1.0 reportとの互換を検証。対象テスト＋Ruff通過、`git diff --check`クリーン。

## 曲調別100-seed生成・クラスタ（2026-10-04）

`restrained` と `driving` の各々を両 equave、同一 seed **0–99**、`--crossing --skip-wav`、register lift 無効で逐次実行。各 cohort は**100/100生成成功・100/100クラスタ検証成功**、生成／検証失敗0件、8クラスタ。成果物は `local_authority/piano_v3_style_100seed_20261004/{2_1,3_1}_{restrained,driving}/`、レポートは同階層の `{cohort}_clusters.json`。時間は各1回の逐次実行の観測値（生成は辞書検証等、クラスタは再コンパイル・MIDI再出力を含む）。最初の起動に失敗した空ログは `timings/_generate.*` として残し、下記の測定に含めない。

| equave | profile | 生成 wall／100 seed | クラスタ wall | 8 medoid seed | cluster report hash |
|---|---|---:|---:|---|---|
| 2/1 | restrained | 463.31 s | 95.82 s | 0, 3, 15, 36, 37, 62, 67, 74 | `sha256:82b5050606c3d9f9ad19e4e67b64c3f502c97aa62efa2afec45de2726a1b8a62` |
| 2/1 | driving | 485.08 s | 117.51 s | 0, 18, 21, 32, 37, 39, 66, 70 | `sha256:c61900fbca275a6ffcba8b7dc92f66a80d8bc7672c9813821d3a1fe8bdc01c6b` |
| 3/1 | restrained | 259.42 s | 48.41 s | 0, 16, 37, 59, 69, 77, 83, 89 | `sha256:6ec3f57933bee68e54ede1451dfbfdf92b057823a469b5ea2a10538b303b2bde` |
| 3/1 | driving | 283.03 s | 66.67 s | 0, 4, 6, 21, 36, 67, 69, 83 | `sha256:5a28eb6966bdbe6dfea226e24c104836d0d4dd7c770016d237676e337460a39e` |

両 equave とも既定の同 seed 100件と Plan hash が一致し、styled Program／Project hash は100/100件で変化。実 Project の tempo は restrained **72 BPM**／driving **150 BPM**（既定120）、全 note の平均 velocity は **26.0／92.6**（既定112.5）、平均 duration は **1232／208 ticks**（既定1080）。driving は harmony の再打鍵により bar 内の異なる onset が3→4、note event が6→15（同 seed 平均）に増えた。これらは **Project の象徴的観測**で、`cadence-symbolic-distance/v3` は onset／密度等を測るが、tempo・velocity・音価を距離へ直接入れない。クラスタ間の差を聴覚上の曲調正解や品質と呼ばない。

100-seedの400件は WAV 省略につき PCM `not_evaluated`。代表 seed 0 を4条件で別途 WAV にし、48 kHz stereo・非無音の基本 PCM 検査が `checked`、各 Program／Project hash が同 seed cohort と一致した。WAV: `local_authority/piano_v3_style_20261004_{octave,tritave}_{restrained,driving}_seed0_wav/seed-0/reference.wav`。試聴による品質や style 分類の正否は未評価。実行ログ・per-seed比較は `local_authority/piano_v3_style_100seed_20261004/timings/summary.{md,json}` と同階層の `*.time`／`*.log` に保存。

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
