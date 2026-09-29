# 音声参照から CPS 生成プロファイルを提案するプログラム — 仕様案

Status: **コア基線実装（2026-09-29）**。純 Python DSP による解析パイプライン
（デコード→品質→時間軸→和声→音響→翻訳→対応可能性→receipt）と 4 種の別 schema、
CLI `analyze_reference_audio` を実装し、テストで検証済み。librosa/Essentia/Basic Pitch/
Demucs/madmom/Chordino 等の外部解析ライブラリは任意の adapter 拡張点として定義し、
コア依存には含めない。音声を入力して曲を複写する仕様ではなく、
和声・リズム・形式・編成・音響的な特徴のうち CPS で実現可能な条件を抽出し、
別 seed から類似の構造を持つ楽曲を生成するための profile 候補を作る。
この文書に記載する JSON 名・コマンド・閾値はコア基線として実装済み。

## 1. 対象と権威境界

最初のターゲットは **単一のローカル音声ファイル**からのインストゥルメンタル
（特にピアノソロ）／通常のポップス形式の解析。入力は WAV/FLAC を優先し、
MP3/AAC は decoder とバージョンを記録して PCM に変換する。最大長・ファイルサイズ・
サンプルレート・メモリ・処理時間は versioned `input_policy` で制限し、範囲外は
理由付きで停止する。全曲を保持する必要はなく、波形と一時 stem はローカルで
扱い、消去方針を指定できるようにする。複数曲からの平均 profile は後続版。

```text
音声/ハッシュ -> デコードされた PCM/ハッシュ -> 複数の観測（時間区間・信頼度・候補）
  -> 拍節と構成の合意 -> コード/ベース/旋律等の仮説 -> 対応可能性検査
  -> CPS profile patch + 不足レポート -> 同 seed の候補生成/Project/WAV 照合
```

入力音声の chord 名は **12-EDO の比較用ラベル**、CPS の sounding ratio は
別の authority。混合音から正確な 5D vector／純正比率や「作曲時の原コード」を
確定しない。絶対 key よりも tonic 仮説と相対 root の推移を重視する。
`home/departure/preparation/arrival/return` を T/D/S の聴覚機能へ直結しない。
5D 辞書の stability は仮指標で、曖昧な候補を `ambiguous/unknown` として残す。
提案する CLI は `analyze_reference_audio --input <file> --target <manifest-id>
--output <directory> [--seed <u64>]`。最初は既存の3D full-song manifest
（例 `full-song-generation-v1`）を実行可能ターゲットに、5D piano v3 は
実装・検証後に別ターゲットとして登録する。2D piano v1 は履歴再現用で
新規 target として選ばせない。未知の manifest ID は拒否する。

## 2. 出力契約（別 schema、既存 profile は直接書き換えない）

出力ディレクトリは `analysis.json`、`profile_patch.json`、
`capability_report.json`、`receipt.json` と、任意の可聴な検証結果を持つ。
音声固有の数値を、既存 schema の `additionalProperties: false` に押し込まない。

| 成果物 | 必須の内容 |
| --- | --- |
| `analysis.json` | 入力 PCM の SHA-256、元音声 hash、decode 条件、時刻基準（秒/sample）、拍時刻、BPM 候補と倍/半テンポ、拍子候補と downbeat、区間境界、繰返し関係、chord 候補（root/quality/bass/no-chord）、転調、onset 密度、音域、役割／音色特徴、音量曲線。各観測に区間・手法/モデル版・confidence/ambiguity・可聴範囲を付ける。推定不能は `null` と理由、観測を削らない |
| `profile_patch.json` | 既存の Composition Generation Profile 2.0 と、ターゲット別 generation／realization／production manifest への**型付き patch**、ターゲット schema/version/hash、選択した equave/軸/3D以上の次元、seed に依存しない重み・範囲・section 別分布。各設定は観測 ID と翻訳規則 ID にトレースできる。検証後に初めて seal する |
| `capability_report.json` | 全観測の `exact`/`approximated`/`unsupported`/`uncertain`/`not_applicable` 判定。対象 schema path、時間範囲、観測値、試行した CPS 値、差分、原因（schema/実装/profile/音声不確実性/予算/音源）、severity、推奨改修、実験上の優先度。未対応項目を黙って落とさない |
| `receipt.json` | tool/build/model/weights、入力・PCM hash、decode/前処理パラメータ、選択した基準 profile と辞書/音源 catalog hash、patch/report hash、seed、候補選択理由、検証ステータスと失敗履歴。モデル出力は実行版と重み hash を固定する |

