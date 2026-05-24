import { Spin } from 'antd'
import {
  DatabaseOutlined,
  FileTextOutlined,
  BlockOutlined,
  EyeOutlined,
} from '@ant-design/icons'
import { useStats } from '../hooks/useStats'
import StatCard from '../components/Charts/StatCard'
import TrendLineChart from '../components/Charts/TrendLineChart'
import DistributionPie from '../components/Charts/DistributionPie'
import HotBarChart from '../components/Charts/HotBarChart'
import Top3Cards from '../components/Charts/Top3Cards'
import HitHistogram from '../components/Charts/HitHistogram'
import CiteHitChart from '../components/Charts/CiteHitChart'
import RagSankeyChart from '../components/Charts/RagSankeyChart'
import ActivityHeatmap from '../components/Charts/ActivityHeatmap'
import ColdKnowledgeBadge from '../components/Charts/ColdKnowledgeBadge'
import '../components/Charts/StatCard.css'

export default function Stats() {
  const {
    overview,
    trend,
    activity,
    kbs,
    selectedKb,
    kbStats,
    kbAdvanced,
    loading,
    loadKbStats,
    clearKbSelection,
  } = useStats()

  return (
    <Spin spinning={loading}>
      <>
        <div className="kb-list-header">
          <div>
            <h2 className="page-title">数据驾驶舱</h2>
            <p className="page-subtitle">全局知识库运营数据实时监控 · 真实数据驱动</p>
          </div>
        </div>

        <ColdKnowledgeBadge data={overview?.cold_knowledge} />

        <div className="stats-grid">
          <StatCard title="知识库" value={overview?.kb_count ?? 0} icon={<DatabaseOutlined />} delta="活跃资产" index={0} />
          <StatCard title="文档总数" value={overview?.doc_count ?? 0} icon={<FileTextOutlined />} delta="已入库" index={1} />
          <StatCard title="知识块" value={overview?.chunk_count ?? 0} icon={<BlockOutlined />} delta="向量化" index={2} />
          <StatCard title="总命中" value={overview?.total_hits ?? 0} icon={<EyeOutlined />} delta="检索+对话" hot index={3} />
        </div>

        <div className="charts-grid">
          <TrendLineChart points={trend} />
          <DistributionPie data={overview?.kb_distribution ?? []} />
        </div>

        <div style={{ marginBottom: 'var(--space-lg)' }}>
          <ActivityHeatmap points={activity} />
        </div>

        <div style={{ marginBottom: 'var(--space-lg)' }}>
          <Top3Cards items={overview?.top_chunks ?? []} />
        </div>

        <HudSection
          kbs={kbs}
          selectedKb={selectedKb}
          kbStats={kbStats}
          kbAdvanced={kbAdvanced}
          onSelectKb={loadKbStats}
          onClearKb={clearKbSelection}
        />
      </>
    </Spin>
  )
}

function HudSection({
  kbs,
  selectedKb,
  kbStats,
  kbAdvanced,
  onSelectKb,
  onClearKb,
}: {
  kbs: { id: string; name: string }[]
  selectedKb: string | null
  kbStats: ReturnType<typeof useStats>['kbStats']
  kbAdvanced: ReturnType<typeof useStats>['kbAdvanced']
  onSelectKb: (id: string) => void
  onClearKb: () => void
}) {
  return (
    <div>
      <h3 className="chart-panel__title" style={{ marginBottom: 16 }}>
        按知识库深度分析
      </h3>
      <div className="kb-selector">
        <button
          type="button"
          className={`kb-selector__tag ${!selectedKb ? 'kb-selector__tag--active' : ''}`}
          onClick={onClearKb}
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

      {selectedKb && kbAdvanced && (
        <>
          <ColdKnowledgeBadge data={kbAdvanced.cold} compact />
          <div className="charts-grid" style={{ marginTop: 16 }}>
            <HitHistogram buckets={kbAdvanced.distribution} />
            <CiteHitChart items={kbAdvanced.citeVsHit} />
          </div>
          <div style={{ marginBottom: 'var(--space-lg)' }}>
            <RagSankeyChart nodes={kbAdvanced.sankey.nodes} links={kbAdvanced.sankey.links} />
          </div>
        </>
      )}

      {selectedKb && kbStats && kbStats.hot_items.length > 0 && (
        <HotBarChart items={kbStats.hot_items} />
      )}
      {selectedKb && kbStats && kbStats.hot_items.length === 0 && (
        <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 13 }}>
          该知识库暂无命中数据
        </p>
      )}
    </div>
  )
}
