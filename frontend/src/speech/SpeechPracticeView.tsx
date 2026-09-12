import { useCallback, useEffect, useRef, useState } from 'react';
import { Mascot, MascotBubble } from '../components/ui';
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
  const [index, setIndex] = useState(0);
  const [listening, setListening] = useState(false);
  const [phase, setPhase] = useState<SpeechProviderPhase>('NOT_CONFIGURED');
  const [lastResult, setLastResult] = useState<SpeechAnalysisResult | null>(null);
  const analyzerRef = useRef<SpeechSignalAnalyzer | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const timerRef = useRef<number | undefined>(undefined);

  useEffect(() => {
    analyzerRef.current = new SpeechSignalAnalyzer(capabilities);
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

  if (!tasks.length) return <div className="empty-state" role="status">Getting a listening activity ready…</div>;

  const task = tasks[index];

  return (
    <div className="game-shell speech-practice">
      <div className="game-topbar">
        <button className="game-back" onClick={onAbandon} aria-label="Leave practice">←</button>
        <div className="game-title"><span className="game-mascot-dot">✦</span><strong>{activityName}</strong></div>
      </div>
      <div className="game-progress-row"><span>Say {index + 1} of {tasks.length}</span><div className="game-progress"><span style={{ width: `${Math.round((index / tasks.length) * 100)}%` }} /></div><span>{Math.round((index / tasks.length) * 100)}%</span></div>
      <main className="game-stage">
        <div className="speech-prompt" key={task.task_id}>
          <span className="child-kicker">{activityDescription}</span>
          <Mascot mood={listening ? 'thinking' : 'happy'} size="medium" />
          <p className="speech-target">{task.expected_text}</p>
          <button className="child-start speech-mic-button" onClick={() => void listen()} disabled={listening || phase === 'ERROR'}>
            {listening ? 'Listening…' : 'Tap here, then say it'}
          </button>
          {phase === 'ERROR' && <p>We could not hear the microphone. Please check that it is allowed and try again.</p>}
          {phase === 'LISTENING' && <MascotBubble mood="thinking">I’m listening…</MascotBubble>}
          {lastResult && <div className="speech-feedback" role="status">{lastResult.correct ? 'Great job!' : 'Almost! Let’s try the next one.'}</div>}
        </div>
      </main>
    </div>
  );
}