`analysis.json` の観測は例えば
`{id, type, start_sample, end_sample, value, candidates, confidence, provenance}`
とし、周波数/拍数/小節の単位を混同しない。`confidence` は校正された確率と
同義ではないため、定義・モデル版・校正集合を一緒に記録する。
異なる解析器の不一致、例えば C:maj / A:min、4/4 / 2/2、80 / 160 BPM は
候補を併記して後段の人手訂正を許可する。

`profile_patch.json` は**直接生成に使えると検証した patch**と、
`proposed_only` の拡張要求を区別。既存の profile 用 validator を通した
基準 profile と patch の merge 結果のみ CPS に投入する。未対応の抽象値を
「適用済み」としない。例（キー名は設計例）:

```json
{
  "schema": "cps.audio-derived-profile-patch",
  "schema_version": "0.1.0-proposal",
  "target": {
    "composition_profile_schema": "cps.composition-generation-profile/2.0.0",
    "target_generator": "full-song-generation-v1"
  },
  "settings": [
    {
      "target_path": "/form_templates/0/sections/1/energy_q",
      "value": 5600,
      "source_observation_ids": ["obs_energy_verse"],
      "translation": "section-energy-rank/v1",
      "status": "candidate"
    }
  ],
  "proposed_only": ["gap_tempo_map_001"],
  "validation": {"status": "not_run", "target_hash": null}
}
```

この path は説明用。実際には profile の `form_templates` 各行の順序・整合性、
型、hash を検証し、複数候補の form を weighted に出力する。レポート例:

```json
{
  "schema": "cps.audio-profile-capability-report",
  "schema_version": "0.1.0-proposal",
  "target_schema": "cps.song-program/0.2",
  "items": [{
    "id": "gap_tempo_map_001",
    "observation_ids": ["obs_tempo_001", "obs_tempo_002"],
    "span_samples": [0, 4410000],
    "capability": "tempo_map",
    "status": "unsupported",
    "observed": {"bpm_range": [92, 118]},
    "attempted": {"tempo_milli_bpm": 105000},
    "error": {"maximum_bpm_deviation": 13},
    "reason": "schema_fixed_clock",
    "severity": "structural",
    "suggested_update": "versioned tempo map in Program/Project/renderer",
    "priority": 1
  }]
}
```

`not_run` と `unsupported` は区別する。`exact` は **profile でその条件を
指定できる**意味で、音響的な再現一致を保証しない。変更の優先度は検出確度、
出現時間、特徴量への寄与、下流の修正規模から計算し、手動で訂正可能にする。

## 3. 解析と profile 化の段階

1. **音声品質**: decoder の出力/PCM 長さ、無音、clipping、チャンネル差、
   位相差、残響/ノイズを測り、音楽の音高特定が不適切な区間を mark。元と
   必要に応じ HPSS/分離 stem を並列で解析し、分離結果を原音より優先しない。
2. **時間軸**: onset、tempo curve、beat/downbeat、拍子と半拍・倍拍候補を
   推定。ダウンビートが曖昧なら `bar_0` を固定せず複数仮説で進める。
   曲頭/曲末余白と pickup は別扱い。beat-synchronous 特徴に対する自己類似
   行列から section／phrase、繰返し/転調下の反復を推定する。
3. **和声**: 混合音・低音／分離 stem の chroma、tuning、局所 key、
   chord posterior と `N` (no-chord) を求め、拍同期で smoothing。
   pedal bass/転回形、借用/非和声音、長音中のコード替わりを別証拠とし、
   12-EDO 認識と JI/equave 仮説を混ぜない。候補は 3/4音に限定せず、
   不明なテンションはそのままレポートする。
4. **旋律・編成・音響**: piano stem/単一楽器なら note on/off、
   同時発音数、拍内位置、レジスタ、跳躍、短い motif/repetition を推定。
   full mix では melody 識別や正確な楽器判定は低信頼度となり得る。
   energy/loudness、transient、帯域、stereo も曲内相対値で保存する。
5. **翻訳**: section を CPS の `opening/statement/preparation/arrival/
   contrast/return/closure` に仮写像し、2～16小節/section、16～64小節
   全体、3～8 section などの整合性を確認。cycle の period、motif の
   相対音程と変形、コード変化の位置を profile の**分布**に変換する。
   固有メロディーの note 列・全コード列・元音源のサンプルを写し込むより
   反復距離/区間転移/和声機能の条件を優先する。
6. **CPS 適合・再生成**: `CompositionPlan -> SongProgram -> Project -> WAV`
   と段階別に照合。profile schema 通過だけでなく 3D/5D domain 予算、
   chord の exact 解決、辞書の coverage、Project の時間/音域、render
   catalog と PCM を検査する。候補失敗はレポートに戻す。

