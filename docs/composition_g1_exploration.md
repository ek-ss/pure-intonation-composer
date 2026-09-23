# G1-only 生成楽曲探索（暫定ローカル運用）

人手による G2 試聴を各候補に要求せず、まず G0 と G1 で生成候補を探索する。
これは G1 の校正済み合否判定ではなく、候補発見用の診断ループ。
既存の archive admission や `ProductionSearchLoop` の品質・権威契約は変更しない。

`run_composition_g1_exploration.py` はラウンドごとに指定数の seed を生成
（または完成済みコホートから読む）し、receipt・音声・Project・G1 report を照合する。
G0 不成立候補は理由を残し、G1 探索集合から除外する。G0 成立候補では次の
単調な G1 診断値について Pareto 非劣解集合を更新する:

- audible motif recurrence、foreground presence、groove distribution、
  part coordination、adjacent section continuity。

どれか一つを最大化した総合点にはしない。G1 の残り 6 指標も全候補のレコードに
保持する。特に development distance と section contrast は適正帯を持つため
単純な最大化対象から外す。重複ベクトルは小さい seed を代表にする。
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
