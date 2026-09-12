import { useState } from 'react';
import type { SpeechTrial, SpeechResponseRecord } from './speechDefinitions';
import { SpeechRound } from './speechGameShell';

export interface SpeechGameViewProps {
  trial: SpeechTrial;
  onResponse: (response: SpeechResponseRecord) => void;
}

export function SoundQuestAdventure({ trial, onResponse }: SpeechGameViewProps) {
  const [unlocked, setUnlocked] = useState(0);
  const storyParts = trial.stimulus.storyParts ?? [];
  const onResult = (result: import('./speechRecognition').SpeechRecognitionResult) => {
    if (result.speechDetected && storyParts.length) {
      setUnlocked(current => Math.min(current + 1, storyParts.length));
    }
    onResponse(result as unknown as SpeechResponseRecord);
  };

  return (
    <div className="sound-quest">
      {storyParts.length ? (
        <div className="story-strip" aria-live="polite">
          {storyParts.map((part, index) => (
            <p key={part} className={index < unlocked ? 'story-revealed' : 'story-locked'}>
              {index < unlocked ? part : '✦ ✦ ✦'}
            </p>
          ))}
        </div>
      ) : null}
      <SpeechRound title={trial.stimulus.levelName} levelName={trial.stimulus.levelName} levelSubtitle={trial.stimulus.levelSubtitle} promptText={trial.stimulus.promptText} onResult={onResult} />
    </div>
  );
}