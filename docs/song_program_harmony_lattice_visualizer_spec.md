# 生成楽曲のコード進行・lattice 遷移 visualizer（MVP 仕様案）

Status: 実装済み（MVP、`/song-harmony-visualizer`）。読み取り専用のローカル JSON ビューア。

## 入力と対象

- 必須: full-song 生成物の `project.json`（`cps.arrangement-project` 1.2.0、
  将来の 1.3.0 にも対応）。ブラウザの `<input type="file" accept=".json,application/json">`
  またはドロップ領域から `File.text()` で読み、生成済みファイルのパスをサーバーへ送らない。
- 任意: 同じ生成ディレクトリの `composition_plan.json`
  （`cps.composition-plan` 2.0.0）。アップロード順は任意。
  `plan.sections[].section_id` と `project.form[].id`、総小節数が一致しない場合は
  計画レイヤーを表示せず警告する。計画上の `state_id` や
  `root_degree_ordinal` を、解決済みコードの `anchor_vector` と同一視しない。
- 任意（後続段階）: `reference.wav` のローカル読み込みとカーソル同期。
  MVP は音声なしで利用できる。
- 入力は JSON オブジェクト、最大 20 MiB。schema/version、配列の上限、
  `harmony_occurrences[].resolved_chord_id` の参照先、座標の次元数、
  tick 範囲を検査してから描画する。未対応版は明示して拒否する。
  DOM への文字列挿入は `textContent` を使い、入力を HTML として解釈しない。

## 画面

1. **時系列**: 横軸は `project.clock.total_ticks` に対する小節。
   `project.form[].start_bar/bars/role` を背景帯として配置し、
   `harmony_occurrences` を `(start_tick, chord_index)` で整列したバーにする。
   同じコードの連続出現を折りたたむ表示と、各出現を表示する切替を設ける。
   重なりがある場合は別レーンに配置し、勝手に最後のコードで上書きしない。
2. **選択詳細**: 出現の `section_id`、開始・長さ（tick と小節）、
   `resolved_chord_id`、参照音程 `reference_divisions/canonical_steps`、
   `exact_ratios`、`anchor_vector`、`voice_offsets` と
   `equave_exponents` を表示する。コード記号（C、Am など）は
   データに存在しないため自動推定せず、「12 分割参照 [0,4,7]」等と表示する。
3. **lattice 射影**: `project.lattice.generators` から X/Y 軸を選ぶ。
   解決済みコードの根を `anchor_vector`、各声部を
   `anchor_vector + voice_offsets[i]` に描き、前後の根を線で結ぶ。
   選択した出現を強調し、線には全次元の差分 `Δanchor` を付ける。
   1 次元では Y=0、3〜5 次元では選択外の次元を凡例に明記し、
   点の詳細に全座標を常時残す。`equave_exponents` は別欄に表示して
   2D の同一位置を同一音高だと誤認させない。
4. **pitch circle**: lattice 射影と対になる equave 正規化円の表示。
   角度は `project.lattice.equave` で決まる: `E = 1200 * log2(equave)` cents
   （例: `2/1` → 1200、`3/1` → 約 1902.0）として
   `angle = ((cents mod E) / E) * 2π - π/2`。基準（1/1）は真上、時計回り。
   `2/1` equave ではメインワークベンチの pitch circle 規約と一致し、
   `3/1` equave では `/compose/bohlen-pierce` の tritave circle 規約と一致する。
   中心には equave とその cents 値を表示する（例: "1/1 · 3/1 equave,
   1902.0 cents"）。描画は lattice 射影と同様に SVG。
   - 解決済みコードの根をすべて、根比率（導出規則参照）の角度に描き、
     前後の根を線で結ぶ。線には全次元の差分 `Δanchor` を付ける
     （lattice 射影と同一）。選択した出現を強調する。
   - 選択した出現の声部を `exact_ratios[i]` の角度に描き、元の分数文字列を
     ラベルとする。未選択コードの声部は単一リング上の混雑を防ぐため描かない。
   - `equave_exponents` は別欄に表示し、同一角度を同一音高だと誤認させない
     （lattice 射影と同一の原則）。選択コードの声部で角度が一致し
     `equave_exponents` が異なる場合は、点を同心円（半径オフセット）で
     ずらして重ね合わせを防ぐ。
   - コード記号（C、Am など）は自動推定せず付与しない。
   - 円上の角度差は音高クラス的位置であり、「音楽的距離」の指標として
     表示しない。
