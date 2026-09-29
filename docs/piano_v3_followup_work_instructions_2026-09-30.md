# ピアノ v3 続きの作業指示（2026-09-30）

前提資料: [次工程の基本指示](piano_v3_next_work_instructions.md)、[実装・検収状況](piano_v3_implementation_status_2026-09-29.md)、[v3 仕様](piano_solo_v3_cadence_profile_spec.md)。この文書は **CompositionPlan→CadencePlan→SongProgram 0.3→Project→MIDI/WAV の実験経路を検収した後**の優先順位を定める。既存の基本指示の「経路を接続する」は実験段階では達成済みとし、正式 profile の受入とは区別する。

## 着手前に固定する事実

- `backend/tools/generate_piano_v3_cadence_trial.py` は、octave seed 4（28 slot）と tritave seed 0（32 slot）で Program／Project／WAV hash、48 kHz stereo 非無音 PCM を再現した。`--skip-wav` の PCM は `not_evaluated`。octave seed 0–3 は `PROGRESSION_NO_PATH` として分母に残り、seed 4 は成功。実測の小 cohort を一般的な成功率とは呼ばない。
- `compare_navigation_coverage` では暫定 `[-1,2]^5` の octave modulo-12 navigation は成立。tritave は step 1/5/11 が50 cent gateを外れ、実 `derive_lattice_navigation` も `GENERATION_12TET_COVERAGE_INSUFFICIENT`。軸別 `0..23` **絶対参照窓**の被覆とは異なる。
- `sparse_charge_receipt` は `bounds_only_not_gen0b_opcode_receipt`。正式 GEN0-B opcode／conformance receipt はない。独立試聴ラベルによる T/D/S threshold 較正もなく、両 profile は **unsealed**。
- 作業ツリーには上記 CLI、`piano_v3.py`／テスト、実装状況文書の未コミット変更がある。`git status --short --branch` を確認して保護する。最新の対象テスト18件とRuffは通過し、octave seed 4／tritave seed 0 の WAV hash を再生成で照合済み。変更後は再検証する。

## P0: 実装済み生成経路の照合を fail-closed にする

**対象**: `backend/app/songprogram/piano_v3.py::cadence_impact_report`、`lower_cadence_plan`、`backend/tools/generate_piano_v3_cadence_trial.py`。

1. 現在の report は `program_bound` を全 intent から検索し、`status=matched` を同 bar の **ratio 一致だけ**で決めている。`project_chords[].root_vector_match` は表示されるが matched 判定には入らない。slot ごとに section/bar の material realization→intent→辞書 authority key/hash/variant hash→Project occurrence/chord を関連付け、**その位置に採用された binding、absolute exact ratio、root vector、声部数・各 vector/lift** がすべて一致した場合のみ matched とする。別の bar／同じ pitch class の equave lift／別 entry が同じ ratio を出した場合を誤認しない。実 Project の `resolved_chords` が保持しない出典は Program の hash に束縛された provenance から追跡し、推測しない。
2. section-relative bar の規則と複数 section の section 開始 tick を明示して検査する。section 境界、前 section と同じ和音、入れ替えた intent ID、root だけ改変、1声だけ lift 改変、Project occurrence の位置変更を negative case にする。
3. `generate_one` と cohort CLI の失敗形式を固定する。schema 失敗、authority 改変、`PROGRESSION_NO_PATH`、MIDI／render／PCM の失敗を seed と段階付きで保存する。部分的な artifact の成功を cohort の成功に数えず、WAV省略を PCM 成功にしない。

**完了条件**: octave seed 4／tritave seed 0 の全 slot が再び matched。上記の位置・root・voice・provenance 改変はそれぞれ typed mismatch を返す。SongProgram 0.3／Project 1.3 sparse schema と両 WAV hash の再現を確認する。

## P1: seed 失敗の原因を測り、候補選択を改善する

