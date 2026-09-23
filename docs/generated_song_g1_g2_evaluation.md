# 生成楽曲の G1/G2 評価手順

ピアノを含むかどうかに依存しない、生成曲コホートの評価準備。G0（生成時の
`song_validity.json`）を照合し、G1 の記号的診断をまとめ、G2 のブラインド試聴を
割り当てる。G1/G2 は現時点で非権威的な診断であり、合否閾値や品質ランキングは
この手順では決めない。

## 入力と準備

各コホートは `seed-0000/` から連番の `seed-NNNN/` を持つ生成出力で、各 seed に
`program.json`, `project.json`, `receipt.json`, `song_validity.json`,
`g1_features.json`, `reference.wav` が必要（音声は `preview.wav` も可）。
入力の receipt と実ファイルのハッシュ、再計算した G1 特徴量を検証する。
全コホートの全 seed が揃うまで割当を出さない。出力先はリポジトリ内の
`local_authority/` 以下に指定する。

例（コホート名は任意。音色やピアノ編成を評価器の条件には使わない）:

```sh
backend/.venv/bin/python backend/tools/prepare_song_evaluation.py \
  --cohort a=local_authority/generated_a \
  --cohort b=local_authority/generated_b \
  --seeds 8 \
  --output local_authority/generated_song_evaluation
```

生成される `g1_report.json` は各候補の G0 成立状況、G1 の 11 指標および
コホート別平均を含む。`private_lineage_split.json` は非公開の復号鍵に相当する
対応表。`blind_calibration.json`, `blind_holdout.json` と `audio/` 以下の不透明な
ファイル名の試聴用 WAV を作る。同一 seed の候補はまとめて calibration または
holdout に割り振る。試聴者に `private_lineage_split.json` と `g1_report.json`、
元の生成ディレクトリ名を見せない。同じ出力先で seed 数や割当シードを変更して
既存の割当を上書きすることはできない。

## G2 試聴と集計

試聴サーバーが参照する `CPS_BLIND_EVALUATION_ROOT` は、**実際に割当を出力した
ディレクトリ**に設定する。上記の `generated_song_evaluation` は手順の例示パス。
今回生成した 32 曲の割当で試聴する場合は、リポジトリルートから次を実行する:

```sh
export CPS_BLIND_EVALUATION_ROOT="$PWD/local_authority/piano_style_comparison_8seed_20260923/g1_g2_evaluation"
test -f "$CPS_BLIND_EVALUATION_ROOT/blind_calibration.json" && \
  test -f "$CPS_BLIND_EVALUATION_ROOT/blind_holdout.json"
backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

別のコホートで上記の準備例を実行した場合は、その出力パスを使用する:

```sh
CPS_BLIND_EVALUATION_ROOT="$PWD/local_authority/generated_song_evaluation" \
  backend/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

環境変数はサーバー**起動時**に読み込まれる。実行中のサーバーで 503
（`GET /api/blind-evaluation/assignment/calibration`）が出る場合は、割当ファイルの
所在を確認し、サーバーを停止して正しいパスで再起動する。起動確認:

```sh
curl -f http://127.0.0.1:8000/api/blind-evaluation/assignment/calibration
```

`http://127.0.0.1:8000/blind-evaluation` で回答する。6 問について
`yes / uncertain / no` を記録し、再生不能なら technical failure として記録する。
API は calibration と holdout の割当を別々に提示し、回答をそれぞれ
`responses/calibration/`, `responses/holdout/` に保存する。まず calibration の
回答を収集し、G1 指標と G2 の回答の関係を確認する。閾値を決める場合は
calibration のみを用い、holdout の回答を見てから閾値を変更しない。
複数聴取者を募集し、各候補で有効回答 3 件以上を目標とする。

```sh
backend/.venv/bin/python backend/tools/summarize_song_g2.py \
  --root local_authority/piano_style_comparison_8seed_20260923/g1_g2_evaluation
```

`g2_summary.json` は各候補の設問別回答数、技術的失敗数、有効回答数、
3 件以上の充足状況を出す。回答がなくても 0 件と明示する。同一 partition の
同一 `listener_id` に複数 session がある場合は二重計上を避けるため集計を
エラーにする。G1/G2 の比較時は `g1_report.json` の候補 ID と
`g2_summary.json` の候補 ID を結合する。回答ファイルは assignment hash と
response hash を検証してから集計する。

曲全体の構造・動機・和声の方向・グルーヴ・セクションの連続性・終止を問う
G2 は人間の聴取を要する。G1 の高得点や G0 成立を G2 の代替にはしない。
G1 v1 はダイナミクスの平坦化を検知できないという既知の制約がある
（`docs/g1_g2_composition_calibration_v1.md`）。
