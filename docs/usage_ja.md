# 使用ガイド

**プロジェクト:** Pure Intonation Composer

バージョン: 0.1

このガイドでは、実装済みのすべての機能について説明します。対象は、ブラウザ上のワークベンチ（各パネルの操作方法）および HTTP/WebSocket API です。正確なリクエスト／レスポンスのスキーマについては [api.md](api.md) を、コピーして実行できるコマンドについては [examples.md](examples.md) を参照してください。

---

# 1. はじめに

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

* ワークベンチ: `http://127.0.0.1:8000`
* 対話型APIドキュメント（Swagger）: `http://127.0.0.1:8000/docs`
* ヘルスチェック: `GET /health`

確率的な処理はすべてシードを受け取ります。同じ入力とシードを与えると、常に同じ出力が生成されます。

---

# 2. ワークベンチ

ワークベンチは、複数のパネルで構成された単一ページです。音声はすべてブラウザ内の WebAudio によってローカル再生され、音階・和声・リズムなどの生成処理はサーバー上で実行されます。

## 2.1 Generatorパネル

音階、すなわち有理数比で表されるピッチクラスの集合を生成し、ピッチ円上に表示します。

1. 生成方法を選択します。
   * **Combination Product Set** — 指定した因子に対して CPS(n,k) を生成します。UIでは harmonic に固定されていますが、APIでは `kind` を指定して subharmonic CPS も生成できます。
   * **Euler–Fokker genus** — 指定した素因子の積から音階を生成します。
   * **Harmonic series** — 最初の N 個の倍音を生成します。
   * **Subharmonic series** — 最初の N 個の分数倍音を生成します。
2. **factors** に、カンマ区切りの正の整数（例: `1, 3, 5, 7`）を入力します。倍音列・分数倍音列の場合は **count** を入力します。
3. CPSの場合は、**組合せの数**（組合せサイズ k）を設定します。
4. **1オクターブ内に正規化**を有効にすると、すべての比が1オクターブ内に折り畳まれます。
5. **音階を生成**を押します。

### スナップ

生成ボタンの下にあるスナップ行では、現在のすべての音を別の音律へ近似できます。

* **EDO** — 各音を、1オクターブを N 等分した音律の最も近いステップへ移動します（N = 2～31）。
* **Prime limit** — 各音を、指定した上限以下の素数から構成される最も近い比へ移動します（例: 5-limit、7-limit）。

API: `POST /api/tuning/snap`

## 2.2 ピッチ円（Radial graph）

各点は音階内の1音を表し、セント値に応じて円周上へ配置されます。

* **点をクリック**すると発音します。音程表の行、または `A S D F …` キーでも発音できます。
* 複数の音を押している間、フォーカス音へ向かう線が和声強度に応じて色分けされます。凡例は円の下に表示されます。
* **ちょうど2音を押す**と、2音間の相対音程比が接続線上に表示されます。
* **倍音（harmonics）**トグルを有効にすると、3、5、7、… の奇数倍音を、選択した上限（5～64）まで破線ガイドとして重ねて表示します。各線にはオクターブ縮約後の比が表示されます。

## 2.3 Graphビュー

CPS音階を使用している場合、**Graph**ボタンでピッチ円から Johnson graph J(n,k) へ切り替えられます。ノードは因子の組合せを表し、1つの因子だけが異なる組合せ同士がエッジで接続されます。

2種類のレイアウトを使用できます。

* **force-directed** — 物理シミュレーション型の配置です。ブラウザ内で決定論的に計算されます。
* **layered grid**（`reference_layered_grid`、[visualization.md](visualization.md) 参照）— 基準ノードと共有する因子数に応じてノードを層状に配置します。左側に `Shared N · Distance M` のラベルが表示されます。**ノードをダブルクリック**すると、そのノードが新しい基準ノードになり、層が再構成されます。各層内の並び順は、辞書順、因子の積、またはピッチから選択できます。

両方のレイアウトで次の操作が可能です。

