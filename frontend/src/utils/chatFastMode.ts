/** AI 对话「快速模式」开关，按知识库 ID 持久化到 localStorage */

const KEY_PREFIX = 'kb-chat-fast-mode:'

export function loadChatFastMode(kbId: string | undefined): boolean {
  if (!kbId) return false
  try {
    return localStorage.getItem(`${KEY_PREFIX}${kbId}`) === '1'
  } catch {
    return false
  }
}

export function saveChatFastMode(kbId: string | undefined, enabled: boolean): void {
  if (!kbId) return
  try {
    localStorage.setItem(`${KEY_PREFIX}${kbId}`, enabled ? '1' : '0')
  } catch {
    /* ignore quota / private mode */
  }
}
