# Seed由来楽曲の局所 fine-tuning 仕様案 v1

Status: **設計案・未実装**。CompositionPlan 2.0、SongProgram 0.2、Project、
既存 G0/G1 と exact-ratio authority の上に追加する非権威的な探索契約。

## 1. 目的と対象

既存 seed から生成された**一曲**を親とし、phrase／bar の和声状態・root 経路・
和音形・和音リズムなど一部だけを変えた派生曲を複数作る。親を常に比較集合に
残し、同じ編成・音色・レンダラで再生成して、親との差分と各候補の評価値を
並べる。seed を振り直して別曲を探す操作とは区別する。

v1 の主な編集対象は和声。将来の motif・drum・bass・texture 編集は、
それぞれ独立した operation と影響範囲を定義して追加する。親からの 1 段派生を
基本とし、派生候補からの再派生は parent hash を新たに固定した別 request とする。

### 用語

- **parent**: `composition_plan.json`、`structural_program.json`、`program.json`、
  `project.json`、receipt と評価 report をハッシュ照合できる seed 生成曲。
- **declared window**: 編集が意図する section／phrase／bar の集合。
- **guard window**: 境界の voice leading と解決を許す隣接領域（v1 は最大前後 1 bar）。
- **actual impact**: Project の実音 event、harmony occurrence、resolved chord と
  パート構成を親と突き合わせて観測した変化。宣言範囲と別に記録する。
- **variant ordinal**: request 内で安定な候補番号。作曲 seed は親と同じままにし、
  `request_hash + ordinal` を選択乱数の domain に用いる。

## 2. 親曲と固定条件

request は `seed`、`composition_plan.plan_hash`、`program_hash`、`project_hash`、
profile／realization profile／generation manifest の内容ハッシュ、structural seed、
compiler build／numeric contract／catalog digest を固定する（例の JSON では後者を
`parent_snapshot.json` に束縛する）。親の receipt と各成果物を
照合できなければ開始しない。variant の入力に既存の listening preview を使う場合も、
拡張 catalog から作った派生 preview Project でなく**元の Project**を親とする。

v1 で固定するもの: form の section 順序・小節数、tempo／clock、lattice domain と
equave、render catalog／音色／mix、非対象の melody motif lineage、drum onset、
baseline の編成。和音形が変わる場合だけ対象パートの target voice ordinal の再束縛を
明示する。別 equave／generator domain への変更は v1 の局所変異ではない。

親が `--skip-wav` 生成なら symbolic G0 は `incomplete` のまま比較できる。
archive-eligible と呼べるのは同じ Project の PCM レンダリングと無音チェックを
通した後だけ。今回の 1,000-seed cohort では 292 曲が Project まで到達し、
245 曲が PCM 以外の hard checks を通過した。失敗 seed は親に使わず、
`PROGRESSION_NO_PATH` 等の高い失敗率を派生探索でも必ず報告する。

## 3. Request 契約（案）

`cps.seed-song-variation-request/1.0.0`。JSON は closed object とし、
`seed` は 0..2^64−1、`candidate_count` は 1..64、`maximum_edits_per_candidate`
は 1..2、`maximum_changed_harmony_bars` は 1..8、`guard_bars_each_side` は 0..1、
`lattice_exposure_target_q` は null 又は 0..10000、`weight` は 1..2^31−1 とする。
候補の全 target は実在する section/phrase/bar に限り、bar は section 内の 0-based。
同時編集する bar は重複不可、合計 bar 数は予算以内、lock された section は対象外。
以下は値の形の例で、ID／hash は説明用。

