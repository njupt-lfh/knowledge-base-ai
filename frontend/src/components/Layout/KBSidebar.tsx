/**
 * 知识库内左侧导航栏（可折叠）
 * 文档管理/治理/图谱/同步/检索 + AI对话/补全任务
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowLeftOutlined, MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons'
import { kbNavGroups, type KBSidebarItem } from './kbSidebarConfig'
import './KBSidebar.css'

interface KBSidebarProps {
  items: KBSidebarItem[]
  activeKey: string
  onSelect: (key: string) => void
  kbName?: string
}

function kbInitial(name: string): string {
  const trimmed = name.trim()
  if (!trimmed) return 'K'
  return trimmed.charAt(0).toUpperCase()
}

export default function KBSidebar({ items, activeKey, onSelect, kbName }: KBSidebarProps) {
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const itemMap = new Map(items.map((item) => [item.key, item]))

  return (
    <nav
      className={`kb-sidebar ${collapsed ? 'kb-sidebar--collapsed' : ''}`}
      aria-label="知识库导航"
    >
      <div className="kb-sidebar__header">
        <button
          type="button"
          className="kb-sidebar__back"
          onClick={() => navigate('/knowledge-bases')}
          title="返回知识库列表"
        >
          <ArrowLeftOutlined className="kb-sidebar__back-icon" />
          <span className="kb-sidebar__back-text">知识库列表</span>
        </button>
        <button
          type="button"
          className="kb-sidebar__toggle"
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? '展开侧栏' : '收起侧栏'}
          aria-expanded={!collapsed}
        >
          {collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
        </button>
      </div>

      {kbName && (
        <div className="kb-sidebar__identity" title={kbName}>
          {collapsed ? (
            <span className="kb-sidebar__avatar" aria-hidden>
              {kbInitial(kbName)}
            </span>
          ) : (
            <p className="kb-sidebar__name">{kbName}</p>
          )}
        </div>
      )}

      <div className="kb-sidebar__body">
        {kbNavGroups.map((group) => {
          const groupItems = group.keys
            .map((key) => itemMap.get(key))
            .filter((item): item is KBSidebarItem => Boolean(item))

          if (groupItems.length === 0) return null

          return (
            <section key={group.label} className="kb-sidebar__section">
              <h3 className="kb-sidebar__section-label">{group.label}</h3>
              <ul className="kb-sidebar__list">
                {groupItems.map((item) => (
                  <li key={item.key}>
                    <button
                      type="button"
                      className={`kb-sidebar__item ${activeKey === item.key ? 'kb-sidebar__item--active' : ''}`}
                      onClick={() => onSelect(item.key)}
                      title={collapsed ? item.label : undefined}
                    >
                      <span className="kb-sidebar__item-icon">{item.icon}</span>
                      <span className="kb-sidebar__item-label">{item.label}</span>
                      {item.badge ? <span className="kb-sidebar__badge">{item.badge}</span> : null}
                      {activeKey === item.key && (
                        <span className="kb-sidebar__indicator" aria-hidden />
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )
        })}
      </div>
    </nav>
  )
}
