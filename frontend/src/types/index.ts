/**
 * 全局 TypeScript 类型定义
 * 与后端 API 响应结构对齐，供页面与 API 层复用
 * 主要导出：KnowledgeBase、Document、Chunk、Conversation、Message 等接口
 */

/** 知识库元数据与统计摘要 */
export interface KnowledgeBase {
  id: string
  name: string
  description: string | null
  embedding_model: string
  chunk_size: number
  chunk_overlap: number
  created_at: string
  updated_at: string
  document_count: number
  total_hits?: number
}

/** 已入库文档及其处理状态 */
export interface Document {
  id: string
  knowledge_base_id: string
  filename: string
  file_type: string
  file_path: string | null
  file_size: number | null
  status: string
  chunk_count: number
  char_count: number
  ingest_duplicate_count?: number
  ingest_conflict_count?: number
  is_active: boolean
  created_at: string
  updated_at: string
}

/** 文档分块（向量检索最小单元） */
export interface Chunk {
  id: string
  document_id: string
  knowledge_base_id: string
  content: string
  chunk_index: number
  char_count: number
  is_active: boolean
  hit_count: number
  created_at: string
}

/** 检索 API 返回的单条结果 */
export interface SearchResultItem {
  chunk_id: string
  content: string
  score: number
  document_id: string
  chunk_index: number
}

/** 对话会话 */
export interface Conversation {
  id: string
  knowledge_base_id: string
  title: string
  share_token: string | null
  created_at: string
}

/** RAG 引用来源（chunk 及相似度） */
export interface SourceItem {
  chunk_id: string
  content: string
  score: number
  chunk_index?: number
  document_id?: string
}

/** 对话消息（用户或助手） */
export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceItem[] | null
  created_at: string
}