5. **計画レイヤー（任意）**: `plan.sections[].phrases[]` の
   `start_bar/length_bars`（section 内相対）から phrase 帯を作り、
   `plan.harmonic_trajectory` を `phrase_id` で結合して
   `state_id/harmonic_function/root_degree_ordinal` を表示する。
   実際のコード出現とは別の色・レーンとし、計画と実現の差を見えるようにする。
6. **操作**: 出現カード、前後キー、表の行から選択を同期。
   lattice 射影 / pitch circle の表示切替、X/Y 軸切替、section フィルタ、
   連続出現の折りたたみを提供する。
   色だけに依存しない形状とテキスト、キーボード操作、狭い画面での
   縦積みレイアウトを用意する。

## 導出規則と実装の境界

```text
occurrence.resolved_chord_id -> project.resolved_chords[].id
bar position = occurrence.start_tick / (ticks_per_beat * beats_per_bar)
voice coordinate[i] = chord.anchor_vector[i] + chord.voice_offsets[voice][i]
root transition = next.anchor_vector - current.anchor_vector
root ratio = product(generators[j] ** anchor_vector[j])   # 厳密分数。根比率はデータに直接含まれない
voice cents[i] = 1200 * log2(exact_ratios[i])
circle angle = (((cents mod E) + E) % E / E) * 2π - π/2   # E = 1200 * log2(equave)
```

`chord_index` は表示順・調査用に保持し、コード配列の添字として使わない。
`exact_ratios` は元の分数文字列を表示する。浮動小数のピッチや
2D ユークリッド距離を「音楽的距離」として表示しない。
pitch circle の角度は cents（浮動小数）で決まるが、これは既存ワークベンチの
円表示と同一の規約であり、距離指標ではない。
必要なら後続版で音高差・voice-leading 指標を別契約として追加する。

実装先は既存 FastAPI 静的ページと同じ構成の
`/song-harmony-visualizer`（HTML/CSS/JS）を想定する。
描画は SVG、解析はブラウザ内の純粋な JS 関数とする。
既存 `/lattice` の表示規約を参考にできるが、生成 API の入力形式へ
Project を変換して再生成しない。MVP の利用には新 API や DB を要しない。

## 受け入れ確認

- seed 0 の `project.json` 単体を読み、8 section・52 和声出現を表示できる。
  18 件の解決済みコードは参照先として検査するが、18 スロットだと誤表示しない。
- 同じ seed の `composition_plan.json` を追加すると phrase と計画 state が
  表示され、Project のみの表示結果は変化しない。
- 軸切替で全座標の詳細を失わず、参照型が `[0,4,7]` のコードに
  根拠のないコード名を付けない。
- `3/1` equave の Project では円は tritave circle となり、`2/1`（1200 cents）と
  `1/1` は異なる角度に来る。`2/1` equave の Project ではメインワークベンチの
  pitch circle 規約と一致する。中心に equave と cents 値が表示される。
- 角度が一致し `equave_exponents` の異なる声部は同心円で区別され、
  詳細に `equave_exponents` が別欄で常時表示される。
- lattice 射影 / pitch circle の切替で選択は保持され、詳細の全座標を失わない。
- 壊れた JSON、未知の schema/version、存在しない chord ID、次元不一致、
  不一致の計画をそれぞれ画面上の明確なエラーとして扱う。
- `none / ostinato / obbligato / mixed` の同一 seed の Project を読むと、
  曲ごとの実際の和声イベントを表示し、ピアノ有無を和声遷移として誤集計しない。
