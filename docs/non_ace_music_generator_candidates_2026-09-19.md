# ACE-Step以外の音楽生成モデル候補（2026-09-19時点）

## 目的

同一generator由来の癖をgenre特徴と誤認しないため、ACE-Step cohortとは独立した
external-generator validation cohortを作る候補を整理する。採用時はprovider名だけでなく、
model ID、snapshotまたはAPI version、全request、seed、response metadata、利用規約snapshot、
raw audio hashを固定する。

## 結論

第一候補は`Eleven Music v2.5`、第二候補は`Lyria 3 Pro Preview`、ローカル再現性の比較対象は
`MusicGen stereo`または`SongGeneration 2`とする。ただし、一つの外部modelで48曲を置換する
のではなく、まず各model 4曲のpilotでcaption追従、無音率、clip品質、receipt取得性を比較する。

## 候補比較

### 1. Eleven Music v2.5 — 優先pilot

- 公式APIは3秒から600秒を受け付け、90秒masterを直接生成できる。
- `music_v2_5`はcomposition planによるsection制御とinstrumental生成に対応する。
- seed入力はあるが、公式仕様は同一入力でも完全再現を保証しない。そのためresponse hashと
  model IDを保存し、再生成一致をnormative要件にしてはならない。
- managed APIなのでcheckpoint bytesは固定できない。API側更新を跨ぐcohort混在は禁止する。
- 有料planとMusic Termsの確認が必要。評価・保存・特徴抽出が契約上許可されることをownerが
  確認してからprovenanceを発行する。

公式資料:

- https://elevenlabs.io/docs/api-reference/music/compose
- https://elevenlabs.io/docs/eleven-api/guides/how-to/music/composition-plans
- https://elevenlabs.io/docs/help-center/product/core-capabilities/music/what-is-eleven-music

### 2. Google Lyria 3 Pro Preview — managed APIの独立検証

- `lyria-3-pro-preview`は184秒、`lyria-3-clip-preview`は30秒を生成できるため、Proなら90秒
  master契約を満たせる。
- 2026-03-25時点でpublic previewであり、model lifecycleと出力再現性は固定checkpointより弱い。
- request ID、model ID、region、API endpoint、request/response metadataを必ず保存する。
- preview利用条件、課金、生成物の保存・評価利用条件をownerが確認するまでauthorityへ昇格しない。

公式資料:

- https://docs.cloud.google.com/vertex-ai/docs/release-notes#March_25_2026

### 3. Meta MusicGen stereo — 非商用research baseline

- local checkpointをdigest固定でき、seed、sampling parameter、runtimeを保存しやすい。
- native生成は32 kHz。30秒を超える生成はextended generationを使えるが、90秒では継ぎ目や
  長期構造がmanaged full-song modelより弱い可能性がある。
- model weightsはCC BY-NC 4.0。商用系authorityには混ぜず、非商用research cohortとして
  provenanceとattributionを分離する。
- `facebook/musicgen-stereo-medium`を4曲pilotの既定候補とする。

公式資料:

- https://github.com/facebookresearch/audiocraft/blob/main/docs/MUSICGEN.md
- https://github.com/facebookresearch/audiocraft/blob/main/model_cards/MUSICGEN_MODEL_CARD.md

### 4. Tencent SongGeneration 2 — local full-song pilot候補

- 公式repositoryはSongGeneration-v2-largeを公開し、最大4分30秒、instrumental出力、
  text description制御を掲げる。
- local checkpointを保持でき、90秒以上の長さとsnapshot固定を両立しやすい。
- 約22 GB以上のGPU memory目安があり、環境負荷が高い。
- repositoryとweightのLICENSE本文、出力利用条件、第三者componentを取得時snapshotで確認する。
  READMEの「commercial-grade」は権利許諾そのものとして扱わない。

公式資料:

- https://github.com/tencent-ailab/SongGeneration

### 5. Stable Audio Open 1.0 — 10秒clipの補助対照

- local model、stereo 44.1 kHz、最大47秒で、30–40秒clipは取得できる。
- positiveと同じ90秒master契約は満たさないため、主cohortではなくclip-level robustness試験に限る。
- codeはMITだがweightは別のCommunity License。取得時のlicenseを保存する。

公式資料:

- https://github.com/Stability-AI/stable-audio-tools
- https://github.com/Stability-AI/stable-audio-open-demo/blob/main/README.md

### 6. YuE / YuE2 — 現時点では保留

- full-song生成とartifact保存の能力は有望だが、公式repository内で世代ごとのweight licenseが
  異なる。YuE READMEのApache 2.0説明とYuE2 weightのCC BY-NC 4.0を混同してはならない。
- 使用checkpointを確定して該当LICENSEをhash固定できるまでpilotへ入れない。

公式資料:

- https://github.com/multimodal-art-projection/YuE
- https://github.com/multimodal-art-projection/YuE/blob/main/MODEL_LICENSE

## 推奨pilot

1. hard negativeから4 captionを事前固定する。
2. Eleven Music v2.5、Lyria 3 Pro、MusicGen stereo、SongGeneration 2で各4曲を生成する。
3. 90秒に対応しないmodelは別のclip-only experimentとして分離する。
4. providerごとに独立したReferenceSet IDとprovenanceを発行する。
5. modelを跨いで再生成結果を聴感選別しない。
6. calibrationだけでprovider差とgenre差を分析し、validation前に採用feature specを固定する。
7. holdoutは最終判定まで開封しない。

## 採用判定

- prompt/caption追従を機械可読receiptで追跡できる
- 90秒masterと30–40秒clipを生成できる
- instrumentalを強制できる
- model/versionまたはcheckpoint digestを記録できる
- requestとseedを保存できる
- storage、feature extraction、evaluationの権利をownerが確認できる
- 技術的失敗と音楽的な不満を区別できる
- API更新やweight license変更をcohort境界として扱える

SunoやUdioは、安定した公式developer API、version固定、receipt、評価用途の権利条件をこの調査で
確定できなかったため、現段階のauthoritative cohort候補には含めない。
