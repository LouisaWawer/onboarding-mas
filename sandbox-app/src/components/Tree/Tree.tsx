import { useState } from 'react'
import { CaretRight, CaretDown, FolderSimple, FileText } from '@phosphor-icons/react'
import './Tree.css'

export type TreeNode = {
  id: string
  label: string
  /** Explizit statt aus `children` abgeleitet – manche Ordner haben (noch) keine sichtbaren Kinder, sollen aber trotzdem als Ordner erscheinen. */
  kind: 'folder' | 'file'
  children?: TreeNode[]
}

type TreeProps = {
  nodes: TreeNode[]
  selectedId?: string
  onSelect?: (id: string) => void
}

export default function Tree({ nodes, selectedId, onSelect }: TreeProps) {
  return (
    <ul className="tree" role="tree">
      {nodes.map((node) => (
        <TreeItem key={node.id} node={node} level={1} selectedId={selectedId} onSelect={onSelect} />
      ))}
    </ul>
  )
}

function TreeItem({
  node,
  level,
  selectedId,
  onSelect,
}: {
  node: TreeNode
  level: number
  selectedId?: string
  onSelect?: (id: string) => void
}) {
  const [expanded, setExpanded] = useState(true)
  const hasChildren = !!node.children?.length
  const isSelected = node.id === selectedId
  const isFolder = node.kind === 'folder'

  return (
    <li role="treeitem" aria-expanded={hasChildren ? expanded : undefined}>
      <button
        type="button"
        className={`tree__row ${isSelected ? 'tree__row--selected' : ''}`}
        style={{ paddingLeft: 2 + (level - 1) * 16 }}
        onClick={() => {
          if (hasChildren) setExpanded((v) => !v)
          onSelect?.(node.id)
        }}
      >
        {hasChildren ? (
          expanded ? (
            <CaretDown size={16} color="var(--color-text)" />
          ) : (
            <CaretRight size={16} color="var(--color-text)" />
          )
        ) : (
          <span className="tree__spacer" />
        )}
        {isFolder ? (
          <FolderSimple size={16} color={isSelected ? 'var(--color-accent)' : 'var(--color-text)'} />
        ) : (
          <FileText size={16} color={isSelected ? 'var(--color-accent)' : 'var(--color-text)'} />
        )}
        <span className={isSelected ? 'tree__label tree__label--selected' : 'tree__label'}>
          {node.label}
        </span>
      </button>
      {hasChildren && expanded && (
        <ul role="group">
          {node.children!.map((child) => (
            <TreeItem key={child.id} node={child} level={level + 1} selectedId={selectedId} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  )
}
