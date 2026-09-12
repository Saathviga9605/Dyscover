import { ReactNode, useState } from 'react';
import { Button, Card } from '../components/ui';
import type { SpeechCapabilities } from './types';

export interface SpeechConsentCardProps {
  capabilities: SpeechCapabilities;
  consented: boolean;
  phase: string;
  message?: string;
  onEnable: () => void;
  onDisable: () => void;
}

export function SpeechConsentCard({ capabilities, consented, phase, message, onEnable, onDisable }: SpeechConsentCardProps) {
  const [busy, setBusy] = useState(false);
  const usable = capabilities.recognition || capabilities.audio;

  if (!usable) {
    return (
      <Card className="gaze-consent-card">
        <h2>Read aloud practice</h2>
        <p>This activity needs a microphone so your child can say the words aloud. A microphone is not available on this device, so this activity is skipped — other practice activities still work.</p>
      </Card>
    );
  }

  return (
    <Card className="gaze-consent-card">
      <h2>Use the microphone for this activity?</h2>
      <p>{consented ? 'The microphone is available. Your child can say each prompt aloud. The audio is never saved or uploaded.' : 'With permission, your child can say each prompt aloud so the activity can hear the answer. Audio is only used for the moment, then discarded — it is never saved or uploaded.'}</p>
      {!consented ? (
        <Button
          disabled={busy || phase === 'REQUESTED'}
          onClick={() => {
            setBusy(true);
            void onEnable();
            setBusy(false);
          }}
        >
          Yes, let this activity listen
        </Button>
      ) : (
        <Button secondary onClick={onDisable}>
          Turn the microphone off
        </Button>
      )}
      {phase === 'REQUESTED' ? <p>{message ?? 'Checking the microphone…'}</p> : null}
      {phase === 'ERROR' && message ? <p>{message}</p> : null}
    </Card>
  );
}

export function SpeechConsentGate({ children, ...props }: SpeechConsentCardProps & { children?: ReactNode }) {
  const { consented } = props;
  return <>{consented ? children : <SpeechConsentCard {...props} />}</>;
}