import { useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mascot, MascotBubble } from '../../components/ui';
import { GameEngine, type GameState, type Trial } from '../engine';
import { LetterDetectiveView, SequenceQuestView, WordFlashView, WordMazeView } from '../components/GameViews';
import type { LetterTrial } from '../definitions/letterDetective';
import type { SequenceTrial } from '../definitions/sequenceQuest';
import type { WordFlashTrial } from '../definitions/wordFlash';
import type { MazeTrial } from '../definitions/wordMaze';
import { api, type NextPracticeActivity, type PracticeSessionStatus } from '../../services/apiClient';
import { MIRRORED_PRACTICE_EVENTS, practiceGameFor, seedForSessionId, toPracticeEvent } from './practice';
import { PRACTICE_COPY } from './practiceCopy';

type Stage = 'loading' | 'intro' | 'playing' | 'done' | 'error';

export function PracticeRunner() {
  const navigate = useNavigate();
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

  useEffect(() => {
    const childId = window.localStorage.getItem('dyscover-stage2-child-id');
    if (!childId) {
      setStage('error');
      setError('Let’s set up an explorer first.');
      return;
    }
    let active = true;
    api
      .getNextPracticeActivity(childId)
      .then(value => { if (!active) return; setRecommendation(value); setStage(value.activity ? 'intro' : 'error'); if (!value.activity) setError('There are no practice activities available just yet.'); })
      .catch(() => { if (!active) return; setStage('error'); setError('We could not reach the practice area. Please try again in a moment.'); });
    return () => { active = false; window.clearTimeout(presentationTimer.current); window.clearTimeout(advanceTimer.current); };
  }, []);

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
    setFeedback(updated.correct ? PRACTICE_COPY.goodFeedback : PRACTICE_COPY.nextFeedback);
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
    });
    const started = await api.startPracticeSession(created.id);
    setPracticeSession(started);
    const definition = practiceGameFor(recommendation.activity.activity_id);
    if (!definition) { setStage('error'); setError('That activity is not available just yet.'); return; }
    const engine = new GameEngine(definition, undefined, seedForSessionId(started.id), started.difficulty);
    engineRef.current = engine;
    engine.start();
    knownEvents.current = 0;
    setStage('playing');
    startTrial();
  };

  const pause = () => {
    const engine = engineRef.current;
    if (!engine) return;
    if (state === 'PAUSED') { engine.resume(); setState('PLAYING'); }
    else if (state === 'PLAYING' || state === 'FEEDBACK') { engine.pause(); window.clearTimeout(presentationTimer.current); window.clearTimeout(advanceTimer.current); setState('PAUSED'); }
  };

  const abandonAndLeave = () => {
    const session = practiceSession;
    if (session) void api.abandonPracticeSession(session.id).catch(() => undefined);
    navigate('/child/home');
  };

  const activity = recommendation?.activity;

  if (stage === 'loading') return <div className="game-loading"><span className="loading-path">✦ · ✦ · ✦</span><p>Getting your practice ready...</p></div>;
  if (stage === 'error') return <div className="game-error"><h1>We could not start practice.</h1><p>{error}</p><button className="button" onClick={() => navigate('/child/home')}>Back to the explorer space</button></div>;
  if (!activity) return null;

  if (stage === 'intro') return (
    <div className="child-space"><section className="child-welcome"><div className="child-copy"><span className="child-kicker">✦ practice zone ✦</span><h1>{PRACTICE_COPY.introTitle}</h1><p>{PRACTICE_COPY.introBody}</p><MascotBubble mood="happy">{activity.display_name}: {activity.description}</MascotBubble><button className="child-start" onClick={() => void begin()}>Start practice <span>→</span></button><Link className="child-exit" to="/child/home">Not now</Link></div><div className="child-scene"><div className="child-cloud cloud-one" /><div className="child-ground" /><Mascot mood="excited" size="large" /></div></section></div>
  );

  if (stage === 'done') return (
    <div className="game-overlay-page"><div className="game-complete"><Mascot mood="excited" size="large" /><span className="child-kicker">practice complete</span><h1>{PRACTICE_COPY.doneTitle}</h1><p>{PRACTICE_COPY.doneBody}</p><button className="button" onClick={() => navigate('/child/home')}>Back to the explorer space <span>→</span></button></div></div>
  );

  const engine = engineRef.current;
  if (!engine || !trial) return null;
  const definition = engine.definition;
  const view = definition.id === 'letter-detective' ? <LetterDetectiveView key={trial.trialId} trial={trial as LetterTrial} onResponse={response => void submit(response)} emit={emit} /> : definition.id === 'word-flash' ? <WordFlashView key={trial.trialId} trial={trial as WordFlashTrial} onResponse={response => void submit(response)} emit={emit} showing={presentation} /> : definition.id === 'sequence-quest' ? <SequenceQuestView key={trial.trialId} trial={trial as SequenceTrial} onResponse={response => void submit(response)} emit={emit} showing={presentation} /> : <WordMazeView key={trial.trialId} trial={trial as MazeTrial} onResponse={response => void submit(response)} emit={emit} />;
  return (
    <div className="game-shell">
      <div className="game-topbar">
        <button className="game-back" onClick={abandonAndLeave} aria-label="Leave practice">←</button>
        <div className="game-title"><span className="game-mascot-dot">✦</span><strong>{activity.display_name}</strong></div>
        <div className="game-actions">
          <button className="game-icon-button" onClick={() => window.alert(`${PRACTICE_COPY.introTitle} ${activity.description}`)} aria-label="Show instructions">?</button>
          <button className="game-icon-button" onClick={pause} aria-label={state === 'PAUSED' ? 'Resume practice' : 'Pause practice'}>{state === 'PAUSED' ? '▶' : 'Ⅱ'}</button>
        </div>
      </div>
      <div className="game-progress-row"><span>Practice {engine.trials.length} of {definition.totalTrials}</span><div className="game-progress"><span style={{ width: `${Math.round((engine.trials.length / definition.totalTrials) * 100)}%` }} /></div><span>{Math.round((engine.trials.length / definition.totalTrials) * 100)}%</span></div>
      <main className="game-stage"><div className="game-intro"><span className="child-kicker">{state === 'PAUSED' ? 'paused for a moment' : 'take your time'}</span><h1>{activity.display_name}</h1><p>{activity.description}</p></div>{view}{feedback && <div className="game-feedback" role="status"><Mascot mood={feedback === PRACTICE_COPY.goodFeedback ? 'happy' : 'thinking'} size="small" /><strong>{feedback}</strong></div>}</main>
      {state === 'PAUSED' && <div className="game-pause-overlay" role="dialog" aria-modal="true" aria-label="Practice paused"><Mascot mood="thinking" size="medium" /><span className="child-kicker">a small pause</span><h2>{PRACTICE_COPY.pausedHeading}</h2><p>{PRACTICE_COPY.pausedBody}</p><button className="child-start" onClick={pause}>{PRACTICE_COPY.continue} <span>→</span></button></div>}
    </div>
  );
}