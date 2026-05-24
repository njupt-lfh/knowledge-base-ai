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
}

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
  is_active: boolean
  created_at: string
  updated_at: string
}

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

export interface SearchResultItem {
  chunk_id: string
  content: string
  score: number
  document_id: string
  chunk_index: number
}

export interface Conversation {
  id: string
  knowledge_base_id: string
  title: string
  share_token: string | null
  created_at: string
}

export interface SourceItem {
  chunk_id: string
  content: string
  score: number
  chunk_index?: number
  document_id?: string
}

export interface Message {
  id: string
  conversation_id: string
  role: 'user' | 'assistant'
  content: string
  sources: SourceItem[] | null
  created_at: string
}