```json
{
  "schema": "cps.seed-song-variation-request",
  "schema_version": "1.0.0",
  "parent": {
    "seed": 14,
    "plan_hash": "sha256:<64 hex>",
    "structural_program_hash": "sha256:<64 hex>",
    "program_hash": "sha256:<64 hex>",
    "project_hash": "sha256:<64 hex>",
    "generation_receipt_hash": "sha256:<64 hex>",
    "composition_profile_hash": "sha256:<64 hex>",
    "realization_profile_hash": "sha256:<64 hex>",
    "generation_manifest_hash": "sha256:<64 hex>",
    "structural_seed": 123,
    "compiler_build_id": "<parent compiler build ID>",
    "numeric_contract": "<parent compiler numeric contract>",
    "catalog_digest": "sha256:<64 hex>"
  },
  "search": {
    "candidate_count": 12,
    "maximum_edits_per_candidate": 2,
    "maximum_changed_harmony_bars": 4,
    "guard_bars_each_side": 1,
    "shortlist_count": 4,
    "render_policy": "shortlist_only",
    "lattice_exposure_target_q": null
  },
  "locks": {
    "section_ids": ["sec_000", "sec_007"],
    "preserve_form": true,
    "preserve_motif_lineage": true,
    "preserve_non_harmony_events_outside_window": true
  },
  "edit_pool": [
    {
      "op": "replace_phrase_harmonic_state",
      "target": {"section_id": "sec_003", "phrase_id": "phr_008"},
      "choices": ["harm_departure", "harm_preparation"],
      "weight": 2
    },
    {
      "op": "replace_bar_root_anchor",
      "target": {"section_id": "sec_003", "bar_ordinal": 2},
      "choices": [[0, 0, 0], [1, -1, 0]],
      "weight": 2
    },
    {
      "op": "replace_local_chord_reference",
      "target": {"section_id": "sec_003", "bar_ordinals": [2, 3]},
      "choices": [
        {"temperament": "edo", "equave": "2/1", "divisions": 12,
         "steps": [0, 3, 7, 10]},
        {"temperament": "ji", "equave": "2/1",
         "ratios": ["1/1", "5/4", "3/2", "7/4"]}
      ],
      "weight": 1
    }
  ]
}
```

例の `equave` は 2/1 domain の親に限る。3/1 親なら 3/1 参照だけを選ぶ。
実際の request では親ハッシュ・section ID・phrase ID と選択肢を実在値で埋める。
配列の順序は意味を持つ。`shortlist_count` は 1..`candidate_count`。
request hash は `request_hash` 自身を除いた canonical JSON
に domain separator `cps.seed-song-variation-request/v1\0` を付けた SHA-256。
同じ parent／request／ordinal は環境の Python hash seed によらず同じ候補を作る。
各 ordinal は `SHA256(request_hash || ordinal || draw_address)` による独立した
counter draw を使用し、weight に従って edit を選ぶ。範囲外／重複／同一値の draw
は棄却して次の counter に進み、上限 32 回で `NO_DISTINCT_EDIT` と記録する。
探索途中の失敗は後続 ordinal の draw を変えない。

### v1 operation の意味

| Operation | 範囲と検証 | 意図した知覚差 |
| --- | --- | --- |
| `replace_phrase_harmonic_state` | 対象 phrase の状態。section function と cadence target に適合し、前後の state transition が有効。冒頭 home と終端 cadence は profile の policy に従う | departure、preparation、return の帰着の変化 |
| `replace_bar_root_anchor` | 指定 bar の root vector。次元・bounds・音域を検証し、変更先が親と非同一 | 同じ和音形を保った root 移動 |
| `replace_local_chord_reference` | 指定 bar のみに EDO step 又は exact JI ratio の参照を適用。2〜8 音の基底契約を尊重し、v1 の試験候補はまず 3／4 音に限定 | 和音の色・声数・格子での解決の変化 |
| `replace_bar_harmonic_rhythm` | 追加の v1 候補。onset と占有時間の組を指定し、melody の全イベントが**ちょうど一つ**の harmony occurrence に収まることを要求 | 保持／2 回発音／安全な裏拍 |

`replace_local_chord_reference` で声数を減らすなら melody の target ordinal について
明示的な `member_remap` を要求する。対応がない音を modulo 等で黙って置換しない。
`replace_bar_harmonic_rhythm` の裏拍は melody が無い区間、又は前後の解決と和声束縛を
検証できた場合に限る。`MELODY_HARMONY_CONFLICT` は失敗として残す。

## 4. 局所性と lowering／mutation の境界

親の `composition_seed` を再抽選しない。最初に対象 phrase／bar を選択し、
編集から実音までの対応を一つの `variation_map` として保存する。

1. **Plan 編集**は intent の変更。元の `composition_plan_hash` と派生 plan hash を両方
   残す。ただし現行 lowering は phrase の `root_degree_ordinal % 3` と section 単位の
   root mode を組み合わせるため、状態を替えただけでは実音が変わらない場合がある。
   no-op 候補は破棄し、明示した局所 bar に反映する lowering API が必要。
   現行 `composition_plan` schema に bar 単位の override は無いため、bar root／chord／
   rhythm の編集は**元 plan を変更せず**、独立した typed edit 決定から派生 Program に
   適用する。`replace_phrase_harmonic_state` のみ plan を再 hash／validate してから lower。
2. **Program 編集**は対象 harmony realization が共有する rhythm/material/chord intent を
   **clone-on-write** で分離してから適用する。現在の `MutationContract 2.0` の
   `replace_root_anchor_item`／`replace_chord_intent_reference`／`rotate_rhythm` を共有 ID に
   直接適用すると、対象外 section に伝播し得る。typed mutation の scope/impact report は
   利用できるが、この局所分離を自動実現するものとはみなさない。
