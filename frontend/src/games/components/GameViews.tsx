import { useState } from 'react';
import type { LetterTrial } from '../definitions/letterDetective';
import type { MirrorTrial } from '../definitions/mirrorMatch';
import type { WordFlashTrial } from '../definitions/wordFlash';
import type { SequenceTrial } from '../definitions/sequenceQuest';
import type { MazeTrial } from '../definitions/wordMaze';
import { Button } from '../../components/ui';

type EventFn = (type: 'OPTION_SELECTED' | 'OPTION_DESELECTED' | 'BUTTON_CLICKED' | 'DRAG_STARTED' | 'DRAG_DROPPED' | 'HINT_SHOWN', payload: Record<string, unknown>) => void;

export function LetterDetectiveView({ trial, onResponse, emit }: { trial: LetterTrial; onResponse: (response: string) => void; emit: EventFn }) { const [selected, setSelected] = useState<string>(); return <div className="game-card-board detective-board"><div className="clue-label">Find the letter that matches</div><div className="detective-clue">{trial.stimulus.target}</div><div className="option-grid">{trial.stimulus.options.map(option => <button className={`game-option letter-option ${selected === option ? 'selected' : ''}`} key={option} onClick={() => { setSelected(option); emit('OPTION_SELECTED', { optionId: option }); onResponse(option); }} aria-label={`Letter ${option}`}>{option}</button>)}</div></div>; }

export function MirrorMatchView({ trial, onResponse, emit }: { trial: MirrorTrial; onResponse: (response: string) => void; emit: EventFn }) { return <div className="game-card-board mirror-board"><div className="mirror-example"><span className="clue-label">Look at this symbol</span><strong>{trial.stimulus.symbol}</strong><small>{trial.stimulus.targetOrientation === 'normal' ? 'Which one looks the same?' : 'Find its matching reflection.'}</small></div><div className="mirror-options">{trial.stimulus.options.map(option => <button className="game-option mirror-option" key={option.id} onClick={() => { emit('OPTION_SELECTED', { optionId: option.id, orientation: option.orientation }); onResponse(option.id); }} aria-label={`Choose ${option.id}`}><span style={{ transform: option.orientation === 'mirror' ? 'scaleX(-1)' : option.orientation === 'rotated' ? 'rotate(180deg)' : undefined }}>{option.label}</span></button>)}</div></div>; }

export function WordFlashView({ trial, onResponse, emit, showing }: { trial: WordFlashTrial; onResponse: (response: string) => void; emit: EventFn; showing: boolean }) { return <div className="game-card-board flash-board"><div className={`flash-stimulus ${showing ? 'flash-showing' : 'flash-hidden'}`} aria-live="polite">{showing ? trial.stimulus.word : 'Which word did you see?'}</div>{!showing && <div className="option-grid word-options">{trial.stimulus.options.map(option => <button className="game-option word-option" key={option} onClick={() => { emit('OPTION_SELECTED', { optionId: option }); onResponse(option); }}>{option}</button>)}</div>}</div>; }

export function SequenceQuestView({ trial, onResponse, emit, showing }: { trial: SequenceTrial; onResponse: (response: string[]) => void; emit: EventFn; showing: boolean }) { const [chosen, setChosen] = useState<string[]>([]); const available = trial.stimulus.sequence; return <div className="game-card-board sequence-board">{showing ? <div className="sequence-display">{available.map(item => <span key={item} className="sequence-token">{item === 'star' ? '✦' : item === 'moon' ? '☾' : item === 'sun' ? '☼' : item === 'leaf' ? '⌁' : item === 'cloud' ? '☁' : '≈'}</span>)}</div> : <><div className="sequence-answer" aria-live="polite">{chosen.length ? chosen.map((item, index) => <span key={`${item}-${index}`}>{item}</span>) : <small>Tap the pieces in order</small>}</div><div className="sequence-choices">{available.map(item => <button className="game-option sequence-option" disabled={chosen.includes(item)} key={item} onClick={() => { const next = [...chosen, item]; setChosen(next); emit('OPTION_SELECTED', { item, position: next.length }); if (next.length === available.length) onResponse(next); }}>{item}</button>)}</div><Button secondary onClick={() => { setChosen([]); emit('OPTION_DESELECTED', { reset: true }); }}>Start again</Button></>}</div>; }

