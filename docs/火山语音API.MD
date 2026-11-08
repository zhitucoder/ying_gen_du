火山语音调用的API如下：

curl -L -X POST 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/submit' \
-H 'Content-Type: application/json' \
-H 'x-api-key: YOUR_API_KEY' \
-H 'X-Api-Resource-Id: volc.seedasr.auc' \
-H 'X-Api-Request-Id: 683695a0-97e8-4743-b9dd-453811120dd1' \
-H 'X-Api-Sequence: -1' \
-d '{
    "user": {
      "uid": "豆包语音"
    },
    "audio": {
      "url": "https://lf3-static.bytednsdoc.com/obj/eden-cn/lm_hz_ihsph/ljhwZthlaukjlkulzlp/console/bigtts/zh_female_cancan_mars_bigtts.mp3",
      "format": "mp3",
      "codec": "raw",
      "rate": 16000,
      "bits": 16,
      "channel": 1
    },
    "request": {
      "model_name": "bigmodel",
      "enable_itn": true,
      "enable_punc": false,
      "enable_ddc": false,
      "enable_speaker_info": false,
      "enable_channel_split": false,
      "show_utterances": false,
      "vad_segment": false,
      "sensitive_words_filter": ""
    }
  }'

API用法：

  curl -L -X POST 'https://openspeech.bytedance.com/api/v3/auc/bigmodel/query' \
-H 'Content-Type: application/json' \
-H 'x-api-key: YOUR_API_KEY' \
-H 'X-Api-Resource-Id: volc.seedasr.auc' \
-H 'X-Api-Request-Id: 683695a0-97e8-4743-b9dd-453811120dd1' \
-d '{}'