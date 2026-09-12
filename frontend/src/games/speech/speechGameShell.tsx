import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Mascot, MascotBubble } from '../../components/ui';
import { SpeechRecognitionController, type SpeechRecognitionResult } from './speechRecognition';

export type SpeechListenPhase = 'idle' | 'listening' | 'done' | 'error';

export interface SpeechRoundProps {
  title: string;
  levelName: string;
  levelSubtitle: string;
  promptText: string;
  children?: ReactNode;
  onResult: (result: SpeechRecognitionResult) => void;
  onInterim?: (transcript: string) => void;
  budgetMs?: number;
}

export function SpeechRound({ title, levelName, levelSubtitle, promptText, children, onResult, onInterim, budgetMs }: SpeechRoundProps) {
  const [phase, setPhase] = useState<SpeechListenPhase>('idle');
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState('');
  const controllerRef = useRef<SpeechRecognitionController | null>(null);

  const start = useCallback(() => {
    if (controllerRef.current) return;
    setPhase('listening');
    setListening(true);
    setInterim('');
    const controller = new SpeechRecognitionController({
      onInterim: text => {
        setInterim(text);
        onInterim?.(text);
      },
      budgetMs,
    });
    controllerRef.current = controller;
    void controller
      .start()
      .then(result => {
        setPhase(result.errorType ? 'error' : 'done');
        onResult(result);
      })
      .finally(() => {
        setListening(false);
        controllerRef.current = null;
      });
  }, [budgetMs, onInterim, onResult]);

  useEffect(() => {
    setPhase('idle');
    setInterim('');
    const timer = window.setTimeout(start, 250);
    return () => {
      window.clearTimeout(timer);
      controllerRef.current?.abort();
      controllerRef.current = null;
    };
  }, [promptText, start]);

  const feedback = interim || (phase === 'listening' ? 'listening…' : '');

  return (
    <div className="speech-round">
      <div className="speech-round-head">
        <span className="child-kicker">{levelName}</span>
        <p>{levelSubtitle}</p>
      </div>
      <div className="speech-prompt" key={promptText}>
        <Mascot mood={listening ? 'thinking' : 'happy'} size="medium" />
        <p className="speech-target">{promptText}</p>
        {children}
        <button
          className="child-start speech-mic-button"
          onClick={() => void start()}
          disabled={listening}
          aria-label={listening ? 'Listening for the answer' : 'Tap here, then say it'}
        >
          {listening ? 'Listening…' : phase === 'error' ? 'Tap to try again' : 'Speak it'}
        </button>
      </div>
      {feedback ? <MascotBubble mood="thinking">{feedback}</MascotBubble> : null}
    </div>
  );
}