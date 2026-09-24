# G1-only 生成楽曲探索（暫定ローカル運用）

人手による G2 試聴を各候補に要求せず、まず G0 と G1 で生成候補を探索する。
これは G1 の校正済み合否判定ではなく、候補発見用の診断ループ。
既存の archive admission や `ProductionSearchLoop` の品質・権威契約は変更しない。

和声・パートのコンパイルだけを確認する場合は単曲 CLI で
`--skip-wav --output local_authority/<new-directory>` を指定できる。
Project・MIDI・G1・格子音高指標は保存するが、PCM 無音チェックは未評価となり、
`song_validity.json` は `incomplete`、receipt は `render_status: skipped`、
`archive_eligible: false` を記録する。WAV とそのハッシュは作らない。
この出力は WAV を要する G1 探索・G2 試聴への入力ではなく、完成曲として
扱う場合は別ディレクトリに通常生成する。
WAV を要する通常生成では、参照レンダラが同じ sample asset を複数 note で
利用するとき、その asset の検証・デコード結果を 1 回のレンダリング内で再利用する。
サンプルごとの gain 計算も Fraction の一時オブジェクトを作らない同値の
整数・ties-to-even 演算にした。PCM の混合順序や出力ハッシュの方式は変えない。
残る主要コストは 48 kHz の
各発音フレームの純 Python 演算、トラック別バスの確保・エンコードと、
`reference.wav` / `perceptual_preview.wav` の二重書き込み。

`run_composition_g1_exploration.py` はラウンドごとに指定数の seed を生成
（または完成済みコホートから読む）し、receipt・音声・Project・G1 report を照合する。
G0 不成立候補は理由を残し、G1 探索集合から除外する。G0 成立候補では次の
単調な G1 診断値について Pareto 非劣解集合を更新する:

- audible motif recurrence、foreground presence、groove distribution、
  part coordination、adjacent section continuity。

どれか一つを最大化した総合点にはしない。G1 の残り 6 指標も全候補のレコードに
保持する。特に development distance と section contrast は適正帯を持つため
単純な最大化対象から外す。重複ベクトルは小さい seed を代表にする。
各候補には格子音高の独立した参照診断 `lattice_pitch` も記録する。
Project の pitched note の exact ratio を最も近い 12-EDO 音高と比較し、
10¢ 以上離れた note 数・octave 同値の異なる音高数・発音時間比（声部ごとの
duration 合計を分母とする）・発音時間加重平均ギャップ・最大ギャップを報告する。
drums は除外し、equave が `3/1` でも比較基準は絶対周波数の 12-EDO とする。
生成時は `lattice_pitch.json` にも保存し、既存コホートは Project から再計算する。
発音時間比が高いほど良いとはみなさず、既定の Pareto 対象にも加えない。

格子音の露出量を探索目標にする場合のみ、外部から `--lattice-target-q 3000`
のように 0〜10000 の**発音時間比の目標値**を渡す。探索はその目標値との
絶対差を proximity に変換して Pareto 軸に追加する（10000 が一致）。
目標の設定は generation profile と独立で、G0／archive 判定には影響しない。
目標値を変える探索は別の出力ディレクトリで行う。
非劣解は「聴覚上よい曲」の保証ではなく、G1 v1 の既知の盲点（ダイナミクスなど）
を含む暫定的な探索結果である。実際の提案は現行 generator の seed 列であり、
G1 に基づくパラメータ変更・局所変異はまだ含まない。

## 完成済みコホートで検証

```sh
backend/.venv/bin/python backend/tools/run_composition_g1_exploration.py \
  --source-cohort local_authority/piano_style_comparison_8seed_20260923/none \
  --rounds 2 --candidates-per-round 4 \
  --output local_authority/piano_style_comparison_8seed_20260923/g1_exploration_none
```

今回の 8 seed の例では、G0 を満たさない seed 5 が候補集合から除外される。
結果は `g1_exploration.json` に保存され、各ラウンドの候補・G1 全指標・
非劣解集合・入力ハッシュを持つ。同じ設定で再実行すると成果物を照合して
同じ結果を返す。ラウンド数は増やせるが、途中のファイル変更や設定変更は
既存レポートを上書きせずエラーとする。

