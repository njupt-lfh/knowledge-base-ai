import { useEffect, useState } from 'react'
import { Card, Col, Row, Statistic, Table, Tag, Typography, message } from 'antd'
import { evalApi, getReportSampleCount } from '../api/eval'
import HudPanel from '../components/common/HudPanel'

export default function EvalDashboard() {
  const [report, setReport] = useState<EvalBaselineReport | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    evalApi.getBaseline()
      .then((res) => setReport(res.data))
      .catch(() => message.error('未找到基线报告，请先运行 backend/scripts/run_rag_eval.py'))
      .finally(() => setLoading(false))
  }, [])

  const agg = report?.aggregate ?? {}
  const ragas = agg.ragas ?? {}
  const sampleCount = report ? getReportSampleCount(report) : undefined

  const columns = [
    { title: '指标', dataIndex: 'name', key: 'name' },
    { title: '数值', dataIndex: 'value', key: 'value' },
  ]
  const rows = [
    { key: '1', name: 'Context Recall (自定义)', value: agg.context_recall_mean ?? '—' },
    { key: '2', name: 'Context Precision (自定义)', value: agg.context_precision_mean ?? '—' },
    { key: '3', name: 'Retrieval Hit Rate', value: agg.retrieval_hit_rate ?? '—' },
    { key: '4', name: 'Negative Reject Rate', value: agg.negative_reject_rate ?? '—' },
    { key: '5', name: 'Faithfulness (RAGAS/Judge)', value: agg.faithfulness_mean ?? ragas.faithfulness ?? '—' },
    { key: '6', name: 'Answer Relevancy (RAGAS)', value: agg.answer_relevancy_mean ?? ragas.answer_relevancy ?? '—' },
  ]

  return (
    <div style={{ padding: 24 }}>
      <HudPanel title="RAG 评测基线 (Phase 0)">
        {loading && <Typography.Text>加载中...</Typography.Text>}
        {report && (
          <>
            <Typography.Paragraph type="secondary">
              生成时间：{report.generated_at} · 样本数：{sampleCount ?? '—'}
            </Typography.Paragraph>
            <Tag color="blue">{report.diagnosis?.primary_bottleneck}</Tag>
            <Typography.Paragraph>{report.diagnosis?.recommendation}</Typography.Paragraph>
            <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={6}><Card><Statistic title="Recall" value={agg.context_recall_mean ?? 0} precision={3} /></Card></Col>
              <Col span={6}><Card><Statistic title="Precision" value={agg.context_precision_mean ?? 0} precision={3} /></Card></Col>
              <Col span={6}><Card><Statistic title="Hit Rate" value={agg.retrieval_hit_rate ?? 0} precision={3} /></Card></Col>
              <Col span={6}><Card><Statistic title="Faithfulness" value={agg.faithfulness_mean ?? 0} precision={3} /></Card></Col>
            </Row>
            <Table columns={columns} dataSource={rows} pagination={false} size="small" />
          </>
        )}
      </HudPanel>
    </div>
  )
}
