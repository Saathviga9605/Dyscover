import { Link } from 'react-router-dom';
import { Card, Mascot, PageHeader } from '../components/ui';

const visualGroup = [
  ['letter-detective', 'Letter Detective', 'Spot the odd lowercase letter out.'],
  ['mirror-match', 'Mirror Match', 'Find the twin that really matches.'],
  ['word-flash', 'Word Flash', 'Catch and remember the flash.'],
  ['sequence-quest', 'Sequence Quest', 'Watch an order, then repeat it.'],
  ['word-maze', 'Word Maze', 'Pick the word the helper wants.'],
] as const;

const speechGroup = [
  ['sound-quest-adventure', 'Sound Quest Adventure', 'Say each word to move the story along.'],
  ['letter-bubble-pop', 'Letter Bubble Pop', 'Say the letters you see to pop the bubbles.'],
  ['maze-runner-rush', 'Maze Runner Rush', 'Name each word as it flashes on the path.'],
] as const;

export function ChildAssessmentHub() {
  return (
    <div className="child-space hub-page">
      <div className="child-topbar">
        <Link className="child-brand" to="/"><span className="brand-mark">✦</span>Dyscover</Link>
        <Link className="child-exit" to="/">Grown-up space <span>↗</span></Link>
      </div>
      <PageHeader eyebrow="✦ explorer mode ✦" title="Pick today's adventure.">
        <p className="page-lede">You can play the visual games, the listening games, or both — whatever feels right.</p>
      </PageHeader>
      <section className="hub-group">
        <div className="hub-group-head"><span className="eyebrow">Visual and reading</span><h2>Look, watch, and choose.</h2></div>
        <div className="hub-card-row">
          {visualGroup.map(([id, name, copy]) => (
            <Card key={id} className={`hub-card hub-card-${id}`}><span className="hub-icon">✦</span><h3>{name}</h3><p>{copy}</p></Card>
          ))}
        </div>
        <Link className="button button-sun hub-launch" to="/child/assessment/visual">Play the visual adventures <span>→</span></Link>
      </section>
      <section className="hub-group">
        <div className="hub-group-head"><span className="eyebrow">Speech and reading</span><h2>Listen, say, and pop.</h2></div>
        <div className="hub-card-row">
          {speechGroup.map(([id, name, copy]) => (
            <Card key={id} className={`hub-card hub-card-${id}`}><span className="hub-icon">⌁</span><h3>{name}</h3><p>{copy}</p></Card>
          ))}
        </div>
        <Link className="button button-sun hub-launch" to="/child/assessment/speech">Play the listening adventures <span>→</span></Link>
      </section>
      <section className="hub-note"><Mascot mood="happy" size="medium" /><div><span className="eyebrow">A calm reminder</span><p>There is no right or wrong. Take your time, and we can explore together.</p></div></section>
    </div>
  );
}