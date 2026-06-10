/**
 * 数据驾驶舱页
 * Tab1 全局概览（一屏 Bento）· Tab2 单库深度分析
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Spin, Tabs } from 'antd'
import { DatabaseOutlined, FileTextOutlined, BlockOutlined, EyeOutlined } from '@ant-design/icons'
import { useStats } from '../hooks/useStats'
import StatCard from '../components/Charts/StatCard'
import TrendLineChart from '../components/Charts/TrendLineChart'
import DistributionPie from '../components/Charts/DistributionPie'
import DocTypePie from '../components/Charts/DocTypePie'
import HotBarChart from '../components/Charts/HotBarChart'
import Top3Cards from '../components/Charts/Top3Cards'
import HitHistogram from '../components/Charts/HitHistogram'
import CiteHitChart from '../components/Charts/CiteHitChart'
import RagSankeyChart from '../components/Charts/RagSankeyChart'
import ActivityHeatmap from '../components/Charts/ActivityHeatmap'
import ColdKnowledgeBadge from '../components/Charts/ColdKnowledgeBadge'
import { ChartRemeasureContext } from '../components/Charts/ChartLayoutContext'
import HudPanel from '../components/common/HudPanel'
import '../components/Charts/StatCard.css'
import './Stats.css'

/** 统计仪表盘主页面 */
export default function Stats() {
  const {
    overview,
    trend,
    activity,
    kbs,
    selectedKb,
    kbStats,
    kbCold,
    kbDocTypes,
    kbAdvanced,
    loading,
    selectKb,
    selectGlobal,
    loadKbDeep,
  } = useStats()

  const [activeTab, setActiveTab] = useState<'overview' | 'deep'>('overview')
  const pendingDeepDefault = useRef(false)
  const selectedKbName = kbs.find((kb) => kb.id === selectedKb)?.name

  const selectFirstKbIfNeeded = useCallback(() => {
    if (selectedKb || kbs.length === 0) return false
    selectKb(kbs[0].id)
    return true
  }, [selectedKb, kbs, selectKb])

  const onTabChange = useCallback(
    (key: string) => {
      const tab = key as 'overview' | 'deep'
      setActiveTab(tab)
      if (tab === 'deep') {
        if (!selectFirstKbIfNeeded()) pendingDeepDefault.current = true
      } else {
        pendingDeepDefault.current = false
      }
    },
    [selectFirstKbIfNeeded],
  )

  /** 知识库列表晚于 Tab 切换到达时，深度 Tab 补选第一个 */
  useEffect(() => {
    if (!pendingDeepDefault.current || activeTab !== 'deep' || selectedKb || kbs.length === 0)
      return
    pendingDeepDefault.current = false
    selectKb(kbs[0].id)
  }, [activeTab, selectedKb, kbs, selectKb])

  /** 进入深度 Tab 时懒加载深度指标 */
  useEffect(() => {
    if (activeTab !== 'deep' || !selectedKb || kbAdvanced) return
    loadKbDeep(selectedKb)
  }, [activeTab, selectedKb, kbAdvanced, loadKbDeep])

  /** Tab 切换后布局稳定时触发图表重测 */
  useEffect(() => {
    const id = window.requestAnimationFrame(() => {
      window.dispatchEvent(new Event('resize'))
    })
    return () => window.cancelAnimationFrame(id)
  }, [activeTab])

  const coldKnowledge = selectedKb ? kbCold : overview?.cold_knowledge

  const overviewKpis = useMemo(() => {
    if (selectedKb && kbStats) {
      return {
        kb_count: 1,
        doc_count: kbStats.document_count,
        chunk_count: kbStats.chunk_count,
        total_hits: kbStats.total_hits,
      }
    }
    return {
      kb_count: overview?.kb_count ?? 0,
      doc_count: overview?.doc_count ?? 0,
      chunk_count: overview?.chunk_count ?? 0,
      total_hits: overview?.total_hits ?? 0,
    }
  }, [selectedKb, kbStats, overview])

  const overviewTopChunks = useMemo(() => {
    if (selectedKb && kbStats) {
      return kbStats.hot_items
        .slice(0, 5)
        .map((item) => ({ content: item.content, hits: item.hit_count }))
    }
    return overview?.top_chunks ?? []
  }, [selectedKb, kbStats, overview])

  const top3Title = selectedKb ? '本库 TOP 3 热知识' : '全局 TOP 3 热知识'

  return (
    <Spin spinning={loading} wrapperClassName="stats-page-spin">
      <ChartRemeasureContext.Provider value={activeTab}>
        <div className="stats-page">
          <Tabs
            className="stats-page__tabs"
            activeKey={activeTab}
            onChange={onTabChange}
            renderTabBar={(tabBarProps, DefaultTabBar) => (
              <div className="stats-page__tab-shell">
                <DefaultTabBar {...tabBarProps} />
                <div className="stats-page__toolbar">
                  <KbSelector
                    kbs={kbs}
                    selectedKb={selectedKb}
                    selectedKbName={selectedKbName}
                    onSelectGlobal={selectGlobal}
                    onSelectKb={selectKb}
                  />
                  <ColdKnowledgeBadge data={coldKnowledge} compact />
                </div>
              </div>
            )}
            tabBarExtraContent={{
              left: (
                <div className="stats-page__header kb-list-header">
                  <h2 className="page-title">数据驾驶舱</h2>
                  <p className="page-subtitle">全局知识库运营数据实时监控 · 真实数据驱动</p>
                </div>
              ),
            }}
            items={[
              {
                key: 'overview',
                label: '全局概览',
                forceRender: true,
                children: (
                  <div className="stats-overview">
                    <div className="stats-overview__kpis">
                      <StatCard
                        title="知识库"
                        value={overviewKpis.kb_count}
                        icon={<DatabaseOutlined />}
                        delta={selectedKb ? '当前库' : '活跃资产'}
                        index={0}
                      />
                      <StatCard
                        title="文档总数"
                        value={overviewKpis.doc_count}
                        icon={<FileTextOutlined />}
                        delta="已入库"
                        index={1}
                      />
                      <StatCard
                        title="知识块"
                        value={overviewKpis.chunk_count}
                        icon={<BlockOutlined />}
                        delta="向量化"
                        index={2}
                      />
                      <StatCard
                        title="总命中"
                        value={overviewKpis.total_hits}
                        icon={<EyeOutlined />}
                        delta="检索+对话"
                        hot
                        index={3}
                      />
                    </div>
                    <div className="stats-overview__trend">
                      <TrendLineChart points={trend} fill />
                    </div>
                    <div className="stats-overview__pie">
                      {selectedKb ? (
                        <DocTypePie data={kbDocTypes} fill />
                      ) : (
                        <DistributionPie data={overview?.kb_distribution ?? []} fill />
                      )}
                    </div>
                    <div className="stats-overview__heatmap">
                      <ActivityHeatmap points={activity} fill />
                    </div>
                    <div className="stats-overview__top3">
                      <Top3Cards items={overviewTopChunks} title={top3Title} fill />
                    </div>
                  </div>
                ),
              },
              {
                key: 'deep',
                label: '单库深度',
                forceRender: true,
                children: (
                  <div className="stats-deep">
                    {activeTab === 'deep' && selectedKb && kbAdvanced ? (
                      <KbDeepSection kbStats={kbStats} kbAdvanced={kbAdvanced} />
                    ) : (
                      <p className="stats-deep__empty">
                        请在上方选择知识库，查看热度分布、引用转化与 RAG 链路等深度指标
                      </p>
                    )}
                  </div>
                ),
              },
            ]}
          />
        </div>
      </ChartRemeasureContext.Provider>
    </Spin>
  )
}

