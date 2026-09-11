import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { assessmentPlan } from './definitions';
import { GameEngine, type GameState, type Trial, type AssessmentSession } from './engine';
import { GameComplete, GameIntro, GameShell } from './components/GameShell';
import { LetterDetectiveView, MirrorMatchView, SequenceQuestView, WordFlashView, WordMazeView } from './components/GameViews';
import type { LetterTrial } from './definitions/letterDetective';
import type { MirrorTrial } from './definitions/mirrorMatch';
import type { SequenceTrial } from './definitions/sequenceQuest';
import type { WordFlashTrial } from './definitions/wordFlash';
import type { MazeTrial } from './definitions/wordMaze';
import { ensureAssessmentSession, persistEvent, persistSummary, persistTrial } from './persistence';

export function GameRunner() {
  const navigate = useNavigate();
  const [gameIndex, setGameIndex] = useState(0);
  const [state, setState] = useState<GameState>('LOADING');
  const [trial, setTrial] = useState<Trial>();
  const [feedback, setFeedback] = useState<string>();
  const [presentation, setPresentation] = useState(true);
  const [error, setError] = useState<string>();
  const engineRef = useRef<GameEngine | null>(null);
  const presentationTimer = useRef<number | undefined>(undefined);
  const advanceTimer = useRef<number | undefined>(undefined);
  const sessionRef = useRef<AssessmentSession | null>(null);
  const persistedEventSequence = useRef(0);
  const definition = assessmentPlan[gameIndex];

  useEffect(() => { let active = true; const sessionPromise = sessionRef.current ? Promise.resolve(sessionRef.current) : ensureAssessmentSession(); sessionPromise.then(session => { if (!active) return; sessionRef.current = session; engineRef.current = new GameEngine(definition, session); setState('INTRO'); }).catch(() => { if (active) { const localSession = sessionRef.current ?? undefined; engineRef.current = new GameEngine(definition, localSession); sessionRef.current = engineRef.current.session; setError('We could not connect, so this adventure will keep your progress nearby.'); setState('INTRO'); } }); return () => { active = false; window.clearTimeout(presentationTimer.current); window.clearTimeout(advanceTimer.current); }; }, [gameIndex, definition]);

  const persistNewEvents = () => { const engine = engineRef.current; if (!engine) return; engine.events.filter(event => event.sequenceNumber > persistedEventSequence.current && event.trialId).forEach(event => { void persistEvent(event.trialId ?? '', event); }); persistedEventSequence.current = engine.session.eventSequence ?? persistedEventSequence.current; };
  const startTrial = () => { const engine = engineRef.current; if (!engine) return; const next = engine.beginTrial(engine.trials.length); persistNewEvents(); setTrial(next); setFeedback(undefined); setState('PLAYING'); const duration = (next.stimulus as { presentationMs?: number; displayMs?: number })?.presentationMs ?? (next.stimulus as { displayMs?: number })?.displayMs; if (definition.id === 'word-flash' || definition.id === 'sequence-quest') { setPresentation(true); presentationTimer.current = window.setTimeout(() => setPresentation(false), duration ?? 1800); } else setPresentation(false); };
  const emit = (eventType: Parameters<GameEngine['emit']>[0], payload: Record<string, unknown> = {}) => { const engine = engineRef.current; if (!engine) return; engine.emit(eventType, payload, trial?.trialId); };
  const submit = (response: unknown) => { const engine = engineRef.current; if (!engine || !trial || state !== 'PLAYING' || presentation) return; const updated = engine.recordResponse(trial, response); engine.completeTrial(updated); persistNewEvents(); void persistTrial(engine.session.assessmentId ?? engine.session.sessionId, definition.id, updated); const result = updated.correct ? 'Great job!' : 'Almost! Let’s keep exploring.'; setFeedback(result); setState('FEEDBACK'); advanceTimer.current = window.setTimeout(() => { if (engine.trials.length >= definition.totalTrials) { engine.completeGame(); persistNewEvents(); setState('GAME_COMPLETE'); } else startTrial(); }, 900); };
  const pause = () => { const engine = engineRef.current; if (!engine) return; if (state === 'PAUSED') { engine.resume(); setState('PLAYING'); } else if (state === 'PLAYING' || state === 'FEEDBACK') { engine.pause(); window.clearTimeout(presentationTimer.current); window.clearTimeout(advanceTimer.current); setState('PAUSED'); emit('SESSION_PAUSED'); } };
  const help = () => { emit('HINT_SHOWN', { source: 'instructions' }); window.alert(definition.instructions.join(' ')); };
  const continueAfterGame = () => { const engine = engineRef.current; if (!engine) return; if (gameIndex >= assessmentPlan.length - 1) { engine.completeSession(); void persistSummary(engine.session.assessmentId ?? engine.session.sessionId, { games: engine.session.games, totalTrials: engine.session.totalTrials }); navigate('/parent/dashboard'); return; } setGameIndex(index => index + 1); };

  if (error && state === 'ERROR') return <div className="game-error"><h1>Oops! Something went wrong.</h1><p>{error}</p><button className="button" onClick={() => window.location.reload()}>Try again</button></div>;
  if (state === 'LOADING') return <div className="game-loading"><span className="loading-path">✦ · ✦ · ✦</span><p>Getting the next adventure ready...</p></div>;
  if (!engineRef.current) return null;
  if (state === 'INTRO') return <div className="game-overlay-page"><GameIntro title={definition.name} instructions={definition.instructions} onStart={() => { engineRef.current?.start(); persistNewEvents(); startTrial(); }} /></div>;
  if (state === 'GAME_COMPLETE') return <div className="game-overlay-page"><GameComplete title={definition.name} completed={engineRef.current.trials.length} total={definition.totalTrials} onContinue={continueAfterGame} /></div>;
  if (!trial) return null;
  const view = definition.id === 'letter-detective' ? <LetterDetectiveView trial={trial as LetterTrial} onResponse={submit} emit={emit} /> : definition.id === 'mirror-match' ? <MirrorMatchView trial={trial as MirrorTrial} onResponse={submit} emit={emit} /> : definition.id === 'word-flash' ? <WordFlashView trial={trial as WordFlashTrial} onResponse={submit} emit={emit} showing={presentation} /> : definition.id === 'sequence-quest' ? <SequenceQuestView trial={trial as SequenceTrial} onResponse={submit} emit={emit} showing={presentation} /> : <WordMazeView trial={trial as MazeTrial} onResponse={submit} emit={emit} />;
  return <GameShell title={definition.name} mission={engineRef.current.trials.length - 1} totalMissions={definition.totalTrials} state={state} instructions={definition.instructions} onPause={pause} onHelp={help} feedback={feedback}>{view}</GameShell>;
}
