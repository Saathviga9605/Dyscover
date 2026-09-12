import { ReactNode, useState } from 'react';
import { Button, Card } from '../components/ui';
import { useLanguage } from '../l10n';
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
  const { t } = useLanguage();
  const [busy, setBusy] = useState(false);
  const usable = capabilities.recognition || capabilities.audio;

  if (!usable) {
    return (
      <Card className="gaze-consent-card">
        <h2>{t('speech.cardUnavailableTitle')}</h2>
        <p>{t('speech.cardUnavailableCopy')}</p>
      </Card>
    );
  }

  return (
    <Card className="gaze-consent-card">
      <h2>{t('speech.cardTitle')}</h2>
      <p>{consented ? t('speech.cardConsentedCopy') : t('speech.cardRequestCopy')}</p>
      {!consented ? (
        <Button
          disabled={busy || phase === 'REQUESTED'}
          onClick={() => {
            setBusy(true);
            void onEnable();
            setBusy(false);
          }}
        >
          {t('speech.cardEnable')}
        </Button>
      ) : (
        <Button secondary onClick={onDisable}>
          {t('speech.cardDisable')}
        </Button>
      )}
      {phase === 'REQUESTED' ? <p>{message ?? t('speech.checkingMic')}</p> : null}
      {phase === 'ERROR' && message ? <p>{message}</p> : null}
    </Card>
  );
}

export function SpeechConsentGate({ children, ...props }: SpeechConsentCardProps & { children?: ReactNode }) {
  const { consented } = props;
  return <>{consented ? children : <SpeechConsentCard {...props} />}</>;
}