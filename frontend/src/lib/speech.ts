// The Web Speech API is not in TypeScript's DOM types and is prefixed in Safari and Chrome.
type RecognitionEvent = { results: ArrayLike<ArrayLike<{ transcript: string }>> };
type Recognition = {
  lang: string;
  interimResults: boolean;
  onresult: ((event: RecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};
type RecognitionConstructor = new () => Recognition;

function recognitionConstructor(): RecognitionConstructor | undefined {
  const w = window as unknown as {
    SpeechRecognition?: RecognitionConstructor;
    webkitSpeechRecognition?: RecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition;
}

export function speechIsSupported(): boolean {
  return recognitionConstructor() !== undefined;
}

/**
 * Listens for one utterance, in the browser. No audio leaves the device through us.
 * Calls back with the transcript so far, then once more when listening ends.
 */
export function listen(handlers: { onTranscript: (text: string) => void; onEnd: () => void }): () => void {
  const Constructor = recognitionConstructor();
  if (!Constructor) {
    handlers.onEnd();
    return () => {};
  }
  const recognition = new Constructor();
  recognition.lang = "en-SG";
  recognition.interimResults = true;
  recognition.onresult = (event) => {
    const text = Array.from(event.results, (result) => result[0]?.transcript ?? "").join(" ");
    handlers.onTranscript(text.trim());
  };
  recognition.onerror = () => handlers.onEnd();
  recognition.onend = () => handlers.onEnd();
  recognition.start();
  return () => recognition.stop();
}
