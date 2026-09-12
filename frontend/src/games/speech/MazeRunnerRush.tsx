import { useEffect, useRef, useState } from 'react';
import type { SpeechTrial, SpeechResponseRecord } from './speechDefinitions';
import { SpeechRound } from './speechGameShell';

export interface SpeechGameViewProps {
  trial: SpeechTrial;
  onResponse: (response: SpeechResponseRecord) => void;
}

export function MazeRunnerRush({ trial, onResponse }: SpeechGameViewProps) {
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

  const modifier = [
    trial.stimulus.flashMode ? 'maze-flash' : '',
    trial.stimulus.distractionMode ? 'maze-distraction' : '',
  ].filter(Boolean).join(' ');

  return (
    <div className={`maze-rush ${modifier}`}>
      <SpeechRound
        title={trial.stimulus.levelName}
        levelName={trial.stimulus.levelName}
        levelSubtitle={trial.stimulus.levelSubtitle}
        promptText={trial.stimulus.promptText}
        onResult={result => onResponse(result as unknown as SpeechResponseRecord)}
        budgetMs={trial.stimulus.totalTimeMs}
      >
        <div className={`maze-path-target ${hidden ? 'target-hidden' : ''}`} aria-live="polite">
          {hidden ? '…' : trial.stimulus.promptText}
        </div>
      </SpeechRound>
    </div>
  );
}