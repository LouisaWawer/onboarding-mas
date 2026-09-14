import { useState } from 'react'
import Avatar from '../../components/Avatar/Avatar'
import { useReportBadge } from '../../state/AppNotifications'
import { TABS, announcements, directory, company, type TabId } from './intranetData'
import './Intranet.css'

/**
 * Entspricht Figmas Intranet-Screen (node 69:9808/69:9822). Nur der Tab
 * "Ankündigungen" ist in Figma inhaltlich ausgestaltet; die drei anderen
 * Tabs sind dort nicht gebaut – Inhalte hier aus docs/
 * Fiktive_Firma_und_Kollegen.md (Verzeichnis, Über uns) bzw. als ehrlicher
 * Minimalzustand ("Neu im Team", da docs keine weiteren Neuzugänge nennen).
 *
 * "Angaben nicht aktuell? Melden" (useSendToLumi-Trigger bei Tom Bauers
 * veraltetem Eintrag) wieder entfernt - nicht im Studienskript vorgesehen
 * (siehe Bericht an die Nutzerin). Der zugrunde liegende Absturz wurde
 * bewusst nicht weiterverfolgt, war aber vermutlich nicht am Trigger selbst
 * festzumachen (reportOutdated/requestNewMeeting in Kalender.tsx riefen
 * denselben Mechanismus identisch auf).
 */
export default function Intranet() {
  const [activeTab, setActiveTab] = useState<TabId>('ankuendigungen')

  // Badge verschwindet, sobald der Ankündigungen-Tab einmal geöffnet wurde.
  useReportBadge('intranet', activeTab !== 'ankuendigungen' && announcements.some((a) => a.isNew))

  return (
    <div className="intranet">
      <div className="intranet__card">
        <header className="intranet__header">
          <h1 className="intranet__title">Intranet</h1>
        </header>
        <div className="intranet__divider" />

        <div className="intranet__tabs">
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`intranet__tab ${tab.id === activeTab ? 'intranet__tab--active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="intranet__divider" />

        <div className="intranet__content">
          {activeTab === 'ankuendigungen' &&
            announcements.map((post) => (
              <article className="intranet__post" key={post.id}>
                <h2 className="intranet__post-title">{post.title}</h2>
                <p className="intranet__post-meta">
                  Autor:in: {post.author} · Datum: {post.date}
                </p>
                <p className="intranet__post-body">{post.body}</p>
                <div className="intranet__post-divider" />
              </article>
            ))}

          {activeTab === 'verzeichnis' && (
            <ul className="intranet__directory">
              {directory.map((person) => (
                <li className="intranet__person" key={person.id}>
                  <Avatar
                    icon={person.isLumi ? 'lumi' : 'initials'}
                    initials={person.initials}
                    color={person.avatarColor}
                    size={40}
                  />
                  <div className="intranet__person-info">
                    <span className="intranet__person-name">{person.name}</span>
                    <span className="intranet__person-role">{person.role}</span>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {activeTab === 'neu-im-team' && (
            <div className="intranet__empty">
              <p>Diese Woche neu dabei: du! Willkommen bei Nordlicht Software.</p>
              <p className="intranet__empty-hint">
                Weitere Neuzugänge werden hier erscheinen, sobald es sie gibt.
              </p>
            </div>
          )}

          {activeTab === 'ueber-uns' && (
            <div className="intranet__about">
              <h2 className="intranet__about-name">{company.name}</h2>
              <p className="intranet__post-body">{company.description}</p>
              <dl className="intranet__facts">
                {company.facts.map((fact) => (
                  <div className="intranet__fact" key={fact.label}>
                    <dt>{fact.label}</dt>
                    <dd>{fact.value}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
