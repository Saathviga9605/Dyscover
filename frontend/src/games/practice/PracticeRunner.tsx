import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mascot, MascotBubble } from '../../components/ui';
import { GameEngine, type GameState, type Trial } from '../engine';
import { LetterDetectiveView, SequenceQuestView, WordFlashView, WordMazeView } from '../components/GameViews';
import type { LetterTrial } from '../definitions/letterDetective';
import type { SequenceTrial } from '../definitions/sequenceQuest';
import type { WordFlashTrial } from '../definitions/wordFlash';
import type { MazeTrial } from '../definitions/wordMaze';
import { api, type NextPracticeActivity, type PracticeSessionStatus, type SpeechTasksResponse } from '../../services/apiClient';
import { MIRRORED_PRACTICE_EVENTS, practiceGameFor, seedForSessionId, toPracticeEvent } from './practice';
import { probeSpeechCapabilities, SpeechConsentCard, SpeechPracticeView, SPEECH_CONSENT_KEY } from '../../speech';
import { useLanguage } from '../../l10n';
import { isActivityAvailable } from '../../l10n/languages';

type Stage = 'loading' | 'intro' | 'playing' | 'speech-intro' | 'speech-playing' | 'done' | 'error';

const SPEECH_PRACTICE_IDS = ['sound-quest-adventure', 'letter-bubble-pop', 'maze-runner-rush'] as const;

