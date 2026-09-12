import { Link } from 'react-router-dom';
import { Card, Mascot, PageHeader } from '../components/ui';
import { useLanguage } from '../l10n';
import { languageName, isActivityAvailable, speechAssessmentPlanFor } from '../l10n/languages';
import type { MessageKey } from '../l10n/messages/en';

const visualGroup: ReadonlyArray<readonly [string, MessageKey, MessageKey]> = [
  ['letter-detective', 'hub.gameLetterDetective', 'hub.gameLetterDetectiveCopy'],
  ['mirror-match', 'hub.gameMirrorMatch', 'hub.gameMirrorMatchCopy'],
  ['word-flash', 'hub.gameWordFlash', 'hub.gameWordFlashCopy'],
  ['sequence-quest', 'hub.gameSequenceQuest', 'hub.gameSequenceQuestCopy'],
  ['word-maze', 'hub.gameWordMaze', 'hub.gameWordMazeCopy'],
];

const speechGroup: ReadonlyArray<readonly [string, MessageKey, MessageKey]> = [
  ['sound-quest-adventure', 'hub.gameSoundQuest', 'hub.gameSoundQuestCopy'],
  ['letter-bubble-pop', 'hub.gameLetterBubble', 'hub.gameLetterBubbleCopy'],
  ['maze-runner-rush', 'hub.gameMazeRunner', 'hub.gameMazeRunnerCopy'],
];

export function ChildAssessmentHub() {
  const { t, language, setLanguage } = useLanguage();
  const speechAvailable = speechAssessmentPlanFor(language);

  return (
    <div className="child-space hub-page">
      <div className="child-topbar">
        <Link className="child-brand" to="/"><span className="brand-mark">✦</span>Dyscover</Link>
        <Link className="child-exit" to="/">{t('child.topbarGrownups')} <span>↗</span></Link>
      </div>
      <PageHeader eyebrow={t('hub.eyebrow')} title={t('hub.title')}>
        <p className="page-lede">{t('hub.lede')}</p>
      </PageHeader>
      <section className="hub-group">
        <div className="hub-group-head"><span className="eyebrow">{t('hub.visualEyebrow')}</span><h2>{t('hub.visualTitle')}</h2></div>
        <div className="hub-card-row">
          {visualGroup.map(([id, name, copy]) => (
            <Card key={id} className={`hub-card hub-card-${id}`}><span className="hub-icon">✦</span><h3>{t(name)}</h3><p>{t(copy)}</p>{!isActivityAvailable(id, language) && <span className="hub-badge">{t('hub.langOnly', { languageName: languageName(language) })}</span>}</Card>
          ))}
        </div>
        {speechAvailable.length === 0 ? <span className="hub-launch-note">{t('hub.notAvailableNoneCopy', { languageName: languageName(language) })}</span> : null}
        <Link className="button button-sun hub-launch" to="/child/assessment/visual">{t('hub.visualLaunch')} <span>→</span></Link>
      </section>
      <section className="hub-group">
        <div className="hub-group-head"><span className="eyebrow">{t('hub.speechEyebrow')}</span><h2>{t('hub.speechTitle')}</h2></div>
        {speechAvailable.length === 0 ? (
          <div className="hub-unavailable">
            <Mascot mood="thinking" size="medium" />
            <span className="eyebrow">{t('hub.notAvailableEyebrow')}</span>
            <h3>{t('hub.notAvailableNone')}</h3>
            <p>{t('hub.notAvailableNoneCopy', { languageName: languageName(language) })}</p>
            <button className="button button-sun" onClick={() => setLanguage('en')}>{t('hub.notAvailableSwitch')} <span>→</span></button>
          </div>
        ) : (
          <>
            <div className="hub-card-row">
              {speechGroup.map(([id, name, copy]) => (
                <Card key={id} className={`hub-card hub-card-${id}`}><span className="hub-icon">⌁</span><h3>{t(name)}</h3><p>{t(copy)}</p>{!isActivityAvailable(id, language) && <span className="hub-badge">{t('hub.langOnly', { languageName: languageName(language) })}</span>}</Card>
              ))}
            </div>
            <Link className="button button-sun hub-launch" to="/child/assessment/speech">{t('hub.speechLaunch')} <span>→</span></Link>
          </>
        )}
      </section>
      <section className="hub-note"><Mascot mood="happy" size="medium" /><div><span className="eyebrow">{t('hub.reminderKicker')}</span><p>{t('hub.reminderCopy')}</p></div></section>
    </div>
  );
}