* ノードをシングルクリックすると、そのピッチを発音します。
* **Walk**コントロールでは、ノード1からグラフ上を移動します。
  * `random walk` — 一様確率で隣接ノードを選択します。シード指定可能です。
  * `weighted walk` — harmonic／monzo／cent距離の近さに基づく重み付きで隣接ノードを選択します。シード指定可能です。
  * `shortest path` — 選択した目的ノードまでの最短経路を求めます。
* 移動経路は強調表示され、各ステップに `#1 #2 …` の番号が付きます。
* ラベル選択では、各組合せの比表示を **harmonic** と **subharmonic** の間で切り替えられます。

API: `POST /api/harmonic-graph`（`operation`、`layout`、`reference`、`sort_mode`）

## 2.4 Soundパネル

ライブ演奏とWAVレンダリングの両方に適用される演奏設定です。

* **基音** — `1/1` に対応する基準周波数です（110～440 Hz）。
* **波形** — sine、triangle、sawtooth、squareから選択します。
* **ADSR**スライダー — attack、decay、sustain、releaseを設定します。
* **Stop all** — 現在鳴っているすべての音をリリースします。
* 画面上のキーボードには、音階の先頭16音が割り当てられます。対応するPCキーは `A S D F G H J K L ; Q W E R T Y` です。

## 2.5 Intervalsパネル（音階エディター）

音階内の全音を、キー割り当て、比、セント、monzo（素数指数）とともに表形式で表示します。

* **Play**を押すと発音し、**×**を押すと音階から削除します。
* 表の上にある入力欄では、次の形式で音を追加できます。
  * 比 — `5/4`
  * セント — `748.2`
  * EDO次数 — `5\12`（12-EDOの5ステップ）
  * 小数比 — `1.33`
  * 数式 — `=2^(6/12)`
* 新しい音はピッチ順に挿入されます。Enterキーで追加します。

API: `POST /api/analyze-interval`  
単一比の解析: `POST /api/analyze-ratio`

## 2.6 Scalesパネル（音階ブラウザ）

名前付き音階をサーバーのメモリ内に保存します。サーバーを再起動すると消去されます。

* **現在の音階を保存** — 指定した名前で現在の音階を保存します。同じ名前で再保存すると上書きされます。
* **Load** — 保存された音階で現在の音階を置き換えます。
* **×** — 保存された音階を削除します。
* **Scala をインポート** — ディスク上の `.scl` ファイルを読み込みます。ファイルを解析し、ファイル名で保存したうえで現在の音階として採用します。
* **Scala を保存**（Intervalsパネル内）— 現在の音階を `.scl` ファイルとしてダウンロードします。

API: `GET/POST /api/scales`、`GET/DELETE /api/scales/{name}`、`POST /api/scales/import`、`POST /api/export/scala`

## 2.7 Composeパネル

CPSの和声グラフから、複数パートを含むテクスチャ全体を生成します。

1. factors、組合せサイズ、**length**、**seed**、距離 **metric** を設定し、**和声進行を生成**を押します。生成された和音は遷移スコア付きのチップとして表示されます。チップをクリックすると、その構成音（root × 各factorをオクターブ縮約した音）を試聴できます。
2. **ベース生成** — 和声進行の下にベースラインを生成します。戦略は `mirror`（subharmonic mirror）、`root`、`fifth`、`hybrid` です。
3. **旋律生成** — 和音の上に独立した旋律声部を生成します。声部数と輪郭（`arch`、`ascending`、`descending`、`free`）を設定できます。
4. **▶ 再生 / 停止** — 選択したテンポで、和音、ベース、旋律をブラウザ内再生または停止します。

**Rhythm Orchestration**

* `Rhythm layers`では、現在のkick/snare/hat/percパターンを、和音の根音・
  第2音・第3音などへ個別に割り当てるか、Harmony/Bass/Melodyの役割へ
  割り当てます。`Chord tones`、`Roles`、`Hybrid`プリセットに加え、各行で
  対象、声部方針、音数不足時の処理、gate、velocity、octave、articulation、
  collisionを編集でき、On/Soloも指定できます。