/** 知识库切换（全局 + 各库） */
function KbSelector({
  kbs,
  selectedKb,
  selectedKbName,
  onSelectGlobal,
  onSelectKb,
}: {
  kbs: { id: string; name: string }[]
  selectedKb: string | null
  selectedKbName?: string
  onSelectGlobal: () => void
  onSelectKb: (id: string) => void
}) {
  const currentLabel = selectedKb ? selectedKbName : '全部知识库'

  return (
    <div className="stats-deep__selector">
      <div className="stats-deep__selector-head">
        <span className="stats-deep__selector-label">知识库</span>
        {currentLabel ? (
          <span className="stats-deep__selector-current">当前：{currentLabel}</span>
        ) : null}
      </div>
      <div className="kb-selector stats-deep__kb-tags">
        <button
          type="button"
          className={`kb-selector__tag ${selectedKb === null ? 'kb-selector__tag--active' : ''}`}
          onClick={onSelectGlobal}
        >
          全局
        </button>
        {kbs.map((kb) => (
          <button
            key={kb.id}
            type="button"
            className={`kb-selector__tag ${selectedKb === kb.id ? 'kb-selector__tag--active' : ''}`}
            onClick={() => onSelectKb(kb.id)}
          >
            {kb.name}
          </button>
        ))}
      </div>
    </div>
  )
}

/** 选中知识库后的深度图表区 */
function KbDeepSection({
  kbStats,
  kbAdvanced,
}: {
  kbStats: ReturnType<typeof useStats>['kbStats']
  kbAdvanced: ReturnType<typeof useStats>['kbAdvanced']
}) {
  if (!kbAdvanced) return null

  const hotItems = kbStats?.hot_items ?? []

  return (
    <div className="stats-deep-bento">
      <div className="stats-deep-bento__hist">
        <HitHistogram buckets={kbAdvanced.distribution} fill />
      </div>
      <div className="stats-deep-bento__cite">
        <CiteHitChart items={kbAdvanced.citeVsHit} fill />
      </div>
      <div className="stats-deep-bento__sankey">
        <RagSankeyChart nodes={kbAdvanced.sankey.nodes} links={kbAdvanced.sankey.links} fill />
      </div>
      <div className="stats-deep-bento__hot">
        {hotItems.length > 0 ? (
          <HotBarChart items={hotItems} fill />
        ) : (
          <HudPanel hot className="chart-panel chart-panel--fill">
            <h3 className="chart-panel__title">知识热度 TOP</h3>
            <p className="stats-deep-bento__placeholder">该知识库暂无命中数据</p>
          </HudPanel>
        )}
      </div>
    </div>
  )
}
