# ACE-Step ジャンル外negative cohort生成・受け渡し手順

## 1. 目的

この文書は、kawaii future bass positive cohortに対する特徴量識別試験用として、
ACE-Step由来のジャンル外negative 48曲を別PCで生成し、CPSへ受け渡す手順を定める。
negative集合は特徴抽出器の識別性能を測る対照群であり、ジャンルの優劣を示すものではない。

## 2. 固定入力

唯一のcaption入力は次のファイルとする。

```text
docs/ace_step_kawaii_future_bass_negative_captions_v1.json
```

- calibration: 24曲（hard 12、medium 6、far 6）
- validation: 12曲（hard 6、medium 3、far 3）
- holdout: 12曲（hard 6、medium 3、far 3）

`id`、`partition`、`negative_tier`、`genre_label`、`seed`、`bpm`、`keyscale`、
`lyrics`、`caption`を変更してはならない。全曲90秒、4/4、text2musicで生成する。

## 3. 最重要の選別禁止

各recordについて、最初に技術的に正常な出力を採用する。positiveとの類似度、聴感、
ジャンルらしさ、曲の好みを理由に再生成・除外・partition移動してはならない。
holdoutは生成完了後も、閾値決定、特徴量設計、prompt修正には使用しない。

再試行できるのは、無音、破損、40秒未満、NaN、生成処理失敗などの技術的失敗だけである。
再試行時もseedと全パラメータを固定し、全attemptと理由をreceiptへ記録する。

## 4. positive cohortとの生成条件統制

比較対象のpositive cohortと次を一致させる。

- ACE-Step repository commitとmodel snapshot
- runtime、device、sampler、steps、guidance、scheduler
- caption rewriteの有無
- 90秒の要求duration
- 30.000秒から40.000秒の固定clip抽出
- FFmpeg versionと引数
- 48 kHz、signed PCM32 little-endian、480,000 frames
- loudness normalization、EQ、limiter、fadeを追加しない

BPMとkeyscaleは各negative recordの指定値を使い、positiveの分布に近い条件を意図的に含む。
これにより、単純なtempo・調性差だけで分類することを防ぐ。

## 5. 作業ディレクトリ

```text
WORK_ROOT/kawaii_future_bass_negative_synthetic_v1/
├── generation_environment.json
├── captions/
│   └── ace_step_kawaii_future_bass_negative_captions_v1.json
├── masters/{calibration,validation,holdout}/
├── clips/{calibration,validation,holdout}/
├── receipts/{calibration,validation,holdout}/
└── transfer_manifest.json
```

ファイル名はcaption `id`をそのまま使う。例:

```text
masters/calibration/kfb_neg_cal_001.wav
clips/calibration/kfb_neg_cal_001.wav
receipts/calibration/kfb_neg_cal_001.json
```

## 6. receipt

各receiptにはpositive cohortの項目に加えて次を含める。

```json
{
  "id": "kfb_neg_cal_001",
  "partition": "calibration",
  "negative_tier": "hard",
  "genre_label": "melodic_future_bass",
  "seed": 51001,
  "caption": "caption setと同一の文字列",
  "lyrics": "[Instrumental]",
  "bpm": 150,
  "keyscale": "C major",
  "timesignature": "4/4",
  "requested_duration_seconds": 90,
  "master_wav_sha256": "sha256:...",
  "clip_wav_sha256": "sha256:...",
  "attempt_count": 1,
  "technical_failures": [],
  "generator_receipt": {}
}
```

`generation_environment.json`にはpositive cohortで使用した環境との一致・差分を明記する。

## 7. clipとmanifest

全曲一律にmasterの30.000秒から10秒を抽出する。

```bash
ffmpeg -v error -ss 30 -i masters/calibration/kfb_neg_cal_001.wav \
  -t 10 -ar 48000 -c:a pcm_s32le clips/calibration/kfb_neg_cal_001.wav
```

transfer manifestの形式、hash計算、entry順序はpositive handoffと同一とする。
順序はcalibration、validation、holdout、その中でidのUTF-8昇順とする。

## 8. CPSへの配置

```text
/Users/ek4sfs/Documents/CPS/local_authority/kawaii_future_bass_negative_synthetic_v1/
├── masters/
├── clips/
├── receipts/
├── captions/
├── generation_environment.json
└── transfer_manifest.json
```

`clips/`を改名せず、manifest内部の相対パスを維持する。WAVをGitへ追加しない。
権利basisとCalibrationDecisionは、転送後に人間ownerの確認を受けてCPS側で発行する。

## 9. 完了条件

- 48曲、partition 24/12/12、tier 24/12/12
- ID、seed、captionが一意
- 全clipが48 kHz PCM32、正確に480,000 frames
- 全hash、receipt、caption bindingが一致
- positiveと同一の生成snapshot・推論条件
- 技術的失敗以外の再生成なし
- similarityを用いた採否選別なし
- holdout未参照
- WAVはGit管理対象外

CPS側ではまずv1特徴量のpositive-positive、positive-negative、tier別分離を測定する。
holdoutを確認する前に、calibrationで閾値、validationで設計判断を固定する。