1. octave seed 0–3 の `PROGRESSION_NO_PATH` を、候補の局所解なし／音域外／voice motion／crossing／候補数のどこで経路が切れたか **layer と bar** を付けて調べる。`stability_q` や Plan の T/D/S ラベルを聴覚上の品質・正解とみなさない。
2. 探索は同一 seed・同一辞書・同一音色・同一 tempo/form に対する bounded な候補置換から始める。進行 feasibility を検査してから選ぶなど、版付きの選択 policy と試行予算を定める。失敗 seed を除いた母数へ書き換えない。違う seed を使って失敗を隠さない。
3. 成功した候補も Project に残った実 slot、PCM、register／周波数、非ゼロ 11/13 軸の実使用量を別々に集計する。成功率、格子音高露出、G1を単独の品質順位にしない。

**完了条件**: 定義した seed cohort の全 seed で成功・失敗段階と理由が再現でき、従来版との同 seed 比較 report を作れる。旧 seed/hash の再現性を保つ。

## P2: tritave navigation の版付き判断

1. まず `derive_lattice_navigation` の modulo-12 契約と axis-search の0～23絶対参照契約のどちらを **profile navigation の gate** にするか決め、変更点を仕様・manifest・fixture に固定する。0～23 を選ぶなら step 19以降の equave lift/register を残す新アルゴリズムを設計し、`step % 12` を流用しない。
2. 別 domain を検討する場合は centered half-domain の vector 合成、最大1024 coordinate／4096 placed、odd-limit・complexity・register、5D各軸、実 `derive_lattice_navigation` を同時に検査する。単軸探索幅を5D矩形直積に入れない。許容誤差の引上げで「被覆済み」と報告しない。
3. 未被覆 step 1/5/11 の vector、signed error、gate 理由を baseline として保存し、新版で octave と tritave をそれぞれ計測する。変更後の実 CadencePlan 曲まで生成し直す。

**完了条件**: 採用 gate の全必要 step が **測定関数と実 navigation の両方**で成立し、予算・Project・PCMを通る。満たせなければ tritave profile は未seal、理由を report に残す。

## P3: 正式 sparse opcode／receipt 契約

`backend/app/songprogram/gen0b_receipt.py` の矩形全列挙を、SongProgram 0.3 の sparse 声部にそのまま適用したことにはしない。宣言／検証／進行探索／再使用の各論理操作を課金し、Program・authority・Project に bind した **新 version の opcode stream と receipt** を設計する。production 実装とは独立した oracle／negative fixture を用意し、root lift、同一 candidate 再利用、cap／hash／authority 改変を照合する。既存0.1/0.2 GEN0-B golden は不変。範囲判定のみの report を正式 receipt へ名称変更するのは、opcode・予算・独立照合が通ってから。

**完了条件**: 実計量から再計算した受入／拒否、opcode totals、receipt hash が独立 oracle と一致し、両 equave の実曲で receipt と Project hash が結び付く。

## P4: 独立試聴と較正（外部ラベル待ち）

`backend/tools/calibrate_harmony_thresholds.py` は学習／held-out 入力を受けるが、現状で実際の独立試聴ラベルはない。評価対象を両 equave・3/4音・異なる tonic・曖昧例から固定し、提示順・評価者・候補 ID・辞書 hash・音声・実 root／ratio を記録する。Plan の機能名や `stability_q` を正解ラベルにしない。関連候補／seed が split を跨がないよう固定し、train のみで threshold を選び、held-out の混同行列・class別・equave別成績と試聴所見を報告。ラベルが無い間は `classification_threshold_calibrated=false` と未sealを維持する。

## 提出と検証

- 実装は P0→P1→P2/P3 の論理単位で切り、P4 は外部ラベルが得られた後に行う。各 PR／コミットに契約変更、negative cases、同 seed 差分、失敗母数、PCM 検収と未評価項目を記録する。
- `backend/` から次を実行: `.venv/bin/python -m pytest -q tests/test_piano_v3_cadence.py tests/test_piano_v3_lowering.py tests/test_piano_v3_song_trial.py tests/test_piano_v3_cadence_generation.py`、変更対象の Ruff、`git diff --check`。authoritative schema/fixture を変更した場合、read-only guard は未コミット差分を失敗とするため、**コミット後**に全スイートを再実行する。
- v3 profile の seal は P0～P3 の実証と P4 の外部ラベル／品質評価を満たした equave ごとに判断する。片方の成功をもう片方の seal に流用しない。