写像ポリシーは `literal_constraints`（高信頼の区間長・拍数等）、
`probabilistic_style`（進行/リズム/反復の分布）、`unresolved`（確認待ち）を
分ける。音声の微分音は整数比の一意な逆写像ではない。2/1・3/1 のどちらが
適切かは音高証拠と生成の可解性を別に評価し、根拠が無ければ既定の 2/1
候補と `equave_unresolved` を出す。新規の piano profile では 2D を選ばない。

## 4. 初期の capability 差分一覧

下表は **現行 schema/実装**と照合した、観測された場合に報告すべき例。
入力音声をまだ解析していないため、特定楽曲での発生を主張するものではない。

| 音声で観測できるパターン | CPS の現在地 | 判定／提案 |
| --- | --- | --- |
| 加減速・ritardando、曲中拍子変更、7/8・5/4 等 | SongProgram 0.2 の clock は曲全体で単一 BPM（30–300）、`beats_per_bar∈{2,3,4,6}`、480 ticks/beat | 構造的に `unsupported`。固定拍への近似誤差とタイムラインを記録。tempo/meter map は schema＋compiler＋Project＋renderer の改版が必要 |
| 16–64 小節を外れる構成、長い section、9節以上、拍節不定の曲 | Composition Generation Profile 2.0 のテンプレートは3～8 section、各2～16小節、総16～64小節。SongProgram の section は1～32小節、Project は最大128小節 | **ターゲット別**に `unsupported` または短縮構成への `approximated`。CPS 全体が64小節しか出せないという主張ではない |
| 自由な拍ずれ、三連/ポリリズム、超細かなグルーヴ | Plan の motif は正規化位置。SongProgram は480 ticks/beat、rhythm steps と回転を持つ | 480 tick 精度で表現可能なら `approximated`/`exact`。拍子多重/連続的な演奏揺れの保存・再現は個別に検証 |
| 転調や tonic の多義性、非機能和声、5音以上や複合和音 | Program の chord reference は2～8 step の EDO 関係、5D は可能。5D 辞書は**3/4音の軸別 index**、stability/TDS は暫定分類 | 原音への exact ratio 投影・範囲/辞書候補を検査。辞書検索は `unsupported`、Program 側は適合性未検証なら `uncertain` と別対象の report 行にする。D/T を強制しない |
| 12-EDO 以外の調律／連続的な pitch bend | Program は equave/generator の exact lattice を扱えるが、音声から比率や root vector は確定しない | 近似誤差と情報不足を別欄に。連続 pitch curve は `unsupported`、単一の安定音高は ratio 候補として試験 |
| ピアノペダルの共鳴、細かなタッチ、時間変化する filter／reverb／pan | Program production の `envelopes` は **空配列のみ**、gain/pan は track ごとの定数。音源 catalog の表現範囲にも依存 | 音声特徴は残すが音色／automation は現行 canonical renderer の再現条件にできない。`unsupported` または instrument 近似 |
| 歌声/歌詞、声部独立の微細な表情、環境音など | `tracks.role` は `drums/bass/harmony/melody/texture`、catalog 限定の render | pitch/rhythm の一部は抽象化可。歌詞/発音や録音音響は profile に直写できない。音源 catalog と役割を照合 |
| section ごとの意図的な楽器出入り・ドロップ前の build | Program は section/realization を持つが、現行 CompositionPlan→曲の bridge は全役割を各 section に配置し、`density_q` を実際の onset 密度へ反映しない | `schema_possible / current_lowering_unsupported` を区別。未実装の Realization 2.1 を完成済みとみなさない |
| 完全な固有旋律・フレーズごとに異なるモチーフ変換 | Profile 2.0 の motif event は2～16、操作語彙は7種、固定トランジション制約 | 統計的近似は可。固有メロディーの転写再生はこの生成 profile の目的と異なる。表現外の音楽的変形は gap に記録 |

基準: [Composition Profile 2.0](composition_generation_profile_2_0.md)、
`backend/songprogram_conformance/schemas/{composition_generation_profile_2_0,song_program_0_2,arrangement_project_1_3}.schema.json`、
[piano v3 案](piano_solo_v3_cadence_profile_spec.md)。

## 5. 解析ライブラリ調査（一次資料、2026-09-28 確認）

候補は adapter ごとに独立 worker で実行し、コア `backend/pyproject.toml`
の依存に直ちに入れない。ここでの「有用」は機能候補であり、CPS 入力との
一致率を実測したものではない。