3. **Project compile**は GEN0-A top-K と GEN0-B のトラック全体の voice-leading path を
   通す。局所変更でも隣接 occurrence の選択が変わる可能性があるので、実際の変化を
   diff する。最初の v1 は全 Project を再コンパイルして正確性を優先する。
4. **局所差分監査**は section／role／絶対 tick／声部 ordinal を軸に、同一 tick の重複音も
   多重集合で照合し、musical payload（note/drum kind、duration、exact ratio 又は drum
   lane、velocity、harmony-occurrence 時間と voice ratios）を比較する。
   `semantic_address` は補助的な provenance として保持するが clone-on-write で変わり得る。
   program/project hash、resolved chord ID、event ID、chord_index 等のグローバル参照は
   新しくなり得るので、これらの文字列だけを差分扱いしない。変更集合が declared＋guard
   window を越えれば `IMPACT_OUT_OF_SCOPE` として候補を棄却する。bar 境界をまたぐ event
   は onset だけでなく占有 tick 範囲の**全 bar**を対象とし、guard は section をまたいで
   前後 1 bar（曲端で切詰め）とする。

guard 内も「無制限の変更可」ではなく差分を記録する。bass が和声 root に追従する設定なら
bass の同期変化を許すが、role／音域／リズムの lock を検査する。対象外の共通音や
motif lineage は失わない。境界での不連続や大きな voice jump は hard failure 又は
比較 report の独立診断にする。variant が親と実音上同一なら `NO_AUDIBLE_CHANGE`。

## 5. 候補生成・評価・比較

1. 親と権威ファイルを固定し、request を検証・seal する。先に親の section/phrase 対応表、
   和声 occurrence、resolved chord、各 event の section／role／音高を snapshot する。
2. ordinal 0 は**編集しない親**。ordinal 1..N は編集種別、場所、選択肢を決定論的に
   抽選する。同一 edit の重複や no-op を記録して除外する。最大 2 edit／4 harmony bar
   など request の予算を越えない。候補生成中の失敗や重複を成功数に数えず、
   後続 ordinal で穴埋めもしない。再試行で別の structural seed や profile に切替えない。
3. clone-on-write → plan/program hash → exact compile → locality audit → symbolic G0
   （PCM 以外）→ G1、格子音高診断、局所和声差分を計算する。compile failure、
   `PROGRESSION_NO_PATH`、素材上限、MIDI 音域外、G0 failure を候補ごとに記録する。
   既存の親の report は同バージョンの評価器で再計算して揃え、親の G1／G0 が欠ける場合も
   成功候補だけに評価器を変えない。`NO_AUDIBLE_CHANGE`／`IMPACT_OUT_OF_SCOPE` も
   `impact_failed` の理由 code として記録する。
4. 親との **paired delta** と候補間の raw metric を並記する。同じ seed／catalog／mix／
   duration の候補だけ比較する。評価契約は次の表を使う。

| 分類 | 記録する値 | 用途 |
| --- | --- | --- |
| 編集・局所性 | 宣言／実際の変更 bar、対象外 event 変更数、変化 voice 数・時間、境界移動量 | 「部分的な変更」と帰着の検証 |
| 和声 | root 数と格子移動、異なる chord/voice-offset 数、3/4 音占有、共通音、和音 onset／bar、voice-leading 移動 | 意図した和声差の可視化 |
| 構成 G1 | 11 生指標と親との差。既定 Pareto は既存の単調な 5 指標のみ | 変化に伴う構成低下の観測。合否／好みの権威にしない |
| 格子音高 | ≥10¢ の note 数・声部時間比、平均／最大 gap、role 別内訳 | 参照値。**高いほど良い扱いはしない** |
| 格子 target（任意） | request の外部指定 `lattice_exposure_target_q` との絶対距離 | 指定されたときだけ比較軸を追加 |
| 完成曲 G0 | symbolic hard checks と、レンダリング後の PCM check | archive admission の前提 |

5. symbolic G0 成立候補から Pareto 非劣解と、変更量の小／中／大、和声色、root 動作を
   意識した小さな shortlist を作る。親が多くの G1 値で優位でも、異なる色の候補を
   比較用として残せる。`lattice_exposure_target_q` が無ければ格子露出量は目的軸にしない。
   適正帯を持つ section contrast や motif development distance も単純最大化しない。
   既存 frontier の完全一致ベクトルは親→ordinal 順で一つに畳む。shortlist は非劣解を
   優先し、残枠を変更 bar 数→和声参照種別→root 移動の未代表区分で埋め、最後は ordinal
   で決定する。親は枠外の比較基準として必ず WAV 化する。
