/**
 * 数据驾驶舱统计 Hook
 * 聚合全局概览与按知识库切换的深度分析数据
 * 主要导出：useStats
 */
import { useCallback, useEffect, useState } from 'react'
import {
  statsApi,
  type StatsOverview,
  type TrendPoint,
  type KBStats,
  type KBAdvancedStats,
  type ActivityPoint,
  type ColdKnowledgeStats,
  type DocTypeItem,
} from '../api/stats'
import { knowledgeApi } from '../api/knowledge'

/**
 * 加载并管理统计页所需的全局与单库数据
 * @returns overview、trend、activity、kbs 及 selectKb / selectGlobal 等方法
 */
export function useStats() {
  const [overview, setOverview] = useState<StatsOverview | null>(null)
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [activity, setActivity] = useState<ActivityPoint[]>([])
  const [kbs, setKbs] = useState<{ id: string; name: string }[]>([])
  const [selectedKb, setSelectedKb] = useState<string | null>(null)
  const [kbStats, setKbStats] = useState<KBStats | null>(null)
  const [kbCold, setKbCold] = useState<ColdKnowledgeStats | null>(null)
  const [kbDocTypes, setKbDocTypes] = useState<DocTypeItem[]>([])
  const [kbAdvanced, setKbAdvanced] = useState<KBAdvancedStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [scopeLoading, setScopeLoading] = useState(false)
  const [deepLoading, setDeepLoading] = useState(false)

  /** 全局概览：KPI / 趋势 / 热力 / 冷知识 */
  const loadGlobalScope = useCallback(async () => {
    const [ov, heat, tr] = await Promise.all([
      statsApi.overview(),
      statsApi.activityHeatmap(undefined, 30),
      statsApi.trend(7),
    ])
    setOverview(ov.data)
    setActivity(heat.data.points)
    setTrend(tr.data.points)
  }, [])

  /** 单库概览：KPI / 趋势 / 热力 / 冷知识（不拉深度指标） */
  const loadKbScope = useCallback(async (kbId: string) => {
    const [basic, kbHeat, kbTrend, cold, docTypes] = await Promise.all([
      statsApi.kbStats(kbId),
      statsApi.activityHeatmap(kbId, 30),
      statsApi.trend(7, kbId),
      statsApi.coldKnowledge(kbId),
      statsApi.docTypes(kbId),
    ])
    setKbStats(basic.data)
    setKbCold(cold.data)
    setKbDocTypes(docTypes.data.items)
    setActivity(kbHeat.data.points)
    setTrend(kbTrend.data.points)
  }, [])

  /** 单库深度指标（分布 / 引用 / 桑基） */
  const loadKbDeep = useCallback(async (kbId: string) => {
    setDeepLoading(true)
    try {
      const [advanced, basic] = await Promise.all([
        statsApi.kbAdvanced(kbId),
        statsApi.kbStats(kbId),
      ])
      setKbAdvanced(advanced)
      setKbStats(basic.data)
    } catch (e) {
      console.error(e)
    } finally {
      setDeepLoading(false)
    }
  }, [])

  /** 首次加载：全局概览与知识库列表 */
  const loadOverview = useCallback(async () => {
    const [, kbList] = await Promise.all([
      loadGlobalScope(),
      knowledgeApi.list({ page: 1, page_size: 100 }),
    ])
    const items = kbList.data.items.map((kb) => ({ id: kb.id, name: kb.name }))
    setKbs(items)
  }, [loadGlobalScope])

  /** 选中「全局」：恢复全平台概览数据 */
  const selectGlobal = useCallback(async () => {
    setSelectedKb(null)
    setKbStats(null)
    setKbCold(null)
    setKbDocTypes([])
    setKbAdvanced(null)
    setScopeLoading(true)
    try {
      await loadGlobalScope()
    } catch (e) {
      console.error(e)
    } finally {
      setScopeLoading(false)
    }
  }, [loadGlobalScope])

  /** 选中知识库：仅切换概览维度，不跳转深度 Tab */
  const selectKb = useCallback(
    async (kbId: string) => {
      setSelectedKb(kbId)
      setKbAdvanced(null)
      setScopeLoading(true)
      try {
        await loadKbScope(kbId)
      } catch (e) {
        console.error(e)
      } finally {
        setScopeLoading(false)
      }
    },
    [loadKbScope],
  )

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
    kbCold,
    kbDocTypes,
    kbAdvanced,
    loading: loading || scopeLoading || deepLoading,
    selectKb,
    selectGlobal,
    loadKbDeep,
    refresh: loadOverview,
  }
}
