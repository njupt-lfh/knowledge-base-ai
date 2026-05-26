import request from './request'

export const feedbackApi = {
  submit: (
    kbId: string,
    body: {
      message_id: string
      feedback_type: 'like' | 'dislike' | 'correction'
      chunk_id?: string
      correction_text?: string
    },
  ) => request.post(`/api/knowledge-bases/${kbId}/feedback`, body),
}
