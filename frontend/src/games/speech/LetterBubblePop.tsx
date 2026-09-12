import { useEffect, useRef, useState } from 'react';
import type { SpeechTrial, SpeechResponseRecord } from './speechDefinitions';
import { SpeechRound } from './speechGameShell';

export interface SpeechGameViewProps {
  trial: SpeechTrial;
  onResponse: (response: SpeechResponseRecord) => void;
}

export function LetterBubblePop({ trial, onResponse }: SpeechGameViewProps) {
  const [hidden, setHidden] = useState(false);
  const hideTimer = useRef<number | undefined>(undefined);
  const hideAfterMs = trial.stimulus.hideAfterMs;

  useEffect(() => {
    setHidden(false);
    if (hideAfterMs) {
      hideTimer.current = window.setTimeout(() => setHidden(true), hideAfterMs);
      return () => {
        window.clearTimeout(hideTimer.current);
      };
    }
    return undefined;
  }, [trial.trialId, hideAfterMs]);

  const letters = trial.stimulus.promptText.split(' ');
  const prompt = hidden ? '?' : trial.stimulus.promptText;

  return (
    <div className="letter-pop">
      <SpeechRound
        title={trial.stimulus.levelName}
        levelName={trial.stimulus.levelName}
        levelSubtitle={trial.stimulus.levelSubtitle}
        promptText={letters.length > 1 ? letters.join(' ').toUpperCase() : prompt.toUpperCase()}
        onResult={result => onResponse(result as unknown as SpeechResponseRecord)}
        budgetMs={trial.stimulus.totalTimeMs}
      >
        <div className={`bubble-row ${hidden ? 'bubbles-hidden' : ''}`}>
          {letters.map(letter => (
            <span key={letter} className="letter-bubble">
              {hidden ? '•' : letter.toUpperCase()}
            </span>
          ))}
        </div>
      </SpeechRound>
    </div>
  );
}