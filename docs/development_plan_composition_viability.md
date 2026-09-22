# 曲としての成立性をgenre評価より先に保証するための再設計

Status: development decision draft, 2026-09-19. ここで定義する自動指標は、
人間評価による校正が完了するまでarchive admissionの権威を持たない。

## 1. 結論

現行full-song pipelineは、コンパイル可能で音が途切れず、複数roleとsectionが
存在することを検査している。しかし、これは「再生可能な構造体」の成立条件であり、
人間が時間的まとまりを持つ曲として認識する条件ではない。したがってgenre評価の
閾値調整より先に、次の4段階へpipelineを分離する。

1. `G0 technical validity`: compile、render、silence、register、polyphony。
2. `G1 composition viability`: phrase、groove、harmonic motion、formal arc、
   audible recall、part coordination、ending closure。
3. `G2 perceptual song recognition`: genreを伏せたblind listeningで、意図的な
   反復、まとまり、展開、協調、始まりと終わりが知覚されること。
4. `G3 genre fit`: G0–G2合格曲だけをtypicality、idiomaticity、reference similarityで評価。

現行`cps.song-validity-assessment`は互換性のため凍結し、意味をG0相当の
`renderable skeleton gate`として扱う。G1を通過していない候補へ「完成楽曲」や
`song archive eligible`という名称を使わない。

## 2. 現状の実測

対象は
`local_authority/mock_full_song_12seed_recall_fix_v1`のseed 0–11である。

- compile成功は12/12、symbolic coverageは全候補100%、完全無音1秒窓は0。
- 現行hard gateは9/12を`archive_eligible=true`にする。
- 12候補中10候補にmelody eventが一つもない。合格9候補のうち7候補も同様である。
- 全12候補で、sectionごとのharmony pitch setは曲中ずっと1種類だけである。
- 2,383 event中、小節後半にonsetを持つものは99件（415 basis points）だけである。
- section roleは独立抽選されるため、例えばseed 0は
  `break > verse > verse > outro > build > verse > verse > break`となる。
  `outro`が中間に現れ、`build`の後にreleaseがなくても現行gateを通過する。

再現コマンド:

```bash
backend/.venv/bin/python backend/tools/audit_composition_viability.py \
  --cohort local_authority/mock_full_song_12seed_recall_fix_v1 \
  --output /tmp/cps-composition-viability-baseline.json
```

この診断はproxy破綻の可視化専用である。genre非依存の普遍的な「良い曲」の定義や、
人間校正済みの合否判定ではない。

## 3. 根本原因

### 3.1 formがsequenceではなく独立ラベル抽選

`section_role`はsectionごとに同じ重み表から独立に選ばれる。section数と小節数だけを
full-song profileが固定し、roleの順序、開始、準備、解放、終止を制約しない。
`development_stage`はrole名から後付けされるため、時間的な展開を生成していない。

### 3.2 materialがphraseではない

現行materialは1小節のcellであり、rhythm onsetは等分gridの先頭から必要数を取る。
このためonsetが小節前半へ偏る。melody pointのcontourは`hold`、harmony root anchorは
単一、mappingは`cycle`である。これらをsection全体へrepeatしても、問いと答え、
呼吸、cadenceを持つphraseにはならない。

### 3.3 arrangementがrole maskと音量差に限定

section差は主にactive role数とvelocity scaleで作られる。bassとkickの同期、
melodyとharmonyの応答、fillから次sectionへの接続など、part間の因果関係は生成されない。

### 3.4 hard gateが存在確認を意味評価として代用

100% coverage、3 role、2種類のrole mask、transform metadataは、それぞれ必要条件に
なり得るが、phrase、harmonic motion、audible developmentを保証しない。
特に`non_identity_transformed_recall`はtransform指定の存在だけを見ており、
聴取上同じmotifが変奏再現されたかを検証しない。

### 3.5 現行quality指標は問題と直交