export function WordMazeView({ trial, onResponse, emit }: { trial: MazeTrial; onResponse: (response: string[]) => void; emit: EventFn }) {
	const [found, setFound] = useState<string[]>([]);
	const [path, setPath] = useState<string[]>([]);
	const [message, setMessage] = useState('Choose a word, then trace its letters.');
	const cells = trial.stimulus.grid.flatMap((row, rowIndex) => row.map((letter, columnIndex) => ({ letter, id: `${rowIndex},${columnIndex}` })));
	const normalizedPaths = Object.entries(trial.stimulus.paths).map(([word, targetPath]) => [word.toUpperCase(), targetPath] as const);
	const selectedTarget = trial.stimulus.targets.find(target => !found.includes(target)) ?? trial.stimulus.targets[0];
	const isAdjacent = (first: string, second: string) => {
		const [firstRow, firstColumn] = first.split(',').map(Number);
		const [secondRow, secondColumn] = second.split(',').map(Number);
		return Math.abs(firstRow - secondRow) <= 1 && Math.abs(firstColumn - secondColumn) <= 1 && (firstRow !== secondRow || firstColumn !== secondColumn);
	};
	const selectCell = (id: string) => {
		if (found.includes(selectedTarget)) return;
		if (path.includes(id)) return;
		if (path.length > 0 && !isAdjacent(path[path.length - 1], id)) {
			setMessage('Those letters are not next to each other. Try a nearby letter.');
			setPath([]);
			emit('OPTION_DESELECTED', { reason: 'non_adjacent', cellId: id });
			return;
		}
		const nextPath = [...path, id];
		setPath(nextPath);
		emit('OPTION_SELECTED', { cellId: id, path: nextPath, target: selectedTarget });
		const match = normalizedPaths.find(([word, targetPath]) => word === selectedTarget && targetPath.length === nextPath.length && (targetPath.every((cell, index) => cell === nextPath[index]) || targetPath.every((cell, index) => cell === nextPath[nextPath.length - index - 1])));
		if (match) {
			const nextFound = [...found, match[0]];
			setFound(nextFound);
			setPath([]);
			setMessage(nextFound.length === trial.stimulus.targets.length ? 'You found every word!' : 'Nice finding! Choose the next word.');
			if (nextFound.length === trial.stimulus.targets.length) onResponse(nextFound);
		} else if (nextPath.length >= selectedTarget.length) {
			setMessage('Almost! Clear the path and try that word again.');
			setPath([]);
			emit('OPTION_DESELECTED', { reason: 'path_mismatch', target: selectedTarget });
		}
	};
	const nextWord = () => { setPath([]); setMessage('Trace the next word.'); emit('BUTTON_CLICKED', { action: 'next_word', target: selectedTarget }); };
	return <div className="game-card-board maze-board"><div className="maze-targets"><span className="maze-target-label">Find:</span>{trial.stimulus.targets.map(target => <button className={`maze-target ${found.includes(target) ? 'found' : target === selectedTarget ? 'current' : ''}`} key={target} onClick={() => { setPath([]); setMessage(`Find ${target}.`); }} aria-label={`Find ${target}`}>{target}</button>)}</div><div className="maze-grid" style={{ gridTemplateColumns: `repeat(${trial.stimulus.size}, 1fr)` }}>{cells.map(cell => <button className={`maze-cell ${path.includes(cell.id) ? 'path' : ''}`} key={cell.id} onClick={() => selectCell(cell.id)} aria-label={`Letter ${cell.letter}`}>{cell.letter}</button>)}</div><p className="maze-help" role="status">{message}</p>{found.length > 0 && found.length < trial.stimulus.targets.length && <Button secondary onClick={nextWord}>Next word <span>→</span></Button>}</div>;
}
