# Audio transcription sample

`ingredients.wav` says:

> Four eggs, two hundred grams of rice, and four potatoes.

Duration: **3.86 seconds**. Format: mono 16 kHz, 16-bit PCM WAV.
Generated locally with macOS `say`, Samantha voice at 160 words per minute,
then converted to WAV with FFmpeg. This is synthetic speech for a manual smoke
test, not a human-recorded formal evaluation transcript.

In `ai/laas.py`, comment out the image test and uncomment the audio test in
`main()`. Set `SOCLAAS_AUDIO_MODEL` in your private `ai/.env` to the school's
speech-to-text model ID, then run from the repository root:

```bash
cd ai
uv run python laas.py
```

`transcribe_audio()` uses the same `SOCLAAS_BASE_URL` and `SOCLAAS_API_KEY` as
the image helpers. With a `/v1` base URL it uploads the file to
`POST /v1/audio/transcriptions`. It prints the transcript only; ingredient
parsing remains a separate `/ai/parse-items` request with `source: "voice"`.
