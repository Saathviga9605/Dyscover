import { useEffect, useState, type ReactNode } from 'react';

export function Button({ children, secondary = false, ...props }: { children: ReactNode; secondary?: boolean } & React.ButtonHTMLAttributes<HTMLButtonElement>) { return <button className={`button ${secondary ? 'button-secondary' : ''}`} {...props}>{children}</button>; }
export function Card({ children, className = '' }: { children: ReactNode; className?: string }) { return <div className={`card ${className}`}>{children}</div>; }
export function Badge({ children }: { children: ReactNode }) { return <span className="badge">{children}</span>; }
export function ProgressBar({ value }: { value: number }) { return <div className="progress-track" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><span style={{ width: `${value}%` }} /></div>; }
export function PageHeader({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) { return <header className="page-header"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1>{children}</header>; }
export function EmptyState({ children }: { children: ReactNode }) { return <div className="empty-state">{children}</div>; }
export function LoadingState() { return <div className="empty-state" role="status">Loading Dyscover...</div>; }
export function ErrorState() { return <div className="empty-state" role="alert">Something went wrong. Please try again.</div>; }

export function Mascot({ mood = 'idle', size = 'medium' }: { mood?: 'idle' | 'happy' | 'thinking' | 'excited'; size?: 'small' | 'medium' | 'large' }) {
	return <div className={`mascot mascot-${size} mascot-${mood}`} role="img" aria-label="Dyscover companion">
		<span className="mascot-star mascot-star-one">✦</span><span className="mascot-star mascot-star-two">✦</span>
		<div className="mascot-body"><span className="mascot-ear mascot-ear-left" /><span className="mascot-ear mascot-ear-right" /><span className="mascot-eye mascot-eye-left" /><span className="mascot-eye mascot-eye-right" /><span className="mascot-smile" /></div>
	</div>;
}

export function MascotBubble({ children, mood = 'happy' }: { children: ReactNode; mood?: 'idle' | 'happy' | 'thinking' | 'excited' }) {
	return <div className="mascot-bubble"><Mascot mood={mood} size="small" /><p>{children}</p></div>;
}

export function SectionHeader({ eyebrow, title, children }: { eyebrow?: string; title: string; children?: ReactNode }) {
	return <div className="section-heading">{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2>{children}</div>;
}

export function AccessibilityPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
	const [textSize, setTextSize] = useState('normal');
	const [readingStyle, setReadingStyle] = useState('default');
	const [reducedMotion, setReducedMotion] = useState(false);
	useEffect(() => { document.documentElement.dataset.textSize = textSize; document.documentElement.dataset.readingStyle = readingStyle; document.documentElement.dataset.reducedMotion = String(reducedMotion); return () => { delete document.documentElement.dataset.textSize; delete document.documentElement.dataset.readingStyle; delete document.documentElement.dataset.reducedMotion; }; }, [textSize, readingStyle, reducedMotion]);
	if (!open) return null;
	return <div className="settings-popover" role="dialog" aria-label="Accessibility settings">
		<div className="settings-heading"><strong>Make it comfortable</strong><button className="icon-button" onClick={onClose} aria-label="Close accessibility settings">×</button></div>
		<label className="setting-row">Text size<select value={textSize} onChange={(event) => setTextSize(event.target.value)}><option value="normal">Normal</option><option value="large">Large</option><option value="xlarge">Extra large</option></select></label>
		<label className="setting-row">Reading style<select value={readingStyle} onChange={(event) => setReadingStyle(event.target.value)}><option value="default">Dyscover default</option><option value="friendly">Reading friendly</option></select></label>
		<label className="setting-check"><input type="checkbox" checked={reducedMotion} onChange={(event) => setReducedMotion(event.target.checked)} /> Reduce motion</label>
	</div>;
}