| 候補 | 用途／制約 | ライセンス・導入判断 |
| --- | --- | --- |
| [librosa](https://librosa.org/doc/latest/index.html) | decode 後の beat/onset、chroma/CQT、HPSS、self-similarity/section 特徴。コード確定や正確な和声機能は自前の時系列推論が必要 | [ISC](https://github.com/librosa/librosa/blob/main/LICENSE.md)。最初の CPU baseline に推奨。version・数値バックエンド・decode を固定 |
| [Essentia](https://essentia.upf.edu/tutorial_tonal_hpcpkeyscale.html) | HPCP、Key、音響特徴・大規模抽出の比較候補。12音系 key は JI/3:1 の正解を意味しない | [AGPLv3/商用ライセンス、モデルは別条件](https://essentia.upf.edu/licensing_information.html)。必要なら分離 adapter で評価 |
| [Basic Pitch](https://github.com/spotify/basic-pitch) | 単一楽器／分離 stem の note・pitch bend 候補。公式に polyphonic 対応だが「1楽器ずつが最良」、フル mix の全声部転写の保証なし | [Apache-2.0](https://github.com/spotify/basic-pitch/blob/main/LICENSE)。公式 README の互換表は Python 3.7–3.11、CPS は `>=3.12`。別環境で試す |
| [Demucs](https://github.com/facebookresearch/demucs) | vocal/drum/bass/other の分離で解析器の補助。音源漏れ・分離の偽音に注意 | [MIT](https://github.com/facebookresearch/demucs/blob/main/LICENSE)。元 repo は 2025-01-01 以降 archive、開発者 fork も最小保守。任意の独立 worker のみ |
| [madmom](https://github.com/CPJKU/madmom) | downbeat／拍節、コード解析の比較候補。プリトレーニング済み model と実行環境を別途検証 | 公式 README: code は BSD 系、[model/data は CC BY-NC-SA 4.0](https://github.com/CPJKU/madmom#license)。現行環境での動作確認前提の任意 adapter |
| [Chordino / NNLS Chroma](https://github.com/c4dm/nnls-chroma) | chroma と chord transcription の 12-EDO 比較基準。Vamp plugin/ホスト統合が必要 | [GPL-2.0](https://github.com/c4dm/nnls-chroma/blob/master/COPYING)。binary/配布形態も別途確認。CPS の chord authority にはしない |

初期構成: `librosa` + 単純な beat 同期 chroma chord baseline（no-chord/unknown
を持つ）+ CPS の schema validator／exact resolver。次に Basic Pitch を
**ピアノ／単一楽器**で比較し、Essentia の HPCP/Key、madmom downbeat、
Chordino chord を同じ評価セットで差分比較。Demucs は stem あり/なしの
誤検出差と処理コストが見合う場合だけ採用する。

## 6. 検証と開発順

1. **固定評価素材**: 合成レンダリングした既知の CPS Project/WAV（Program
   由来の拍・和音・形式が正解として存在）、人手で bar/chord を付けた
   録音、ピアノ単体と full mix、可変 tempo/meter、無音/長いイントロを含む。
   自己レンダリング素材は認識の過大評価を避けるため録音曲と分けて報告。
2. **analysis/receipt**: decode 再現性、時間軸、候補・unknown・confidence、
   観測 ID を定義。同一 PCM/設定/モデルで同じ正規化結果・hash。CPU baseline
   を先に作り、依存重いモデルは分離 worker で段階導入。
3. **capability registry**: schema・実装・profile・catalog の対応範囲を
   バージョン付きで読み、観測の各区間に `exact/approximated/unsupported/
   uncertain` を割り当てる。新しい CPS version で古い report を再採点
   できる。report のどの gap も元区間に戻れるようにする。
4. **profile translation**: form/section/phrase と beat の境界を検証し、
   テンプレート重み・motif 抽象関係・リズム密度・chord/cadence 候補を
   翻訳。型と hash の合う候補のみ seal。写像の失敗は `profile_patch` に
   偽の値を入れず `report` に載せる。
5. **同 seed 比較**: baseline profile と音声由来 profile を同じ seed 群、
   equave、catalog、render 条件で Project と PCM まで生成。beat/downbeat、
   section 境界、chord-root 列、反復距離、energy、役割密度、聴取による
   「構造的な類似」と「独自性」を別々に評価。G1 や pitch 露出の最大化を
   自動的な音楽品質指標にしない。WAV を省略した候補は PCM 品質**未評価**。

受入例: 既知の CPS レンダリング素材では節境界と BPM/コードの有効候補を
観測から再取得し、現行 schema に載らない可変 tempo のテスト音声では
少なくとも1件の `tempo_map` gap が対象区間と誤差付きで出る。
全候補について profile validator、compiler、Project／WAV の結果と
失敗を母数付きで報告する。人手修正後の結果は自動推定と別バージョンにする。
