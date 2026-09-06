import { useEffect, useState } from 'react'
import Tree, { type TreeNode } from '../../components/Tree/Tree'
import PreviewBlock from '../../components/PreviewBlock/PreviewBlock'
import Filter from '../../components/Filter/Filter'
import { useReportBadge } from '../../state/AppNotifications'
import { tree, articles, abwesenheitArticles, type Article } from './knowledgeHubData'
import './KnowledgeHub.css'

type View = 'landing' | 'filtered' | 'detail'

const FILTERS = ['Zuletzt angesehen', 'kürzlich veröffentlicht', 'Für mich Relevant']

type KnowledgeHubProps = {
  /** Ändert sich bei jedem Klick auf das Sidebar-Icon (auch wenn Hub schon aktiv ist) – setzt die Navigation auf Landing zurück. */
  resetToken?: number
}

function findPath(nodes: TreeNode[], id: string, trail: string[] = []): string[] | null {
  for (const node of nodes) {
    const nextTrail = [...trail, node.label]
    if (node.id === id) return nextTrail
    if (node.children) {
      const found = findPath(node.children, id, nextTrail)
      if (found) return found
    }
  }
  return null
}

function findNode(nodes: TreeNode[], id: string): TreeNode | undefined {
  for (const node of nodes) {
    if (node.id === id) return node
    if (node.children) {
      const found = findNode(node.children, id)
      if (found) return found
    }
  }
  return undefined
}

function collectArticleIds(node: TreeNode): string[] {
  const ids = articles[node.id] ? [node.id] : []
  return node.children ? ids.concat(...node.children.map(collectArticleIds)) : ids
}

export default function KnowledgeHub({ resetToken }: KnowledgeHubProps) {
  const [readIds, setReadIds] = useState<string[]>([])
  const [view, setView] = useState<View>('landing')
  const [selectedTreeId, setSelectedTreeId] = useState<string | undefined>(undefined)
  const [activeArticleId, setActiveArticleId] = useState<string | null>(null)
  const [filteredBreadcrumb, setFilteredBreadcrumb] = useState('')
  const [filteredArticleIds, setFilteredArticleIds] = useState<string[]>([])
  const [activeFilter, setActiveFilter] = useState(FILTERS[0])

  // Sidebar-Icon dient als Home-Button für den Knowledge Hub: jeder Klick
  // (auch bei bereits aktivem Bereich) soll zur Landing-Ansicht zurückführen.
  useEffect(() => {
    setView('landing')
    setSelectedTreeId(undefined)
    setActiveArticleId(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetToken])

  useReportBadge(
    'hub',
    Object.values(articles).some((a) => a.isNew && !readIds.includes(a.id)),
  )

  function selectTreeNode(id: string) {
    setSelectedTreeId(id)

    if (articles[id]) {
      setActiveArticleId(id)
      setView('detail')
      setReadIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
      return
    }

    const node = findNode(tree, id)
    const path = findPath(tree, id)
    setFilteredBreadcrumb(path ? path.join(' / ') : '')
    setFilteredArticleIds(node ? collectArticleIds(node) : [])
    setView('filtered')
  }

  function openArticle(id: string) {
    setSelectedTreeId(id)
    setActiveArticleId(id)
    setView('detail')
    setReadIds((prev) => (prev.includes(id) ? prev : [...prev, id]))
  }

  const activeArticle: Article | undefined = activeArticleId ? articles[activeArticleId] : undefined

  return (
    <div className="hub">
      <div className="hub__card">
        <h1 className="hub__title">Wissens Hub</h1>
        <div className="hub__divider" />
        <div className="hub__body">
          <nav className="hub__tree" aria-label="Knowledge-Hub-Navigation">
            <Tree nodes={tree} selectedId={selectedTreeId} onSelect={selectTreeNode} />
          </nav>

          <div className="hub__content">
            {view === 'landing' && (
              <>
                <div className="hub__lumi-suggests">
                  <PreviewBlock
                    variant="card"
                    headline={articles['urlaub-beantragen'].headline}
                    path={articles['urlaub-beantragen'].path}
                    content={articles['urlaub-beantragen'].preview}
                    onClick={() => openArticle('urlaub-beantragen')}
                  />
                </div>
                <div className="hub__filters">
                  {FILTERS.map((label) => (
                    <Filter key={label} label={label} active={label === activeFilter} onClick={() => setActiveFilter(label)} />
                  ))}
                </div>
                {abwesenheitArticles.map((id) => (
                  <PreviewBlock
                    key={id}
                    headline={articles[id].headline}
                    path={articles[id].path}
                    content={articles[id].preview}
                    onClick={() => openArticle(id)}
                  />
                ))}
              </>
            )}

            {view === 'filtered' && (
              <>
                <p className="hub__breadcrumb">{filteredBreadcrumb}</p>
                {filteredArticleIds.length > 0 ? (
                  filteredArticleIds.map((id) => (
                    <PreviewBlock
                      key={id}
                      headline={articles[id].headline}
                      path={articles[id].path}
                      content={articles[id].preview}
                      onClick={() => openArticle(id)}
                    />
                  ))
                ) : (
                  <p className="hub__empty">Für diesen Bereich sind in diesem Prototyp noch keine Artikel hinterlegt.</p>
                )}
              </>
            )}

            {view === 'detail' && activeArticle && (
              <>
                <p className="hub__breadcrumb">{activeArticle.breadcrumb}</p>
                <div className="hub__article">
                  <h2 className="hub__article-headline">{activeArticle.headline}</h2>
                  {activeArticle.meta && <p className="hub__article-meta">{activeArticle.meta}</p>}
                  <p className="hub__article-body">{activeArticle.body ?? activeArticle.preview}</p>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
