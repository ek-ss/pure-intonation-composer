# ACE-Step 48曲リファレンスWAV生成・受け渡し手順

## 1. 目的

この文書は、別PC上のエージェントがACE-Stepを使って48曲を生成し、CPSの
kawaii future bass用synthetic reference cohortへ安全に受け渡すための作業指示である。

この集合のscopeは`synthetic_generator_conditioned`である。実在する商用楽曲群全体の
代表性を主張してはならない。また、WAV生成完了だけではCalibrationDecisionを
`promoted`にしてはならない。

## 2. 権威入力

生成条件の唯一の入力は次のJSONである。

```text
docs/ace_step_kawaii_future_bass_reference_captions_v1.json
```

48レコードは次のように分割済みである。

- calibration: 24曲
- validation: 12曲
- holdout: 12曲

`id`、`partition`、`seed`、`bpm`、`keyscale`、`lyrics`、`caption`を変更してはならない。
durationは全件90秒、拍子は4/4である。

## 3. 生成環境の固定

生成前に、次の情報を`generation_environment.json`へ記録する。

```json
{
  "generator": "ACE-Step",
  "model_snapshot": "実際に使用した完全なcheckpoint名またはdigest",
  "repository_commit": "ACE-Step実装のcommit SHA",
  "runtime": "Python/CUDA/PyTorch等の固定情報",
  "device": "GPU名",
  "task_type": "text2music",
  "inference_parameters": {},
  "caption_set": "ace_step_kawaii_future_bass_reference_captions_v1.json",
  "caption_set_sha256": "実ファイルから計算したSHA-256"
}
```

モデルsnapshot、sampler、steps、guidance、schedulerなど、音声へ影響する値は全48曲で
固定する。JSONにない生成パラメータを曲ごとに手調整してはならない。

ACE-Stepへの対応は次のとおり。

| caption set | ACE-Step入力 |
|---|---|
| `caption` | caption / prompt |
| `lyrics` | lyrics |
| `bpm` | bpm |
| `keyscale` | keyscale |
| 共通`time_signature` | timesignature |
| 共通`duration_seconds` | duration |
| `seed` | seed |
| 共通設定 | task_type=`text2music` |

自動caption rewriteを使う場合、その有無を全曲で統一して記録する。可能なら、この
caption集合を直接条件として使い、曲ごとに異なるLLM rewriteを加えない。

## 4. 出力ディレクトリ

別PCでは次の構成で作業する。`WORK_ROOT`は任意の安全なローカルパスでよい。

```text
WORK_ROOT/kawaii_future_bass_synthetic_v1/
├── generation_environment.json
├── captions/
│   └── ace_step_kawaii_future_bass_reference_captions_v1.json
├── masters/
│   ├── calibration/
│   ├── validation/
│   └── holdout/
├── clips/
│   ├── calibration/
│   ├── validation/
│   └── holdout/
├── receipts/
│   ├── calibration/
│   ├── validation/
│   └── holdout/
└── transfer_manifest.json
```

ファイル名はcaption recordの`id`をそのまま使う。

```text
masters/calibration/kfb_cal_001.wav
clips/calibration/kfb_cal_001.wav
receipts/calibration/kfb_cal_001.json
```

スペース、追加suffix、連番の付け直しは禁止する。

## 5. 生成規則

1. caption JSONの順序で処理する。
2. 各recordのseedとmetadataをそのまま指定する。
3. 最初に正常終了した90秒出力をmasterとして採用する。
4. 音楽的な好みを理由に再生成してはならない。
5. 無音、破損、長さ不足、NaN、書き込み失敗などの技術的失敗だけ再試行できる。
6. 再試行時も同一seed・同一設定を使い、全attemptのhashと理由をreceiptへ残す。
7. holdoutを聴いて選別、prompt修正、閾値調整してはならない。
8. 同一曲または派生版を複数partitionへ配置してはならない。

各曲のreceiptには少なくとも次を記録する。

