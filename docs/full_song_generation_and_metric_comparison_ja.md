# Full-song生成・完成楽曲hard gate・指標比較手順

## 1. 目的

この手順は、決定論的なfull-song profileで複数seedを生成し、次の処理を一括して検証するためのものです。

1. structural sample
2. production lowering
3. compile
4. reference WAV render
5. 固定snapshot FeatureExtractor v1による10秒特徴量抽出
6. Native JI／PIL／mock genre評価
7. 完成楽曲hard gate
8. 評価指標のseed間比較

FeatureExtractor v1はジャンル識別試験に失敗しています。この手順のgenre similarityは配管試験専用であり、production判断、CalibrationDecision昇格、ジャンル適合の主張には使用できません。

## 2. 比較対象の指標

性能比較に使用する指標は次の3個です。

- `native_ji.coherence`
- `pil_genre.typicality_q`
- `pil_genre.idiomaticity_q`

次の2個は表示・診断用に限定し、順位と性能集計から除外します。

- `genre_similarity_q`
- `pil_genre.inverse_cliche_q`

指標比較は完成楽曲hard gateの後に行います。hard gate不合格候補を、高い評価値だけを理由に完成楽曲archiveへ入れてはいけません。

## 3. 前提条件

リポジトリルートを作業ディレクトリにします。

```bash
cd /Users/ek4sfs/Documents/CPS
```

Python環境は次を使用します。

```text
backend/.venv/bin/python
```

次のlocal authorityが配置済みであることを確認します。

```text
local_authority/kawaii_future_bass_synthetic_v1/
local_authority/kawaii_future_bass_negative_synthetic_v1/
```

最低限、positive側のReferenceSetManifestとFeatureRecord群、negative側の`discrimination_report.json`が必要です。

```text
local_authority/kawaii_future_bass_synthetic_v1/authority/reference_set/
local_authority/kawaii_future_bass_negative_synthetic_v1/generated/discrimination_report.json
```

`local_authority/`以下のWAVと生成成果物はローカル検証用です。Gitへ追加しません。

## 4. 12 seedのfull-song生成

次の例はseed 0〜11を8 workerで生成します。

```bash
backend/.venv/bin/python \
  backend/tools/run_fixture_generation_cohort.py \
  --seeds 12 \
  --seed-start 0 \
  --workers 8 \
  --profile full-song \
  --output local_authority/mock_full_song_12seed_v1
```

出力先にはseedごとのProgram、Project、WAVとcohort reportが作成されます。

```text
mock_full_song_12seed_v1/
  cohort_report.json
  generation_manifest.json
  exploration_profile.json
  seed-0000/
    program.json
    project.json
    preview.wav
    arrangement_plan.json
  ...
  seed-0011/
```

`cohort_report.json`で、少なくとも次を確認します。

- `compile_survival`
- `duplicates.program_hash`
- `duplicates.project_hash`
- `duplicates.wav_hash`
- `pcm_continuity.fully_silent_one_second_window_count`
- `symbolic_coverage`
- `arrangement`
- `processing_time_ms`

全seed成功を要求する場合は、`compile_survival.success == seed_count`であることを確認します。

## 5. 候補WAVの特徴量抽出

各WAVから固定snapshotのFeatureRecordを作ります。

```bash
for n in 0 1 2 3 4 5 6 7 8 9 10 11; do
  seed=$(printf '%04d' "$n")
  backend/.venv/bin/python \
    backend/tools/extract_genre_feature.py \
    --wav "local_authority/mock_full_song_12seed_v1/seed-${seed}/preview.wav" \
    --manifest backend/songprogram_conformance/profiles/pcm32_genre_feature_extractor_v1.json \
    --output "local_authority/mock_full_song_12seed_v1/seed-${seed}/candidate_genre_feature.json" \
    >/dev/null || exit 1
done
```

抽出器はWAV先頭から固定10秒を使用します。10秒未満のWAVはpaddingやloopを行わず失敗します。

## 6. mock評価と完成楽曲hard gate

次を実行すると、配置済みlocal authorityを束ねたmock authorityを作り、全seedへNative JI、PIL、genre similarityおよび完成楽曲hard gateを適用します。

```bash
backend/.venv/bin/python \
  backend/tools/run_mock_sample_archive_trial.py \
  --cohort local_authority/mock_full_song_12seed_v1
```

主な出力は次のとおりです。

```text
mock_evaluation_authority.json
mock_sample_archive_report.json
seed-NNNN/mock_evaluation_report.json
seed-NNNN/mock_song_validity.json
```