Native JI coherenceは音律的一貫性、PIL typicality／idiomaticityは校正対象の
知覚・genre属性を扱う。どちらもformal arc、phrase closure、groove、hookの存在を
単独では保証しない。G1不合格候補の順位付けに使うと、よく調律された「鳴っているだけ」
を上位へ残す。

## 4. 次期生成プロセス

次期profileは現行`exploration profile`を延命せず、
`cps.composition-generation-profile/2.0`として別契約にする。広い乱択から偶然の曲を
待つのではなく、時間階層を上から下へ生成する。

### Stage A: formal arc

section roleを独立抽選しない。profileが順序付きform templateまたは有限状態grammarを
所有し、seedは有効なpathだけを選ぶ。初期実装は検証しやすいtemplate方式とする。

```text
intro -> verse_a -> build -> drop_a -> verse_b -> build -> final -> outro
intro -> verse_a -> drop_a -> break -> build -> final -> outro
```

各sectionは`function`、`energy target`、`density target`、`cadence target`、
`foreground state`を持つ。ラベルからstageを推測しない。

### Stage B: harmonic trajectory

曲全体のtonal centerを一つコピーする方式をやめ、section境界を含むroot/function pathを
先に生成する。最低限、home、departure、preparation、returnの状態を持たせる。
純正律／可変equaveの探索はこの軌道を実現する手段であり、軌道そのものの代用ではない。

- 曲内に複数の知覚可能なharmony stateがある。
- build終端は次sectionのarrivalを準備する。
- final/outroはprofile指定のhomeまたは意図されたopen endingへ収束する。
- voice leadingは隣接chordだけでなくphrase終端を含めて最適化する。

### Stage C: phrase and motif

1小節cellではなく、2または4小節のphraseを最小単位にする。phraseは
`pickup/body/answer/cadence`のslotを持ち、restを構造要素として生成する。
motif変形はrotate metadataだけでなく、実音event列の対応を保持する。

必要な変形は、rhythmic displacement、interval-preserving transpose、contour-preserving
ornament、fragmentation、extension、call/responseである。各変形は元motifとの
audible correspondenceと変化量をreportする。

### Stage D: coordinated parts

roleを独立に鳴らさず、依存順に生成する。

1. harmony trajectoryとphrase boundary
2. groove spine（kick、snare/clap、hat/percussion）
3. bass（harmony rootとkickの両方へ拘束）
4. foreground motif／melody
5. pad、texture、fill、transition

drumsはkick一音だけのmapを完成曲profileで禁止する。各section境界にはfill、休止、
pickup、sustainのいずれかの接続gestureを要求する。

### Stage E: variation with locks

seedで全要素を再抽選せず、form、harmony、motif、groove、arrangementを別sub-seedへ分離する。
弱いsectionだけを再生成できるようにし、曲全体のmotif identityとcadence planをlockする。

## 5. 次期profileの責務

profileはgenre labelより前に、次の構成契約を明示する。

```text
form_templates[]
section_function_policy
energy_density_trajectory
harmonic_function_graph
phrase_lengths_bars
motif_transform_budget
foreground_role_policy
groove_spine_policy
part_coordination_constraints
boundary_gesture_policy
ending_policy
technical_render_policy
```

genre profileはこのcomposition profileへ、tempo、instrument、syncopation傾向、典型的な
form候補などのpriorを追加してよい。ただしG0/G1の合否定義を上書きしてはならない。

## 6. G1 composition viabilityの評価ベクトル

一つの総合`quality score`を先に作らない。原因を保持する以下のvectorとして記録する。

