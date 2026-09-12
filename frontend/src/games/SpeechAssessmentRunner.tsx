import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { speechAssessmentPlan } from './speech/speechDefinitions';
import { GameEngine, type GameState, type AssessmentSession } from './engine';
import { GameComplete, GameIntro, GameShell } from './components/GameShell';
import { SoundQuestAdventure, LetterBubblePop, MazeRunnerRush } from './speech';
import { ensureAssessmentSession, persistEvent, persistSpeechAssessmentTrial, persistSummary, persistTrial } from './persistence';
import { SpeechConsentGate, SPEECH_CONSENT_KEY, probeSpeechCapabilities } from '../speech';
import type { SpeechTrial, SpeechResponseRecord } from './speech/speechDefinitions';
import { speechFeaturesEventPayload } from './speech/speechTelemetry';
import { speechSupported } from './speech/speechRecognition';
import { useLanguage } from '../l10n';
import { languageName, speechAssessmentPlanFor } from '../l10n/languages';
import { Mascot } from '../components/ui';

export function SpeechAssessmentRunner() {
  const navigate = useNavigate();
  const { t, language, setLanguage } = useLanguage();
  const availablePlan = speechAssessmentPlanFor(language);
  const [gameIndex, setGameIndex] = useState(0);
  const [state, setState] = useState<GameState>('LOADING');
  const [trial, setTrial] = useState<SpeechTrial>();
  const [feedback, setFeedback] = useState<string>();
  const [error, setError] = useState<string>();
  const engineRef = useRef<GameEngine<SpeechTrial> | null>(null);
  const advanceTimer = useRef<number | undefined>(undefined);
  const sessionRef = useRef<AssessmentSession | null>(null);
  const backendTrialIds = useRef(new Map<string, string>());
  const persistedSeqByTrial = useRef(new Map<string, number>());
  const [consented, setConsented] = useState(() => window.localStorage.getItem(SPEECH_CONSENT_KEY) === 'granted');
  const capable = speechSupported();
  const definition = speechAssessmentPlan[gameIndex];

  useEffect(() => { if (availablePlan.length === 0) return; let active = true; const sessionPromise = sessionRef.current ? Promise.resolve(sessionRef.current) : ensureAssessmentSession(); sessionPromise.then(session => { if (!active) return; sessionRef.current = session; engineRef.current = new GameEngine(definition, session); setState('INTRO'); }).catch(() => { if (active) { const localSession = sessionRef.current ?? undefined; engineRef.current = new GameEngine(definition, localSession); const engine = engineRef.current; sessionRef.current = engine.session; setError(t('game.connectFallback')); setState('INTRO'); } }); return () => { active = false; window.clearTimeout(advanceTimer.current); }; }, [gameIndex, definition, availablePlan.length, t]);

  const persistNewEvents = () => { const engine = engineRef.current; if (!engine) return; const fallbackTrialId = engine.trials.at(-1)?.trialId; for (const event of engine.events) { const localTrialId = event.trialId ?? fallbackTrialId; if (!localTrialId) continue; const backendId = backendTrialIds.current.get(localTrialId); if (!backendId) continue; const since = persistedSeqByTrial.current.get(localTrialId) ?? 0; if (event.sequenceNumber <= since) continue; void persistEvent(backendId, event); persistedSeqByTrial.current.set(localTrialId, event.sequenceNumber); } };
  const startTrial = () => { const engine = engineRef.current; if (!engine) return; const next = engine.beginTrial(engine.trials.length); persistNewEvents(); setTrial(next); setFeedback(undefined); setState('PLAYING'); };
  const startGame = () => { const engine = engineRef.current; if (!engine) return; engine.start(); persistNewEvents(); startTrial(); };

  const enableMic = async () => { setConsented(true); window.localStorage.setItem(SPEECH_CONSENT_KEY, 'granted'); startGame(); };
  const disableMic = () => { setConsented(false); window.localStorage.setItem(SPEECH_CONSENT_KEY, 'denied'); };

  const submit = async (response: SpeechResponseRecord) => {
    const engine = engineRef.current;
    if (!engine || !trial || state !== 'PLAYING') return;
    const updated = engine.recordResponse(trial, response);
    engine.completeTrial(updated);
    const speechTrial = updated as SpeechTrial;
    const evidence = speechTrial.metadata?.evidence;
    if (evidence) engine.emit('SPEECH_FEATURES', speechFeaturesEventPayload(evidence), trial.trialId);
    setFeedback(updated.correct ? t('game.shell.feedbackGreat') : t('game.shell.feedbackAlmost'));
    setState('FEEDBACK');
    const backendId = await persistTrial(engine.session.assessmentId ?? engine.session.sessionId, definition.id, updated);
    backendTrialIds.current.set(trial.trialId, backendId ?? trial.trialId);
    persistNewEvents();
    void persistSpeechAssessmentTrial(engine.session.assessmentId ?? engine.session.sessionId, speechTrial, backendId ?? null);
    advanceTimer.current = window.setTimeout(() => {
      if (engine.trials.length >= definition.totalTrials) { engine.completeGame(); persistNewEvents(); setState('GAME_COMPLETE'); }
      else startTrial();
    }, 900);
  };

  const continueAfterGame = () => { const engine = engineRef.current; if (!engine) return; if (gameIndex >= availablePlan.length - 1) { engine.completeSession(); void persistSummary(engine.session.assessmentId ?? engine.session.sessionId, { games: engine.session.games, totalTrials: engine.session.totalTrials }); navigate('/parent/dashboard'); return; } setGameIndex(index => index + 1); };
  const abandonAndLeave = () => { const engine = engineRef.current; if (!engine) return; if (state === 'PLAYING' || state === 'FEEDBACK') { engine.emit('SESSION_ABANDONED', { reason: 'child-exit' }, engine.trials.at(-1)?.trialId); persistNewEvents(); } navigate('/child/assessment'); };

  if (availablePlan.length === 0) return (
    <div className="child-space hub-page">
      <div className="child-topbar"><span className="child-brand"><span className="brand-mark">✦</span>Dyscover</span></div>
      <div className="hub-unavailable">
        <Mascot mood="thinking" size="medium" />
        <span className="eyebrow">{t('hub.notAvailableEyebrow')}</span>
        <h2>{t('hub.notAvailableNone')}</h2>
        <p>{t('hub.notAvailableNoneCopy', { languageName: languageName(language) })}</p>
        <button className="button button-sun" onClick={() => setLanguage('en')}>{t('hub.notAvailableSwitch')} <span>→</span></button>
      </div>
    </div>
  );
  if (error && state === 'ERROR') return <div className="game-error"><h1>{t('game.error.title')}</h1><p>{error}</p><button className="button" onClick={() => window.location.reload()}>{t('game.error.retry')}</button></div>;
  if (state === 'LOADING') return <div className="game-loading"><span className="loading-path">✦ · ✦ · ✦</span><p>{t('game.loading.speech')}</p></div>;
  if (!engineRef.current) return null;
  if (state === 'INTRO') return (
    <div className="game-overlay-page">
      <GameIntro title={definition.name} instructions={definition.instructions} onStart={startGame} />
      <SpeechConsentGate
        capabilities={probeSpeechCapabilities()}
        consented={consented}
        phase={consented ? 'READY' : 'REQUESTED'}
        message={t('speech.micNeverSaved')}
        onEnable={() => void enableMic()}
        onDisable={disableMic}
      />
    </div>
  );
  if (state === 'GAME_COMPLETE') return <div className="game-overlay-page"><GameComplete title={definition.name} completed={engineRef.current.trials.length} total={definition.totalTrials} onContinue={continueAfterGame} /></div>;
  if (!trial) return null;
  const view = definition.id === 'sound-quest-adventure' ? <SoundQuestAdventure key={trial.trialId} trial={trial as SpeechTrial} onResponse={submit} /> : definition.id === 'letter-bubble-pop' ? <LetterBubblePop key={trial.trialId} trial={trial as SpeechTrial} onResponse={submit} /> : <MazeRunnerRush key={trial.trialId} trial={trial as SpeechTrial} onResponse={submit} />;
  return (
    <div className="game-runner-wrap">
      <GameShell title={definition.name} mission={engineRef.current.trials.length - 1} totalMissions={definition.totalTrials} state={state} instructions={definition.instructions} onPause={() => undefined} onHelp={() => window.alert(definition.instructions.join(' '))} feedback={feedback}>{view}</GameShell>
      <button className="speech-exit" onClick={abandonAndLeave} aria-label={t('speech.exitAria')}>✕</button>
      {!capable && <div className="speech-unavailable" role="status">{t('speech.browserUnsupported')}</div>}
    </div>
  );
}