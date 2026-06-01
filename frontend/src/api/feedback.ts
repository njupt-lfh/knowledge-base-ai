/**
 * 对话反馈 API
 * 点赞/点踩/纠正提交，用于 RAG 质量闭环
 * 主要导出：feedbackApi
 */
import request from './request'

export const feedbackApi = {
  /**
   * 提交单条消息的反馈
   * @param kbId 知识库 ID
   * @param body 消息 ID、反馈类型及可选 chunk/纠正文本
   */
  submit: (
    kbId: string,
    body: {
      message_id: string
      feedback_type: 'like' | 'dislike' | 'correction'
      chunk_id?: string
      chunk_ids?: string[]
      correction_text?: string
    },
  ) => request.post(`/api/knowledge-bases/${kbId}/feedback`, body),
}