* `Generate`ではHarmony、Bass、Melodyの各行に独立したStrategy、Profile、
  Density、Syncopationを設定します。transition-aware、Semi-Markov、
  interlocking、実験的ratio-derivedを役割ごとに選択できます。Melody行の
  設定は生成済みの全旋律声部へ適用され、barsとseedは全体で共有します。
* **Apply rhythm / Generate rhythm**後は、再生、MIDI、JSON、WAVが同じ
  tick単位イベント列を使用します。**Clear rhythm**で従来の固定ステップへ
  戻ります。
* Composition Rollは時間比例表示へ切り替わり、各音の発音・持続と
  ソースパターンのレーンを表示します。

エクスポート:

* **MIDI** — 楽曲をMIDIファイルとしてダウンロードします。**ピッチベンドで正確な音程**を有効にすると、各音を個別のチャンネルへ配置し、正確なピッチベンドを付加します。これにより微分音を正しく保持できます。無効の場合は、最も近い12平均律の半音へ量子化されます。
* **JSON** — 楽曲構造をJSONとしてダウンロードします。
* **WAV レンダリング** — サーバー上で非同期ジョブとしてオフラインレンダリングします。完了すると、ボタンの下に音声プレーヤーが表示されます。Soundパネルの波形とADSRに加え、軽いリバーブが適用されます。

API: `POST /api/compose/harmony`、`/api/compose/bass`、`/api/compose/melody`、`/api/compose/voice-leading`、`/api/compose/rhythm/apply`、`/api/compose/rhythm/generate`、`/api/export/midi`（`pitch_bend`）、`/api/export/json`、`POST /api/render/jobs` + `GET /api/render/jobs/{id}` + `GET /api/render/jobs/{id}/audio`

## 2.8 Rhythmパネル

* **Euclidean リズムを生成** — Sステップ上にP個のパルスを、指定した回転量で分配します。グリッドには各ステップのオン／オフが表示されます。
* **ヒューマナイズ** — シード付きでタイミング（±ms）とベロシティを変化させます。セルの不透明度がベロシティを表します。
* **▶ 再生** — パターンを4周期分クリック音で再生します。ヒューマナイズされた時間オフセットが適用され、4ステップごとにアクセントが付きます。
* **MIDI** — 選択したノート番号を使い、GMパーカッション（チャンネル10）としてパターンを書き出します。例: 36 = kick、38 = snare、42 = closed hat。ヒューマナイズ後のベロシティも保持されます。
* **JSON** — パターンと各ヒットをエクスポートします。

API: `POST /api/rhythm/euclidean`、`/api/rhythm/humanize`、`/api/rhythm/phase-shift`、`/api/rhythm/state-graph`、`/api/export/rhythm/midi`

## 2.9 Timeline（レコーダー）

* **Record** — 録音を開始／停止します。キーボード、ピッチ円、グラフで演奏したすべての音が、実際のタイムスタンプ付きで記録されます。
* イベントは、秒単位の軸を持つタイムライン上に実時間で配置されます。
* **▶** — 元のタイミングを保ったまま録音を再生します。
* **Clear** — 録音内容を破棄します。

## 2.10 Transport WebSocket

`ws://127.0.0.1:8000/api/ws/transport` は、JSONコマンド `play`、`pause`、`stop`、`improvise`（`seed`付き）を受け取り、トランスポート状態メッセージを返します。詳細は [examples.md](examples.md) を参照してください。

## 2.11 Lattice Lab（Experimental）

整数生成子 `(a, b, …)` の指数ベクトルを、正確な比
`aⁿ¹ · bⁿ² · …` として扱う実験用の和声ラボです。

* **格子を生成** — 生成子と指数範囲から格子点を列挙します。同じ
  ピッチクラスとなる異なる座標は衝突グループとして表示されます。
* **和音を生成** — 許可ステップ、音数、シードから、発音が重複しない
  根音相対の和音ベクトルを決定論的に生成します。生成結果は和音ベクトル欄へ
  反映されるため、そのまま編集できます。
* **ハーモニーを再構成** — ルート比と、根音から独立に加算する和音ベクトル
  列から和音を正確に復元します。根音 `(0,0)` は暗黙に含まれます。
  **Compose に送る**では、全構成音を1つの和音として渡し、ベース・旋律生成、
  再生、MIDI、JSON、WAVで利用できます。
