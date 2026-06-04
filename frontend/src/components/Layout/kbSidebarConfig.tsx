/**
 * 知识库侧栏导航配置（与 KBSidebar 组件分离，满足 react-refresh/only-export-components）
 */
import {
  FileTextOutlined,
  WarningOutlined,
  SafetyCertificateOutlined,
  ApartmentOutlined,
  SyncOutlined,
  SearchOutlined,
  MessageOutlined,
  UnorderedListOutlined,
} from '@ant-design/icons'

export interface KBSidebarItem {
  key: string
  label: string
  icon: React.ReactNode
  badge?: number
}

export const kbSidebarItems: KBSidebarItem[] = [
  { key: 'documents', label: '文档管理', icon: <FileTextOutlined /> },
  { key: 'conflicts', label: '入库冲突', icon: <WarningOutlined /> },
  { key: 'governance', label: '治理建议', icon: <SafetyCertificateOutlined /> },
  { key: 'graph', label: '知识图谱', icon: <ApartmentOutlined /> },
  { key: 'sync', label: '文件夹同步', icon: <SyncOutlined /> },
  { key: 'search', label: '检索测试', icon: <SearchOutlined /> },
  { key: 'chat', label: 'AI 对话', icon: <MessageOutlined /> },
  { key: 'gaps', label: '补全任务', icon: <UnorderedListOutlined /> },
]

export const kbNavGroups: { label: string; keys: string[] }[] = [
  { label: '内容管理', keys: ['documents', 'conflicts', 'governance', 'graph', 'sync', 'search'] },
  { label: '智能应用', keys: ['chat', 'gaps'] },
]
