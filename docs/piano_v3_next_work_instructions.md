# ピアノ v3 次工程 作業指示書

更新日: 2026-09-29。基点: `piano-solo-v2` の `dc32dbe9`。対象は **5D・octave と tritave を別 authority とする、カデンツ駆動の曲生成を検収可能な profile にすること**。実装時は必ず現行の [v3 仕様](piano_solo_v3_cadence_profile_spec.md) と実コードを再確認する。

## 0. 現在地と変更してはいけない境界

- `SongProgram 0.3` の `dictionary_variant` は sparse 配置声部の exact ratio、vector、equave exponent と source hash を持つ。sealed 辞書 variant は辞書 seal／entry／index tuple／root-relative **exact** ratio で検証される。`0.1/0.2` の既存成果物・seed・hash を書き換えない。
- `lower_cadence_plan` は bar ごとに harmony cell／intent を clone-on-write で作り、`cadence_impact_report` は `(section_id, bar)` の実 chord を**絶対 ratio（register を含む）**で照合する。`backend/tests/test_piano_v3_lowering.py` は schema 適合、lower→compile、register 違いの不一致を確認する。
- `generate_piano_tritave_trial.py` は16小節の fixture 派生の実験曲を seed 0/1 で Program→Project→MIDI→WAV まで生成する。sealed 辞書の7/11/13軸3件と、3/1境界を跨ぐ axis-search `[0,7,19]` 1件を区別する。軸検索で24音すべてを被覆したことと、24音すべてを**曲で発音したこと**は別。
- `sparse_charge_receipt` は**矩形点数と宣言声部数の範囲判定のみ**。`scope=bounds_only_not_gen0b_opcode_receipt` は意図的であり、GEN0-B opcode 計量済み receipt と読み替えない。`classification_threshold_calibrated=false`、v3 profile 未seal を維持する。
- 最新の全スイートは `925 passed, 1 skipped`。作業開始時に `git status --short --branch` を確認し、別の未コミット成果を一括 stage しない。

## 1. 実曲生成を CadencePlan 経路へ接続する

**目的**: fixture から任意の4 section を組み立てる試験と、`CompositionPlan → CadencePlan → SongProgram 0.3 → Project → PCM` を通る生成を区別し、後者を両 equave で実行する。

1. `backend/app/songprogram/piano_v3.py` の `generate_cadence_plan`／`lower_cadence_plan` を `backend/tools/generate_piano_tritave_trial.py` や `backend/tools/generate_piano_v3_trial.py` の production・render 経路へ接続する。既存 v1/v2 を改変して seed の意味を変えず、v3 専用 manifest／CLI を追加する。
2. `CompositionPlan` の section／bar 数、root と実音の register、slot ごとの sealed variant の鍵と source hash を記録する。生成途中の `CADENCE_NO_EMBEDDABLE_VARIANT`、`SPARSE_VARIANT_*`、`PROGRESSION_NO_PATH`、PCM 失敗を seed の候補母数から除外しない。tritave 13軸の `[0,7,19]` は現行 odd-limit で不適合でも別 variant が鳴ることを混同しない。
3. 各 slot の Program binding、Project chord occurrence、absolute exact ratio、section/bar、root／voice の一致を検収する。WAV を省略した場合の PCM は `not_evaluated`。生成した WAV については sample rate、チャンネル、非無音・ピーク・hash を記録する。外部の試聴結果や品質点数を PCM 成功から推定しない。

**完了条件**: 同 seed・同 authority で再生成した Plan／Program／Project／PCM hash が一致。octave と tritave それぞれ複数 seed の成功／失敗が report に残り、全採用 slot が Project の同じ位置で一致。Program 0.3 と Project 1.3 sparse の schema に通る。既存2D seed も再現する。

## 2. GEN0-B sparse 計量を正式に設計・検証する

**現状の未実装箇所**: `backend/app/songprogram/gen0b_receipt.py`／`backend/app/songprogram/compiler.py` の既存 opcode／receipt 経路は矩形 domain を全列挙する契約。`piano_v3.sparse_charge_receipt` はこの経路の代替ではない。

1. `0.3` 専用の版付き opcode／budget／receipt 契約を記述する。宣言 sparse 声部の重複、root・equave lift、各 occurrence で再利用した候補、全配置矩形点数を何回課金するかを確定し、hash の入力に Program／選択候補／Project を結び付ける。1軸の探索幅を5Dの直積として課金しない一方、実際に実行した探索・検証・進行の費用を省略しない。
2. production と独立した conformance fixture／negative cases を用意する。負数、cap 超過、hash 改変、辞書 authority 不一致、別 register の同 pitch class、13軸 odd-limit 超過、axis 候補と sealed variant の混同を拒否する。
3. opcode stream と receipt を再計算で検証できるようにし、既存 GEN0-B fixture は byte parity を保つ。正式な契約が成立してから trial report の `bounds_only_not_gen0b_opcode_receipt` を版付き正式 receipt に切り替える。