* **和声進行を生成** — 和声進行の差分ベクトルを累積して根音列を作り、
  各根音に同じ和音ベクトルを適用します。進行全体の再生とCompose転送が
  できます。
* **ウォーク** — 指数格子上の経路を生成し、各地点を移動ルートとした
  和声スタックを構成します。各地点へ同じ根音相対の和音ベクトルを適用し、
  **和声ウォーク再生**では全構成音を同時発音します。ウォーク側の
  **Compose に送る**では経路全体を和声進行へ変換します。
* **Lattice Keyboard** — Lattice Labにフォーカスがある間、生成または
  再構成した和音を `A S D F …` キーで押している間だけ発音できます。
  画面上の鍵盤も同じ割り当てです。

API: `POST /api/exponent-lattice/scale`、`/harmony`、`/chord`、
`/progression`、`/walk`、`/analyze`

---

# 3. API概要

ベースURLは `http://127.0.0.1:8000` です。すべてのリクエストボディはJSONです。音楽入力が不正な場合は、HTTPステータス422とともに `{"detail": "…"}` 形式のエラーが返されます。

| グループ | エンドポイント |
| --- | --- |
| 音階生成 | `POST /api/cps`、`/api/euler-fokker`、`/api/harmonic-series`、`/api/subharmonic-series` |
| 解析 | `POST /api/analyze-ratio`、`/api/analyze-interval`、`/api/tuning/snap` |
| 音階ストア | `GET/POST /api/scales`、`GET/DELETE /api/scales/{name}`、`POST /api/scales/import` |
| グラフ | `POST /api/harmonic-graph`（構築、walk、layered layout） |
| 作曲 | `POST /api/compose/harmony`、`/api/compose/voice-leading`、`/api/compose/bass`、`/api/compose/melody`、`/api/compose/rhythm/apply`、`/api/compose/rhythm/generate` |
| リズム | `POST /api/rhythm/euclidean`、`/api/rhythm/state-graph`、`/api/rhythm/phase-shift`、`/api/rhythm/humanize` |
| Lattice Lab | `POST /api/exponent-lattice/scale`、`/api/exponent-lattice/harmony`、`/api/exponent-lattice/chord`、`/api/exponent-lattice/progression`、`/api/exponent-lattice/walk`、`/api/exponent-lattice/analyze` |
| レンダリング | `POST /api/render/wav`、`POST /api/render/jobs`、`GET /api/render/jobs/{id}`、`GET /api/render/jobs/{id}/audio` |
| エクスポート | `POST /api/export/midi`、`/api/export/rhythm/midi`、`/api/export/scala`、`/api/export/json` |
| リアルタイム | `WS /api/ws/transport` |

完全なスキーマは [api.md](api.md) を参照してください。実行可能なコマンドは [examples.md](examples.md) にあります。

---

# 4. 典型的なワークフロー

## 4.1 CPS音階を探索する

`1, 3, 5, 7` を因子、k=2としてCPSを生成 → ピッチ円上で各音を演奏 → **倍音**を有効にして倍音との整列を確認 → 2音を同時に押して音程比を確認 → 12-EDOへスナップし、平均律での対応音を聴き比べます。

## 4.2 楽曲を作成してエクスポートする

シード42で和声進行を生成 → hybridベースとarch形の旋律を追加 → **再生**で試聴 → ピッチベンド付きMIDIをDAW向けにエクスポートし、試聴用にWAVも出力します。

## 4.3 和声グラフを移動する

Graphビューへ切り替え → layered gridレイアウトを選択 → 離れたノードをダブルクリックして、そのノードを中心に再配置 → harmonic metricとシードを指定してweighted walkを実行 → 和声空間を移動する1つの進行例として経路を確認します。

## 4.4 リズムトラックを作成する

E(5,13)をrotation=2で生成 → シード付きでヒューマナイズ → **再生**で試聴 → MIDIをkick（ノート36）としてエクスポート → DAWへ読み込みます。
