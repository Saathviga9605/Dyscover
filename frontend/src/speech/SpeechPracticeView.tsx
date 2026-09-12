import { useCallback, useEffect, useRef, useState } from 'react';
import { Mascot, MascotBubble } from '../components/ui';
import { useLanguage } from '../l10n';
import { getStoredLocale } from '../l10n/languages';
import { SpeechSignalAnalyzer } from './analyzer';
import type { ReadingTask, SpeechAnalysisResult, SpeechCapabilities, SpeechProviderPhase } from './types';

export interface SpeechPracticeViewProps {
  activityName: string;
  activityDescription: string;
  tasks: ReadingTask[];
  capabilities: SpeechCapabilities;
  difficulty: number;
  onResult: (task: ReadingTask, result: SpeechAnalysisResult, index: number) => void;
  onComplete: () => void;
  onAbandon: () => void;
  onPhaseChange?: (phase: SpeechProviderPhase, message?: string) => void;
}

export const SPEECH_CONSENT_KEY = 'dyscover-speech-consent';

export function SpeechPracticeView({ activityName, activityDescription, tasks, capabilities, difficulty, onResult, onComplete, onAbandon, onPhaseChange }: SpeechPracticeViewProps) {
  const { t } = useLanguage();
  const [index, setIndex] = useState(0);
  const [listening, setListening] = useState(false);
  const [phase, setPhase] = useState<SpeechProviderPhase>('NOT_CONFIGURED');
  const [lastResult, setLastResult] = useState<SpeechAnalysisResult | null>(null);
  const analyzerRef = useRef<SpeechSignalAnalyzer | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    analyzerRef.current = new SpeechSignalAnalyzer(capabilities, { lang: getStoredLocale() });
    setPhase('READY');
    onPhaseChange?.('READY');
    return () => {
      abortRef.current?.abort();
      window.clearTimeout(timerRef.current);
    };
  }, [capabilities, onPhaseChange]);

  const listen = useCallback(async () => {
    const task = tasks[index];
    if (!task || listening) return;
    setListening(true);
    setLastResult(null);
    setPhase('LISTENING');
    onPhaseChange?.('LISTENING');
    const controller = new AbortController();
    abortRef.current = controller;
    setPhase('PROCESSING');
    onPhaseChange?.('PROCESSING');
    try {
      const result = await analyzerRef.current?.observe(task, controller.signal);
      if (result) {
        setLastResult(result);
        onResult(task, result, index);
        setPhase('READY');
        onPhaseChange?.('READY');
        if (index >= tasks.length - 1) {
          timerRef.current = window.setTimeout(onComplete, 900);
        } else {
          timerRef.current = window.setTimeout(() => setIndex(index + 1), 900);
        }
      }
    } catch {
      setPhase('ERROR');
      onPhaseChange?.('ERROR');
    } finally {
      setListening(false);
    }
  }, [index, listening, tasks, onResult, onComplete, onPhaseChange]);

  if (!tasks.length) return <div className="empty-state" role="status">{t('speech.launchEmpty')}</div>;

  const task = tasks[index];

  return (
    <div className="game-shell speech-practice">
      <div className="game-topbar">
        <button className="game-back" onClick={onAbandon} aria-label={t('practice.abandon')}>←</button>
        <div className="game-title"><span className="game-mascot-dot">✦</span><strong>{activityName}</strong></div>
      </div>
      <div className="game-progress-row"><span>{t('speech.count', { index: index + 1, total: tasks.length })}</span><div className="game-progress"><span style={{ width: `${Math.round((index / tasks.length) * 100)}%` }} /></div><span>{Math.round((index / tasks.length) * 100)}%</span></div>
      <main className="game-stage">
        <div className="speech-prompt" key={task.task_id}>
          <span className="child-kicker">{activityDescription}</span>
          <Mascot mood={listening ? 'thinking' : 'happy'} size="medium" />
          <p className="speech-target">{task.expected_text}</p>
          <button className="child-start speech-mic-button" onClick={() => void listen()} disabled={listening || phase === 'ERROR'}>
            {listening ? t('speech.listening') : t('speech.tapToSay')}
          </button>
          {phase === 'ERROR' && <p>{t('speech.errorListening')}</p>}
          {phase === 'LISTENING' && <MascotBubble mood="thinking">{t('speech.listeningBubble')}</MascotBubble>}
          {lastResult && <div className="speech-feedback" role="status">{lastResult.correct ? t('game.shell.feedbackGreat') : t('speech.feedbackAlmost')}</div>}
        </div>
      </main>
    </div>
  );
}