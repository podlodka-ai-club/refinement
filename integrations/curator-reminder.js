// Memory Curator: напоминание свериться с базой знаний, когда сессия
// уходит в idle (ответ агента завершён). macOS-нотификация, один раз
// на сессию; любые ошибки глушатся — плагин не должен ломать opencode.
const seen = new Set()

export const CuratorReminder = async ({ $ }) => {
  return {
    event: async ({ event }) => {
      if (event.type !== "session.idle") return
      const id =
        event.properties?.sessionID ??
        event.properties?.session_id ??
        event.properties?.info?.sessionID
      if (id) {
        if (seen.has(id)) return
        seen.add(id)
      }
      try {
        await $`osascript -e 'display notification "Если в сессии были проверенные уроки — /curator-save" with title "Memory Curator"'`
      } catch {
        // не macOS или osascript недоступен — молча
      }
    },
  }
}