```json
{
  "id": "kfb_cal_001",
  "partition": "calibration",
  "seed": 41001,
  "caption": "caption JSONと同一の文字列",
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

## 6. 評価用10秒クリップ

現行の固定feature extractorは入力WAVの先頭10秒を読む。イントロへの偏りを避け、
全曲に同じ規則を適用するため、masterの30.000秒から40.000秒を切り出し、clipの
先頭10秒とする。聴感に応じて開始位置を変更してはならない。

評価用clipの必須形式は次のとおり。

- 48,000 Hz
- PCM signed 32-bit little-endian
- stereoを維持（mono出力ならmonoのままでよい）
- 非圧縮WAV
- 正確に480,000 frames
- loudness normalization、limiter、EQ、fade追加は禁止

FFmpegを使用できる場合の例:

```bash
ffmpeg -v error -ss 30 -i masters/calibration/kfb_cal_001.wav \
  -t 10 -ar 48000 -c:a pcm_s32le clips/calibration/kfb_cal_001.wav
```

`-ss`の位置やFFmpeg versionを全曲で統一する。masterが40秒未満なら技術的失敗として
扱い、短い音声をzero paddingまたはloopしてはならない。

確認例:

```bash
ffprobe -v error -select_streams a:0 \
  -show_entries stream=sample_rate,channels,sample_fmt,duration \
  -of json clips/calibration/kfb_cal_001.wav
```

## 7. Hashとtransfer manifest

master、clip、receiptのSHA-256を計算する。macOSの例:

```bash
shasum -a 256 clips/calibration/kfb_cal_001.wav
```

`transfer_manifest.json`は48件すべてを含み、各entryには次を記録する。

- id
- partition
- master相対パスとSHA-256
- clip相対パスとSHA-256
- receipt相対パスとSHA-256
- frame count
- sample rate
- channels
- PCM format

entryは`calibration`、`validation`、`holdout`の順、その中ではidのUTF-8昇順に並べる。
manifest生成後にWAVやreceiptを変更してはならない。

## 8. 権利・provenance境界

ACE-Step生成物について、別PCのエージェントが独断で`rights_basis: owned`や
CalibrationDecisionの`promoted`を宣言してはならない。使用モデルと出力物の利用条件を
人間のownerが確認した後、CPS側でReferenceSourceProvenanceを発行する。

別PC側は次を証拠として保存する。

- 使用したモデルsnapshotとlicense
- ACE-Step実装のcommit
- 入力caption setのhash
- 完全な生成パラメータ
- generatorが返したreceiptまたはmetadata
- master/clipのraw hash
- 技術的失敗を含むattempt履歴

## 9. CPS PCへの配置

転送後の配置先は次とする。

```text
/Users/ek4sfs/Documents/CPS/local_authority/kawaii_future_bass_synthetic_v1/
├── masters/
├── clips/
│   ├── calibration/
│   ├── validation/
│   └── holdout/
├── receipts/
├── generation_environment.json
└── transfer_manifest.json
```

別PCの`clips/`はディレクトリ名と内部の相対パスを変更せず転送する。
`transfer_manifest.json`のパスが不変の検証対象であるため、`audio/`への改名は禁止する。
WAVをGit管理対象の`backend/`、
`docs/`、fixtureディレクトリへ置いてはならない。転送後はCPS PC上で全hashを再計算し、
transfer manifestとの一致を確認する。

## 10. 完了条件

- master 48件
- 10秒clip 48件
- receipt 48件
- calibration/validation/holdoutが24/12/12
- ID、seed、captionに重複なし
- clipは全件48 kHz PCM32で480,000 frames
- すべてのhashがtransfer manifestと一致
- holdoutを用いた選別や再調整なし
- 生成環境とattempt履歴が保存済み
- WAVはGitへ追加されていない

完了報告には、件数、失敗・再試行件数、モデルsnapshot、ACE-Step commit、manifest hash、
転送物のルートディレクトリだけを記載する。WAV内容や秘密情報をログへ埋め込まない。