6. 親と shortlist **だけ**を同じ stock catalog で WAV 化し、PCM G0 と音声 hash を追加する。
   周波数 envelope に収まらない曲を別 catalog で鳴らす場合は preview と明記し、
   比較の公平性と archive-eligible を主張しない。最後に親と候補の A/B 試聴を行う。
   G2 の大規模人手回答は各反復の前提にしない。

単一の総合点で「勝者」を決めない。選択 report は親、失敗候補、全非劣解、
shortlist、各候補の採用理由と比較対象 hash を残す。アーカイブへの昇格は
既存の完成曲 G0 と別途の権威手続きを通す。

## 6. 成果物と再開契約

```text
local_authority/seed_variations/<parent-project-hash>/<request-hash>/
  request.json                   # immutable: parent binding, locks, budget, target
  parent_snapshot.json           # plan/program/project/evaluation hashes; immutable
  candidates/candidate-0000/    # unedited parent comparison row
   candidates/candidate-0001/    # edit_decision, plan (元 plan 又は派生 plan), program/project,
                                # symbolic evaluations, actual-impact report, receipt
  ...
  comparison.json               # all rows, paired deltas, failures, Pareto, shortlist
  audio/candidate-NNNN/         # shortlisted reference.wav, PCM G0, audio receipt
```

ディレクトリ名には `sha256:` 接頭辞を除いた 64 hex を用いる。
`comparison.json` は `cps.seed-song-variation-comparison/1.0.0`。parent hash、request hash、
各候補の operation と選択確率表の ID、before/after hashes、状態
（`rejected_before_compile`／`compile_failed`／`impact_failed`／`symbolic_g0_failed`／`symbolic_valid`／
`rendered_g0_passed`／`rendered_g0_failed`）、理由 code、metric と delta、
Pareto・shortlist 判定を含む。候補と比較 report は canonical JSON＋versioned domain
separator の SHA-256 で seal する。同じ request の再実行は既存ファイルを再照合して再利用、
異なる親 hash・profile・target なら新しい出力ディレクトリを要求する。書き込みは一時
ファイルから atomic replace とし、途中失敗を成功 receipt に見せない。

## 7. 実装順序と受入試験

1. **局所編集と差分監査**: 共有 chord/material の複製、ID の安定生成、対象外の event
   musical payload の完全一致を確かめる。まず `replace_bar_root_anchor` で開始する。
2. **和声参照と phrase 状態**: JI／EDO、3／4 声、target ordinal 再束縛、前後 transition、
   既存 motif lineage と境界の voice leading を検証する。
3. **評価・選択**: 親を含めた paired report、G0 symbolic／PCM 状態の区別、G1 と任意の
   外部 target、失敗率、Pareto と shortlist の再現性を固定する。
4. **試聴**: stock catalog で同一 Project を WAV 化し、少数 A/B を作る。

必須ケース: 同一 request の byte-for-byte 再現、親 hash 改変の拒否、共有 material の
他 section への漏出防止、phrase state 編集が無音の no-op になる場合の拒否、
4→3 声で未対応 melody member の拒否、melody を覆わない harmony rhythm の拒否、
guard 越え voice-leading 変更の拒否、`PROGRESSION_NO_PATH` の候補単位記録、
WAV-skipped の `archive_eligible=false`、stock catalog と preview catalog の区別。

## 8. 現行コードとの接続点

- `backend/app/songprogram/composition_generation.py`: plan／harmonic state、motif lineage。
- `backend/app/songprogram/composition_lowering.py`: phrase state → bar root／rhythm、
  source material の共有と clone-on-write が必要な箇所。
- `backend/app/songprogram/mutation.py`: typed mutation、scope／impact の既存契約。
  v1 はこの API を使う場合も、局所 target 分離と actual Project diff を追加する。
- `backend/app/songprogram/compiler.py`／`resolver.py`: exact chord top-K と
  トラック全体の進行選択、melody/harmony binding。
- `backend/app/songprogram/composition_viability.py`、
  `lattice_pitch_diagnostic.py`、`song_validity.py`: raw 値と staged G0。
- `backend/tools/run_composition_g1_exploration.py`: 5 軸 Pareto の既存参考実装。
- `backend/tools/render_symbolic_cluster_representatives.py`: 保存済み Project から
  再コンパイルせずに WAV を作る試聴段階の参考実装。