## 新しい seed を生成して探索

```sh
backend/.venv/bin/python backend/tools/run_composition_g1_exploration.py \
  --seed-offset 8 --rounds 2 --candidates-per-round 2 \
  --piano-style none \
  --output local_authority/g1_exploration_20260923
```

`--piano-style` は生成時の編成指定であり、評価の入力・基準には使わない。
候補は出力先の `candidates/seed-NNNN/` に保存され、生成済み seed は照合して
再利用する。進行状況はラウンド単位で原子的に記録する。生成処理は
レンダリングを含むため時間がかかる。候補数・ラウンド数を明示して実行する。

G2 の収集を後で再開する場合の割当作成と集計方法は
`docs/generated_song_g1_g2_evaluation.md` を参照する。

## 異なる構成プロファイルの比較試験

`backend/songprogram_conformance/profiles/composition_generation_v2.json` を共通の基準
とし、`backend/songprogram_conformance/profiles/g1_experiments/` に次の 3 案を固定する。
全案で `role_flexible.json` という共通の realization profile を使う。これは
opening / arrival / closure などの section function を単一の編成に結び付けず、
同じ function でも複数の drums・bass・harmony・melody・texture の組合せを選べる。
texture は全 function 共通の pad / pluck / arp から選び、素材数の上限を守る。

| 案 | 基準との主な差 |
| --- | --- |
| `contrast_arc` | 対比区間を持つ form の選択重みを上げ、対比・到達・終止の energy と density の差を拡大 |
| `motif_recall` | 上昇形モチーフと statement / recall / answer の選択重みを上げる |
| `rhythm_dialogue` | drum と bass の onset 候補を増やし、境界 gesture の位置を変更 |

実音化では曲ごとに既存 lattice anchor から home と追加 2 root を選び、
phrase ごとの和声状態を参照して、section ごとに「root 保持」「2 root 往復」
「3 root の巡回」「phrase 状態に追従」のいずれかを選ぶ。和音は bar ごとに配置し、
リズムは section ごとに
保持・交互・2 回発音のまとまり・bar 別抽選から選び、2 回発音では
拍頭または 1/4 小節ずらした裏拍の開始位置を使う。drums と bass の onset 選択には各 CompositionPlan
の part coordination を優先候補として渡すため、`rhythm_dialogue` の変更も実音に反映する。

これらは改善済みプロファイルではなく、G1 が特徴の差をどう観測するか調べるための
実験条件。プロファイルの再生成・内容とハッシュの検証には
`backend/tools/build_g1_experiment_profiles.py` を使う。実験中はプロファイルを
書き換えず、各案について同じ seed・generation manifest・編成を使用する。

```sh
backend/tools/run_g1_profile_experiments.sh --dry-run
backend/tools/run_g1_profile_experiments.sh
```

既定値は `SEED_OFFSET=0`、`ROUNDS=1`、`CANDIDATES_PER_ROUND=2`、
`PIANO_STYLE=none`。基準を含む 4 プロファイル × 2 seed = **8 曲**を生成する。
`REALIZATION_PROFILE` で共通の realization profile を明示変更できる。
`OUTPUT_ROOT` の既定値は `local_authority/g1_profile_experiments_v1/` で、案ごとに
`candidates/` と `g1_exploration.json` を分離する。たとえば 8 seed へ延長する場合:

```sh
ROUNDS=4 backend/tools/run_g1_profile_experiments.sh
```

再実行時は既存の seed を検証して利用する。`ROUNDS` だけを増やして延長できる。
`SEED_OFFSET`、`CANDIDATES_PER_ROUND`、編成、生成 manifest、プロファイルを
変える試験は **別の `OUTPUT_ROOT`** を使う。全案を別の seed 範囲で試す場合も
`SEED_OFFSET=8 OUTPUT_ROOT=local_authority/g1_profile_experiments_seed8` のように
独立させる。G1 非劣解集合は各案の内部で計算されるため、案同士の比較には同じ
seed の `g1_metrics_q` と G0 失敗を並べて確認する。