export function PracticeRunner() {
  const navigate = useNavigate();
  const { t, language } = useLanguage();
  const hasSpeechAvailable = SPEECH_PRACTICE_IDS.some(id => isActivityAvailable(id, language));
  const [stage, setStage] = useState<Stage>('loading');
  const [recommendation, setRecommendation] = useState<NextPracticeActivity | null>(null);
  const [practiceSession, setPracticeSession] = useState<PracticeSessionStatus | null>(null);
  const [state, setState] = useState<GameState>('READY');
  const [trial, setTrial] = useState<Trial>();
  const [feedback, setFeedback] = useState<string>();
  const [presentation, setPresentation] = useState(true);
  const [error, setError] = useState<string>();
  const engineRef = useRef<GameEngine | null>(null);
  const presentationTimer = useRef<number | undefined>(undefined);
  const advanceTimer = useRef<number | undefined>(undefined);
  const knownEvents = useRef(0);
  const speechSession = useRef<PracticeSessionStatus | null>(null);
  const speechTasks = useRef<SpeechTasksResponse | null>(null);
  const speechFeatures = useRef<Record<string, number>>({});
  const speechCapabilities = useRef(probeSpeechCapabilities());
  const hasSpeechMic = speechCapabilities.current.recognition || speechCapabilities.current.audio;
  const [speechConsented, setSpeechConsented] = useState(() => (typeof window !== 'undefined' ? window.localStorage.getItem(SPEECH_CONSENT_KEY) === 'true' : false));
  const [speechPhase, setSpeechPhase] = useState<string>('NOT_CONFIGURED');
  const [speechMessage, setSpeechMessage] = useState<string>();

  useEffect(() => {
    const childId = window.localStorage.getItem('dyscover-stage2-child-id');
    if (!childId) {
      setStage('error');
      setError(t('practice.setupFirst'));
      return;
    }
    let active = true;
    api
      .getNextPracticeActivity(childId, language)
      .then(value => { if (!active) return; setRecommendation(value); setStage(value.activity ? 'intro' : 'error'); if (!value.activity) setError(t('practice.noneYet')); })
      .catch(() => { if (!active) return; setStage('error'); setError(t('practice.unreachable')); });
    return () => { active = false; window.clearTimeout(presentationTimer.current); window.clearTimeout(advanceTimer.current); };
  }, [t, language]);

  const flushPracticeEvents = async () => {
    const engine = engineRef.current;
    const session = practiceSession;
    if (!engine || !session) return Promise.resolve();
    const pending = engine.events
      .slice(knownEvents.current)
      .filter(event => MIRRORED_PRACTICE_EVENTS.has(event.eventType));
    knownEvents.current = engine.events.length;
    for (const event of pending) {
      await api.recordPracticeEvent(session.id, toPracticeEvent(event)).catch(() => undefined);
    }
  };

  const startTrial = () => {
    const engine = engineRef.current;
    if (!engine) return;
    const next = engine.beginTrial(engine.trials.length);
    setTrial(next);
    setFeedback(undefined);
    setState('PLAYING');
    const definition = engine.definition;
    const duration = (next.stimulus as { presentationMs?: number; displayMs?: number })?.presentationMs ?? (next.stimulus as { displayMs?: number })?.displayMs;
    if (definition.id === 'word-flash' || definition.id === 'sequence-quest') {
      setPresentation(true);
      presentationTimer.current = window.setTimeout(() => setPresentation(false), duration ?? 1800);
    } else setPresentation(false);
  };

  const emit = (eventType: 'OPTION_SELECTED' | 'OPTION_DESELECTED' | 'BUTTON_CLICKED' | 'DRAG_STARTED' | 'DRAG_DROPPED' | 'HINT_SHOWN', payload: Record<string, unknown>) => {
    const engine = engineRef.current;
    if (!engine) return;
    engine.emit(eventType, payload, trial?.trialId);
  };

  const submit = async (response: unknown) => {
    const engine = engineRef.current;
    if (!engine || !trial || state !== 'PLAYING' || presentation) return;
    const updated = engine.recordResponse(trial, response);
    engine.completeTrial(updated);
    setFeedback(updated.correct ? t('game.shell.feedbackGreat') : t('practice.nextFeedback'));
    setState('FEEDBACK');
    void flushPracticeEvents();
    advanceTimer.current = window.setTimeout(() => {
      if (engine.trials.length >= engine.definition.totalTrials) {
        engine.completeGame();
        void flushPracticeEvents().finally(async () => {
          if (practiceSession) await api.completePracticeSession(practiceSession.id).catch(() => undefined);
        });
        setState('GAME_COMPLETE');
        setStage('done');
      } else startTrial();
    }, 900);
  };

  const begin = async () => {
    const childId = window.localStorage.getItem('dyscover-stage2-child-id');
    if (!recommendation?.activity || !childId) return;
    const created = await api.createPracticeSession({
      child_id: childId,
      activity_id: recommendation.activity.activity_id,
      difficulty: recommendation.difficulty_level ?? undefined,
      language,
    });
    const started = await api.startPracticeSession(created.id);
    setPracticeSession(started);
    const definition = practiceGameFor(recommendation.activity.activity_id);
    if (!definition) { setStage('error'); setError(t('practice.notAvailableYet')); return; }
    const engine = new GameEngine(definition, undefined, seedForSessionId(started.id), started.difficulty);
    engineRef.current = engine;
    engine.start();
    knownEvents.current = 0;
    setStage('playing');
    startTrial();
  };

  const beginSpeech = async () => {
    const childId = window.localStorage.getItem('dyscover-stage2-child-id');
    if (!childId) return;
    const next = await api.getNextPracticeActivity(childId, language, 'microphone');
    if (!next.activity) { setStage('error'); setError(t('practice.noSpeechNow')); return; }
    const created = await api.createPracticeSession({ child_id: childId, activity_id: next.activity.activity_id, difficulty: next.difficulty_level ?? undefined, language });
    const started = await api.startPracticeSession(created.id);
    speechSession.current = started;
    const tasks = await api.getSpeechTasks(next.activity.activity_id, 5, seedForSessionId(started.id), language).catch(() => null);
    if (!tasks?.tasks?.length) { setStage('error'); setError(t('practice.speechNotReady')); return; }
    speechTasks.current = tasks;
    speechFeatures.current = {};
    setStage('speech-playing');
    setPracticeSession(started);
  };

  const handleSpeechResult = async (_task: import('../../speech').ReadingTask, result: import('../../speech').SpeechAnalysisResult, _index: number) => {
    if (!speechSession.current) return;
    await api.recordPracticeEvent(speechSession.current.id, { event_type: 'RESPONSE_SUBMITTED', payload: { correct: result.correct, difficulty: result.expected_text.length } }).catch(() => undefined);
    for (const [k, v] of Object.entries(result.features)) {
      if (typeof v === 'number') speechFeatures.current[k] = Math.max(speechFeatures.current[k] ?? 0, v);
    }
  };

  const finishSpeech = async (abandoned = false) => {
    const session = speechSession.current;
    speechSession.current = null;
    if (session && !abandoned) await api.completePracticeSession(session.id).catch(() => undefined);
    if (session) {
      await api.recordPracticeEvent(session.id, { event_type: 'SPEECH_FEATURES', payload: { features: speechFeatures.current } }).catch(() => undefined);
    }
    speechFeatures.current = {};
    setStage('done');
  };

  const pause = () => {
    const engine = engineRef.current;
    if (!engine) return;
    if (state === 'PAUSED') { engine.resume(); setState('PLAYING'); }
    else if (state === 'PLAYING' || state === 'FEEDBACK') { engine.pause(); window.clearTimeout(presentationTimer.current); window.clearTimeout(advanceTimer.current); setState('PAUSED'); }
  };

  const abandonAndLeave = () => {
    const session = practiceSession;
    if (speechSession.current) void finishSpeech(true);
    if (session) void api.abandonPracticeSession(session.id).catch(() => undefined);
    navigate('/child/home');
  };

  const activity = recommendation?.activity;

  if (stage === 'loading') return <div className="game-loading"><span className="loading-path">âœ¦ Â· âœ¦ Â· âœ¦</span><p>{t('practice.loading')}</p></div>;
  if (stage === 'error') return <div className="game-error"><h1>{t('practice.errorTitle')}</h1><p>{error}</p><button className="button" onClick={() => navigate('/child/home')}>{t('practice.backToChild')}</button></div>;
  if (!activity) return null;

  if (stage === 'intro') return (
    <div className="child-space">
      <section className="child-welcome">
        <div className="child-copy">
          <span className="child-kicker">{t('practice.introKicker')}</span>
          <h1>{t('practice.introTitle')}</h1>
          <p>{t('practice.introBody')}</p>
          <MascotBubble mood="happy">{activity.display_name}: {activity.description}</MascotBubble>
          <button className="child-start" onClick={() => void begin()}>{t('practice.start')} <span>â†’</span></button>
          <Link className="child-exit" to="/child/home">{t('practice.notNow')}</Link>
        </div>
        <div className="child-scene"><div className="child-cloud cloud-one" /><div className="child-ground" /><Mascot mood="excited" size="large" /></div>
      </section>
      {hasSpeechMic && hasSpeechAvailable && (
        <section className="child-welcome speech-intro-card">
          <div className="child-copy">
            <span className="child-kicker">{t('practice.speechKicker')}</span>
            <h2>{t('practice.speechTitle')}</h2>
            <p>{t('practice.speechIntroCopy')}</p>
            {!speechConsented ? (
              <SpeechConsentCard
                capabilities={speechCapabilities.current}
                consented={false}
                phase={speechPhase}
                message={speechMessage}
                onEnable={() => {
                  window.localStorage.setItem(SPEECH_CONSENT_KEY, 'true');
                  setSpeechConsented(true);
                  document.dispatchEvent(new Event('dyscover:speech-consent'));
                }}
                onDisable={() => undefined}
              />
            ) : (
              <div>
                <p>{t('practice.speechConsentedCopy')}</p>
                <button className="child-start" onClick={() => void beginSpeech()}>{t('practice.speechStart')} <span>â†’</span></button>
              </div>
            )}
          </div>
          <div className="child-scene"><div className="child-cloud cloud-two" /><div className="child-ground" /><Mascot mood="thinking" size="large" /></div>
        </section>
      )}
    </div>
  );

  if (stage === 'done') return (
    <div className="game-overlay-page"><div className="game-complete"><Mascot mood="excited" size="large" /><span className="child-kicker">{t('practice.doneKicker')}</span><h1>{t('practice.doneTitle')}</h1><p>{t('practice.doneBody')}</p><button className="button" onClick={() => navigate('/child/home')}>{t('practice.backToChild')} <span>â†’</span></button></div></div>
  );

  if (stage === 'speech-playing') {
    const speech = speechTasks.current;
    if (!speech?.tasks?.length || !practiceSession) return null;
    return (
      <SpeechPracticeView
        activityName={activity.display_name}
        activityDescription={activity.description}
        tasks={speech.tasks}
        capabilities={speechCapabilities.current}
        difficulty={practiceSession.difficulty}
        onResult={(task, result, index) => void handleSpeechResult(task, result, index)}
        onComplete={() => void finishSpeech(false)}
        onAbandon={abandonAndLeave}
        onPhaseChange={(phase, text) => { setSpeechPhase(phase); setSpeechMessage(text); }}
      />
    );
  }

  const engine = engineRef.current;
  if (!engine || !trial) return null;
  const definition = engine.definition;
  const view = definition.id === 'letter-detective' ? <LetterDetectiveView key={trial.trialId} trial={trial as LetterTrial} onResponse={response => void submit(response)} emit={emit} /> : definition.id === 'word-flash' ? <WordFlashView key={trial.trialId} trial={trial as WordFlashTrial} onResponse={response => void submit(response)} emit={emit} showing={presentation} /> : definition.id === 'sequence-quest' ? <SequenceQuestView key={trial.trialId} trial={trial as SequenceTrial} onResponse={response => void submit(response)} emit={emit} showing={presentation} /> : <WordMazeView key={trial.trialId} trial={trial as MazeTrial} onResponse={response => void submit(response)} emit={emit} />;
  return (
    <div className="game-shell">
      <div className="game-topbar">
        <button className="game-back" onClick={abandonAndLeave} aria-label={t('practice.abandon')}>â†</button>
        <div className="game-title"><span className="game-mascot-dot">âœ¦</span><strong>{activity.display_name}</strong></div>
        <div className="game-actions">
          <button className="game-icon-button" onClick={() => window.alert(`${activity.display_name}: ${activity.description}`)} aria-label={t('practice.instructionsAria')}>?</button>
          <button className="game-icon-button" onClick={pause} aria-label={state === 'PAUSED' ? t('practice.resumeAria') : t('practice.pauseAria')}>{state === 'PAUSED' ? 'â–¶' : 'â…¡'}</button>
        </div>
      </div>
      <div className="game-progress-row"><span>{t('practice.progress', { current: engine.trials.length, total: definition.totalTrials })}</span><div className="game-progress"><span style={{ width: `${Math.round((engine.trials.length / definition.totalTrials) * 100)}%` }} /></div><span>{Math.round((engine.trials.length / definition.totalTrials) * 100)}%</span></div>
      <main className="game-stage"><div className="game-intro"><span className="child-kicker">{state === 'PAUSED' ? t('game.shell.kickerPaused') : t('game.shell.kickerPlaying')}</span><h1>{activity.display_name}</h1><p>{activity.description}</p></div>{view}{feedback && <div className="game-feedback" role="status"><Mascot mood={feedback === t('game.shell.feedbackGreat') ? 'happy' : 'thinking'} size="small" /><strong>{feedback}</strong></div>}</main>
      {state === 'PAUSED' && <div className="game-pause-overlay" role="dialog" aria-modal="true" aria-label={t('practice.pausedAria')}><Mascot mood="thinking" size="medium" /><span className="child-kicker">{t('game.shell.pauseKicker')}</span><h2>{t('game.shell.pauseTitle')}</h2><p>{t('game.shell.pauseCopy')}</p><button className="child-start" onClick={pause}>{t('practice.continue')} <span>â†’</span></button></div>}
    </div>
  );
}