| 指標 | 見るもの | 初期の扱い |
| --- | --- | --- |
| `formal_arc_consistency_q` | profileの有効path、energyの準備と解放、終端 | template違反だけhard、連続値は診断 |
| `phrase_boundary_strength_q` | 2/4小節境界の休止、cadence、accent収束 | 診断 |
| `audible_motif_recurrence_q` | event fingerprint上の再認可能な反復 | 診断、校正後hard候補 |
| `motif_development_distance_q` | 同一すぎず無関係でもない変奏量 | 範囲指標、最大化しない |
| `harmonic_motion_q` | state数、root/function遷移、arrival | 退化だけhard候補 |
| `groove_distribution_q` | 小節内onset分布と周期的安定性 | 退化だけhard候補 |
| `section_contrast_q` | density、role、register、loudnessの隣接差 | 範囲指標 |
| `adjacent_section_continuity_q` | 境界をまたぐ共通素材とgesture | 範囲指標 |
| `part_coordination_q` | kick–bass、harmony–melody、fill–arrival | 診断、校正後hard候補 |
| `foreground_presence_q` | hook／melody等のforegroundが意図区間に存在 | profile宣言に対するhard候補 |
| `ending_closure_q` | 最終phraseのrhythm/harmony/energy収束 | ending policy違反だけhard |

「多いほど良い」とは限らない。contrast、syncopation、developmentは上下限を持つ
適正帯として扱う。coverageやevent数で代用せず、無音を含む時間配置とrole関係から計算する。

## 7. G2 blind listening protocol

genre名、seed、評価値を伏せ、30–45秒previewとfull-songの二段階で次を質問する。

1. 音の羅列ではなく、意図された時間的まとまりとして聞こえるか。
2. 繰り返されるphraseまたはmotifを一つ認識できるか。
3. sectionの境界と、少なくとも一つの展開／対比を認識できるか。
4. rhythm、bass、harmony、foregroundが互いに関係して聞こえるか。
5. 始まり、中間、終わりを持つ一つの作品として聞こえるか。
6. clipping、過密、欠落などがなく技術的に聴取可能か。

回答は`yes / uncertain / no`とし、genre適合や好みは別票にする。`uncertain`を自動合格へ
丸めない。最低3名、同一lineageをcalibration/testへ跨がせない分割、blind negativeを
含む条件で校正する。

## 8. negative controlsと反事実試験

人手曲または人手で整えたceiling fixtureから次の破壊版を作る。

- section順をshuffleする。
- motif recallだけ別素材へ置換する。
- onsetを小節前半へ寄せる。
- harmonyを全section同一にする。
- bassをkickおよびharmonyから時間・音高の両方でずらす。
- final cadenceとending gestureを除去する。

各自動指標は対応する破壊だけに主に反応することをmetamorphic testで確認する。
一つの破壊で全指標が同時に大きく動く場合は、同じproxyの言い換えになっている。

## 9. 昇格条件

G1自動gateをarchive admissionへ昇格する条件は次とする。

- blind G2判定に対するfalse acceptanceの95%上限が10%以下。
- false rejectionの95%上限が15%以下。
- listener内weighted kappaが0.6以上、listener間一致が0.5以上。
- current generator negative、破壊negative、human-authored ceiling、新generatorを含む。
- threshold、renderer、catalog、feature code、dataset splitのhashを固定する。
- metricを最大化したadversarial searchで新しい破綻が出た場合は昇格を撤回する。

昇格前は、G0合格候補を`technical preview archive`へ置き、G2で確認済みの候補だけを
`recognized composition archive`へ入れる。

## 10. 実装順序

1. 現行12/100 seedを診断toolでbaseline化し、結果をimmutable reportとして保存する。
2. ordered form templateとsection functionを持つprofile 2.0 schemaを追加する。
3. phrase／groove／harmonic trajectory generatorを、既存compilerの前段として追加する。
4. G1 feature reportを実装し、まだrejectには使わない。
5. negative controlsと少数のhuman ceiling fixtureでmetamorphic testを通す。
6. blind G2 cohortを収集し、G1 thresholdをholdoutで校正する。
7. G1/G2通過候補だけを既存PIL genre評価へ渡す。

最初の実装milestoneは、genre scoreの改善ではなく次で判定する。

- 有効form path 100%。
- melodyまたはprofile宣言されたforegroundが対象sectionに存在。
- 全section同一harmonyの退化候補0%。
- phrase終端とsection境界がevent上で明示される。
- blind G2で現行generatorより明確に高いrecognition率を得る。
