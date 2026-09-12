import { useState } from 'react';
import { Button, Card } from '../components/ui';

export interface GazeConsentCardProps {
  capable: boolean;
  consented: boolean;
  phase: string;
  message?: string;
  onEnable: () => void;
  onDisable: () => void;
}

export function GazeConsentCard({ capable, consented, phase, message, onEnable, onDisable }: GazeConsentCardProps) {
  const [busy, setBusy] = useState(false);

  if (!capable) {
    return (
      <Card className="gaze-consent-card">
        <h2>Eye tracking</h2>
        <p>Eye tracking is not supported on this device or browser. The games still work by clicking, as always.</p>
      </Card>
    );
  }

  return (
    <Card className="gaze-consent-card">
      <h2>Track your eyes?</h2>
      <p>
        With your permission, Dyscover can look at how your eyes move during games to see which parts of the screen get the most attention. The
        camera image is never saved or uploaded.
      </p>
      {!consented ? (
        <Button
          disabled={busy || phase === 'REQUESTED' || phase === 'CALIBRATING'}
          onClick={() => {
            setBusy(true);
            void onEnable();
            setBusy(false);
          }}
        >
          Yes, track my eyes
        </Button>
      ) : (
        <Button secondary onClick={onDisable}>
          Stop eye tracking
        </Button>
      )}
      {phase === 'REQUESTED' || phase === 'CALIBRATING' ? <p>{message ?? 'Preparing eye tracking…'}</p> : null}
      {message && phase === 'ERROR' ? <p>{message}</p> : null}
    </Card>
  );
}