mock成果物では必ず次を確認します。

```text
evaluation_mode = mock_failed_genre_discrimination
genre_similarity_authoritative = false
production_decisions_allowed = false
```

## 7. 完成楽曲hard gate

`mock_song_validity.json`の`archive_eligible`が完成楽曲archiveへの入場条件です。全項目合格時だけ`true`になります。

hard gateは次を検査します。

- 16〜64 bars
- 3〜8 sections
- 全sectionにrealizationが存在
- drums／bass／harmony／melodyのうち3 role以上が実際に発音
- symbolic coverageが8,500 basis points以上
- 完全無音1秒窓が0
- arrangement developmentが合格
- 実発音polyphonyが各trackの上限以内
- 同一materialの非identity変形recallが複数sectionに存在

失敗理由は`failure_codes`と`hard_checks`に保存されます。

`mock_sample_archive_report.json`では、次を分けて扱います。

- `preview_archive_count`: 試聴可能候補数
- `gen0_song_archive_count`: 完成楽曲hard gate合格数
- `gen0_song_archive`: hard gate合格後の候補だけを含む配列

## 8. 3指標の性能集計

mock genre similarityとinverse clicheを除外した集計を作成します。

```bash
backend/.venv/bin/python \
  backend/tools/analyze_three_metric_performance.py \
  --report local_authority/mock_full_song_12seed_v1/mock_sample_archive_report.json \
  --output local_authority/mock_full_song_12seed_v1/three_metric_performance_report.json
```

出力には各指標の次の値が含まれます。

- minimum
- median
- maximum
- mean
- population standard deviation
- range
- distinct value count
- seed ranking

`performance_conclusion`が次の場合、完成楽曲を選別する性能は評価できていません。

```text
distribution_only_no_viable_song_discrimination
```

これは指標計算の失敗ではなく、比較対象にhard gate合格曲が存在しないことを意味します。

## 9. 評価比較グラフ

mock evaluation report全体を確認するSVGは次で生成できます。

```bash
backend/.venv/bin/python \
  backend/tools/render_mock_evaluation_chart.py \
  --report local_authority/mock_full_song_12seed_v1/mock_sample_archive_report.json \
  --output local_authority/mock_full_song_12seed_v1/evaluation_comparison.svg
```

グラフを読むときは、最初にhard gate結果を確認します。Native JIやPIL値が高くても、`archive_eligible=false`の候補は完成楽曲上位候補ではありません。

## 10. 結果の解釈順序

結果は次の順で判断します。

1. sample／compile／renderの成功率
2. 完全無音、coverage、polyphonyなどの技術的成立性
3. 完成楽曲hard gate
4. 重複率と多様性
5. hard gate合格候補間のNative JI比較
6. hard gate合格候補間のPIL typicality／idiomaticity比較
7. 実音声聴取または音声対応LLMによる外部評価

PIL typicality／idiomaticityのrangeや標準偏差が極端に小さい場合、指標が候補間を十分に分離できていません。Native JI coherenceは格子上の一貫性を測りますが、メロディ、展開、フック、音色、ミックス品質を単独では保証しません。

## 11. 再実行と比較

同じmanifest、seed範囲、worker数で再実行した場合、Program／Project／評価reportのhashが一致することを確認します。別条件の比較では同じ出力ディレクトリを上書きせず、cohortごとに新しいディレクトリを使用します。

例:

```text
local_authority/mock_full_song_12seed_v1/
local_authority/mock_full_song_12seed_recall_fix_v1/
```

修正前後では、最低限次を比較します。

- compile survival
- GEN0完成楽曲成立率
- hard check別失敗数
- Program／Project／WAV重複率
- role presence
- transformed recall率
- 3指標の分布と順位
- seedあたり処理時間

## 12. 現在判明している制限

- FeatureExtractor v1のgenre similarityはジャンル識別能力が不足しています。
- mock genre modelによるinverse clicheは現状の比較対象にできません。
- reference rendererは決定論性優先で、full-song WAV生成時間が大きくなります。
- hard gate合格曲が0件のcohortでは、3指標の完成楽曲選別性能は確定できません。
- 変形recallが生成されない場合は、評価閾値を緩めずsampler／loweringを修正します。

## 13. 推奨する次の試験

full-song loweringへ非identity変形recall生成を実装した後、同じseed 0〜11を別ディレクトリへ再生成します。修正前後でseedを揃えることで、成立率の変化と3指標への影響を対応比較できます。
