import { useCallback, useEffect, useState } from 'react'
import {
  statsApi,
  type StatsOverview,
  type TrendPoint,
  type KBStats,
  type KBAdvancedStats,
  type ActivityPoint,
} from '../api/stats'
import { knowledgeApi } from '../api/knowledge'

export function useStats() {
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [activity, setActivity] = useState<ActivityPoint[]>([])
  const [kbs, setKbs] = useState<{ id: string; name: string }[]>([])
  const [selectedKb, setSelectedKb] = useState<string | null>(null)
  const [kbStats, setKbStats] = useState<KBStats | null>(null)
  const [kbAdvanced, setKbAdvanced] = useState<KBAdvancedStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [kbLoading, setKbLoading] = useState(false)

  const loadKbStatsInternal = useCallback(async (kbId: string) => {
    setSelectedKb(kbId)
    setKbLoading(true)
    try {
      const [basic, advanced, kbHeat, kbTrend] = await Promise.all([
        statsApi.kbStats(kbId),
        statsApi.kbAdvanced(kbId),
        statsApi.activityHeatmap(kbId, 30),
        statsApi.trend(7, kbId),
      ])
      setKbStats(basic.data)
      setKbAdvanced(advanced)
      setActivity(kbHeat.data.points)
      setTrend(kbTrend.data.points)
    } catch (e) {
      console.error(e)
    } finally {
      setKbLoading(false)
    }
  }, [])

  const loadOverview = useCallback(async () => {
    const [ov, heat, kbList, tr] = await Promise.all([
      statsApi.overview(),
      statsApi.activityHeatmap(undefined, 30),
      knowledgeApi.list({ page: 1, page_size: 100 }),
      statsApi.trend(7),
    ])
    const items = kbList.data.items.map((kb) => ({ id: kb.id, name: kb.name }))
    setOverview(ov.data)
    setActivity(heat.data.points)
    setTrend(tr.data.points)
    setKbs(items)

    if (items.length > 0) {
      await loadKbStatsInternal(items[0].id)
    }
  }, [loadKbStatsInternal])

  const loadKbStats = useCallback(
    (kbId: string) => loadKbStatsInternal(kbId),
    [loadKbStatsInternal],
  )

  const clearKbSelection = useCallback(async () => {
    setSelectedKb(null)
    setKbStats(null)
    setKbAdvanced(null)
    setKbLoading(true)
    try {
      const [heat, tr] = await Promise.all([
        statsApi.activityHeatmap(undefined, 30),
        statsApi.trend(7),
      ])
      setActivity(heat.data.points)
      setTrend(tr.data.points)
    } finally {
      setKbLoading(false)
    }
  }, [])

  useEffect(() => {
    setLoading(true)
    loadOverview()
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [loadOverview])

  return {
    overview,
    trend,
    activity,
    kbs,
    selectedKb,
    kbStats,
    kbAdvanced,
    loading: loading || kbLoading,
    loadKbStats,
    clearKbSelection,
    refresh: loadOverview,
  }
}