**完了条件**: 実計量から導出した受入／拒否・opcode totals・hash が独立 oracle と一致する。単なる `675×5=3375` と12声部の上限判定だけでは完了としない。

## 3. tritave navigation と profile seal の判断

- `backend/app/songprogram/exploration_generation.py::derive_lattice_navigation` の `nearest-12tet-vector/v1` は **modulo 12 の navigation**。`backend/app/harmony_dictionary/axis_search.py` の **0～23半音の絶対参照窓**は別の契約。両者の「被覆」を同じ成功フラグにしない。
- `piano_v3.py::PIANO_V3_DOMAINS` の暫定 `[-1,2]^5` は1024 coordinate／4096 placed だが、現行 tritave centered navigation の必要ステップを50 cent以内で全部覆わない。まず `measure_navigation_coverage` と実 `derive_lattice_navigation` を同一 domain／policy で比較し、未被覆ステップ・vector・誤差を保存する。
- 解決策は**版付きの navigation policy の変更**または**予算内の別 domain の探索**として明示し、上限だけを黙って緩めない。tritave で24音 absolute navigation を要件にするなら modulo 12 実装を流用せず、0～23 の target と lift を保つ新 policy／schema／fixture にする。どちらの受入条件を採るか profile に固定する。
- 選択した domain／policy で generator prime、中心からの vector 合成、1024／4096予算、odd-limit・complexity・register、全必要ステップの50 cent gate を実際の lowering と compiler で測定。失敗なら未seal のまま理由を記録する。

**完了条件**: 両 equave の manifest が独立に検証され、必要な navigation 被覆を実装と測定の両方で満たし、前節の実曲・正式 receipt・Project／PCM 検収まで通って初めて v3 profile の seal を判断する。

## 4. T/D/S threshold の独立較正（ラベル収集まで保留）

`backend/app/harmony_dictionary/calibration.py` と `backend/tools/calibrate_harmony_thresholds.py` は、`id`、`split=train|held_out`、`label=tonic|dominant|subdominant`、`stability_q`、`label_source=independent_listening` を入力として受ける。**必要なのは実際の独立試聴ラベル**であり、この文字列を生成器が埋めても証拠にならない。

1. octave／tritave、3/4音、tonic の違い、同 seed の対照、unknown／曖昧例を含む音源と評価表を準備する。候補 ID、辞書 hash、root、absolute ratios、提示順、評価者・試聴結果を保存する。Plan の `home/departure/preparation/arrival` や `stability_q` から正解ラベルを自動生成しない。
2. train／held-out を関連 chord／seed が跨がない単位で固定し、train でのみ threshold を選ぶ。held-out は混同行列、class 別件数、曖昧判定、equave 別結果を報告する。T/D/S を聴取から判定できない例を無理に3択へ割り当てず、必要なら入力契約を別 version へ改訂する。
3. 独立ラベルが揃うまでは `evaluated_not_sealed` と `classification_threshold_calibrated=false` を維持する。現行の仮 threshold を採用済み profile と称さない。

**完了条件**: 再現可能なラベル出典・固定 split・held-out 指標・試聴記録と閾値版が揃い、profile の受入閾値を満たした場合のみ seal 候補にする。必要な独立ラベルが無ければ、この工程はブロック中と明記する。

## 5. 提出・検証手順

- 適切な unit／negative／end-to-end テストと Ruff を実行し、authoritative schema／fixture を変更する場合は変更理由と版を残す。`backend/.venv/bin/python -m pytest -q` は `backend/` から実行する。fixture read-only guard は未コミット schema 差分を検知するので、全スイートの最終確認は当該変更を論理単位でコミットした後にも実行する。
- profile 候補は seed、Plan／Program／Project hash、辞書・policy・compiler identity、候補失敗数、正式 receipt の有無、PCM 検収、paired 評価を一つの report から辿れるようにする。G1 や格子音高露出量だけを品質指標にしない。
- コミットは契約・実装・fixture・文書の依存が追える論理単位に分割し、各単位で `git diff --check`、テスト、`git status --short --branch` を確認する。push は依頼と作業ブランチを確認して実施する。
