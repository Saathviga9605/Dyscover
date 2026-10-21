import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import { useLanguage } from '../l10n';
import {
  api,
  ApiError,
  type ChatMessage,
  type ChatStatus,
  type Conversation,
} from '../services/apiClient';
import { LexiLogo } from './LexiLogo';

const MAX_CHARS = 2000;
const OPEN_EVENT = 'dyscover-open-lexi';

/** Open the Lexi panel from anywhere (e.g. a call-to-action button). */
export function openLexi(): void {
  window.dispatchEvent(new Event(OPEN_EVENT));
}

/** RFC 4122 v4 id; `randomUUID` is unavailable on non-secure origins (e.g. a LAN IP). */
export function newMessageId(): string {
  if (typeof crypto.randomUUID === 'function') return crypto.randomUUID();
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

interface PendingSend {
  content: string;
  clientMessageId: string;
}

function LexiPanel({ onClose }: { onClose: () => void }) {
  const { t } = useLanguage();
  const [status, setStatus] = useState<ChatStatus | null>(null);
  const [statusError, setStatusError] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [draft, setDraft] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<{ text: string; retry: PendingSend | null } | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  // Conversations created by this panel start empty; loading their history would race
  // with the in-flight first message and could duplicate it.
  const createdHere = useRef(new Set<string>());
  const conversationId = conversation?.id ?? null;
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    api
      .getChatStatus()
      .then(value => active && setStatus(value))
      .catch(() => active && setStatusError(true));
    api
      .listConversations()
      .then(list => {
        if (!active) return;
        setConversations(list);
        if (list[0]) setConversation(list[0]);
      })
      .catch(() => undefined);
    inputRef.current?.focus();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!conversationId) {
      setMessages([]);
      return;
    }
    if (createdHere.current.has(conversationId)) return;
    let active = true;
    setLoadingHistory(true);
    api
      .listMessages(conversationId)
      .then(page => active && setMessages(page.messages))
      .catch(() => active && setError({ text: t('lexi.historyError'), retry: null }))
      .finally(() => active && setLoadingHistory(false));
    return () => {
      active = false;
    };
  }, [conversationId, t]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [messages, sending]);

  const describeError = useCallback(
    (err: unknown): string => {
      if (err instanceof ApiError) {
        if (err.code === 'network') return t('common.offline');
        if (err.status === 429) return t('lexi.errorBusy');
        if (err.code === 'not_configured') return t('lexi.notConfigured');
        if (err.status === 504) return t('lexi.errorTimeout');
        if (err.status === 422) return t('lexi.errorInvalid');
      }
      return t('lexi.errorGeneric');
    },
    [t]
  );

  const send = useCallback(
    async (pending: PendingSend) => {
      if (sending) return;
      setSending(true);
      setError(null);
      try {
        let target = conversation;
        if (!target) {
          target = await api.createConversation();
          createdHere.current.add(target.id);
          setConversation(target);
          setConversations(list => [target as Conversation, ...list]);
        }
        const exchange = await api.sendMessage(target.id, pending.content, pending.clientMessageId);
        const added = new Set([exchange.user_message.id, exchange.assistant_message.id]);
        setMessages(current => [
          ...current.filter(message => !added.has(message.id)),
          exchange.user_message,
          exchange.assistant_message,
        ]);
        setConversation(exchange.conversation);
        setConversations(list => [
          exchange.conversation,
          ...list.filter(item => item.id !== exchange.conversation.id),
        ]);
        setDraft(current => (current === pending.content ? '' : current));
      } catch (err) {
        setError({ text: describeError(err), retry: pending });
      } finally {
        setSending(false);
        inputRef.current?.focus();
      }
    },
    [conversation, describeError, sending]
  );

  const submitDraft = () => {
    const content = draft.trim();
    if (!content || sending || content.length > MAX_CHARS) return;
    void send({ content, clientMessageId: newMessageId() });
  };

  const unavailable = statusError || (status !== null && !status.configured);
  const suggestions = [t('lexi.suggestGames'), t('lexi.suggestPrivacy'), t('lexi.suggestHelp')];

  return (
    <section className="lexi-panel" role="dialog" aria-modal="false" aria-labelledby="lexi-title">
      <header className="lexi-heading">
        <div className="lexi-identity">
          <LexiLogo size={36} />
          <div>
            <strong id="lexi-title">Lexi</strong>
            <span className="lexi-subtitle">{t('lexi.subtitle')}</span>
          </div>
        </div>
        <div className="lexi-toolbar">
          <button
            type="button"
            className="icon-button"
            onClick={() => setShowHistory(value => !value)}
            aria-expanded={showHistory}
            aria-label={t('lexi.history')}
            title={t('lexi.history')}
          >
            ☰
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={() => {
              setConversation(null);
              setMessages([]);
              setError(null);
              setShowHistory(false);
              inputRef.current?.focus();
            }}
            aria-label={t('lexi.newChat')}
            title={t('lexi.newChat')}
          >
            ＋
          </button>
          <button
            type="button"
            className="icon-button"
            onClick={onClose}
            aria-label={t('lexi.close')}
            title={t('lexi.close')}
          >
            ×
          </button>
        </div>
      </header>

      {showHistory && (
        <nav className="lexi-history" aria-label={t('lexi.history')}>
          {conversations.length ? (
            <ul>
              {conversations.map(item => (
                <li key={item.id} className={item.id === conversation?.id ? 'active' : ''}>
                  <button
                    type="button"
                    onClick={() => {
                      setConversation(item);
                      setShowHistory(false);
                    }}
                  >
                    {item.title || t('lexi.untitled')}
                  </button>
                  <button
                    type="button"
                    className="icon-button"
                    aria-label={t('lexi.deleteChat', { title: item.title || t('lexi.untitled') })}
                    onClick={async () => {
                      await api.deleteConversation(item.id).catch(() => undefined);
                      setConversations(list => list.filter(entry => entry.id !== item.id));
                      if (conversation?.id === item.id) setConversation(null);
                    }}
                  >
                    🗑
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="subtle-text">{t('lexi.noHistory')}</p>
          )}
        </nav>
      )}

      <div
        className="lexi-messages"
        ref={listRef}
        aria-live="polite"
        aria-busy={sending || loadingHistory}
      >
        {unavailable ? (
          <p className="lexi-notice" role="status">
            {t('lexi.notConfigured')}
          </p>
        ) : null}
        {!messages.length && !loadingHistory && !unavailable && (
          <div className="lexi-welcome">
            <p className="lexi-message">{t('lexi.welcome')}</p>
            <div className="lexi-chips">
              {suggestions.map(text => (
                <button
                  key={text}
                  type="button"
                  disabled={sending}
                  onClick={() => void send({ content: text, clientMessageId: newMessageId() })}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        )}
        {loadingHistory && <p className="subtle-text">{t('common.loading')}</p>}
        {messages.map(message => (
          <div
            key={message.id}
            className={`lexi-message ${message.role === 'user' ? 'lexi-message-user' : ''}`}
          >
            <span className="visually-hidden">
              {message.role === 'user' ? t('lexi.you') : 'Lexi'}:{' '}
            </span>
            {message.content}
          </div>
        ))}
        {sending && (
          <div className="lexi-message lexi-typing" role="status">
            <span className="visually-hidden">{t('lexi.typing')}</span>
            <i aria-hidden="true" />
            <i aria-hidden="true" />
            <i aria-hidden="true" />
          </div>
        )}
      </div>

      {error && (
        <div className="lexi-error" role="alert">
          <span>{error.text}</span>
          {error.retry && (
            <button
              type="button"
              className="text-link"
              disabled={sending}
              onClick={() => error.retry && void send(error.retry)}
            >
              {t('common.retry')}
            </button>
          )}
        </div>
      )}

      <form
        className="lexi-form"
        onSubmit={event => {
          event.preventDefault();
          submitDraft();
        }}
      >
        <label htmlFor="lexi-input" className="visually-hidden">
          {t('lexi.inputLabel')}
        </label>
        <textarea
          id="lexi-input"
          ref={inputRef}
          rows={2}
          value={draft}
          maxLength={MAX_CHARS}
          disabled={unavailable}
          placeholder={t('lexi.placeholder')}
          onChange={event => setDraft(event.target.value)}
          onKeyDown={event => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
              event.preventDefault();
              submitDraft();
            }
          }}
        />
        <button
          className="button button-small"
          type="submit"
          disabled={sending || unavailable || !draft.trim()}
        >
          {sending ? t('lexi.sending') : t('lexi.send')}
        </button>
      </form>
      <p className="lexi-disclosure">{t('lexi.disclosure')}</p>
    </section>
  );
}

export function LexiWidget() {
  const { t } = useLanguage();
  const { isAuthenticated, isLoading } = useAuth();
  const [open, setOpen] = useState(false);
  const toggleRef = useRef<HTMLButtonElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    toggleRef.current?.focus();
  }, []);

  useEffect(() => {
    const onOpen = () => setOpen(true);
    window.addEventListener(OPEN_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_EVENT, onOpen);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') close();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, close]);

  return (
    <div className="lexi-wrap">
      {open &&
        (isAuthenticated ? (
          <LexiPanel onClose={close} />
        ) : (
          <section className="lexi-panel" role="dialog" aria-labelledby="lexi-title">
            <header className="lexi-heading">
              <div className="lexi-identity">
                <LexiLogo size={36} />
                <strong id="lexi-title">Lexi</strong>
              </div>
              <button
                type="button"
                className="icon-button"
                onClick={close}
                aria-label={t('lexi.close')}
              >
                ×
              </button>
            </header>
            <div className="lexi-messages">
              <p className="lexi-message">
                {isLoading ? t('common.loading') : t('lexi.signInPrompt')}
              </p>
            </div>
            {!isLoading && (
              <div className="lexi-form">
                <Link className="button button-small" to="/login" onClick={close}>
                  {t('auth.loginNav')}
                </Link>
              </div>
            )}
          </section>
        ))}
      <button
        ref={toggleRef}
        type="button"
        className="lexi-toggle"
        onClick={() => (open ? close() : setOpen(true))}
        aria-expanded={open}
        aria-label={open ? t('lexi.close') : t('lexi.open')}
      >
        <LexiLogo size={34} />
        <span>Lexi</span>
      </button>
    </div>
  );
}
