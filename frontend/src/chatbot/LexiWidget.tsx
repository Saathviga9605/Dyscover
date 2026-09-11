import { useState } from 'react';
import { Mascot } from '../components/ui';

export function LexiWidget() {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState(['Lexi is getting ready for your next adventure.']);
  const sendMessage = (value: string) => { const trimmed = value.trim(); if (!trimmed) return; setMessages(current => [...current, trimmed, 'That is a lovely question. A grown-up can explore it with you.']); setMessage(''); };
  return <div className="lexi-wrap">
    {open && <section className="lexi-panel" aria-label="Lexi assistant">
      <div className="lexi-heading"><div className="lexi-identity"><Mascot mood="happy" size="small" /><div><span className="eyebrow">Friendly guide</span><strong>Lexi</strong></div></div><button className="icon-button" onClick={() => setOpen(false)} aria-label="Close Lexi">×</button></div>
      <div className="lexi-messages" aria-live="polite">{messages.map((item, index) => <p className={`lexi-message ${index % 2 ? 'lexi-message-user' : ''}`} key={`${item}-${index}`}>{item}</p>)}</div>
      <div className="lexi-chips"><button onClick={() => sendMessage('What happens next?')}>What happens next?</button><button onClick={() => sendMessage('Tell me about privacy')}>Privacy</button></div>
      <form onSubmit={(event) => { event.preventDefault(); sendMessage(message); }}><input aria-label="Message Lexi" value={message} onChange={(event) => setMessage(event.target.value)} placeholder="Ask Lexi" /><button className="voice-button" type="button" aria-label="Voice input coming soon">◖</button><button className="button button-small" type="submit">Send</button></form>
    </section>}
    <button className="lexi-toggle" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-label="Open Lexi">L<span>Lexi</span></button>
  </div>;
}
