/**
 * 文件夹同步配置面板
 * 添加本地目录监听、手动扫描入库
 * 主要导出：默认 FolderSyncPanel 组件
 */
import { useCallback, useEffect, useState } from 'react'
import { Button, Input, Space, Switch, Table, Typography, message } from 'antd'
import { FolderOpenOutlined, ReloadOutlined, SyncOutlined } from '@ant-design/icons'
import { syncApi, type FolderWatch } from '../../api/sync'
import { formatDateTime } from '../../utils/format'

interface Props {
  kbId: string
  onSynced?: () => void
}

/**
 * 知识库详情「文件夹同步」Tab
 * @param onSynced 扫描入库成功后刷新文档列表与健康度
 */
export default function FolderSyncPanel({ kbId, onSynced }: Props) {
  const [watches, setWatches] = useState<FolderWatch[]>([])
  const [loading, setLoading] = useState(false)
  const [folderPath, setFolderPath] = useState('')
  const [recursive, setRecursive] = useState(false)
  const [scanningId, setScanningId] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      setWatches((await syncApi.listWatches(kbId)).data)
    } catch {
      message.error('加载同步配置失败')
    }
    setLoading(false)
  }, [kbId])

  useEffect(() => {
    load()
  }, [load])

  const handleAdd = async () => {
    const path = folderPath.trim()
    if (!path) {
      message.warning('请填写文件夹路径')
      return
    }
    try {
      await syncApi.createWatch({
        knowledge_base_id: kbId,
        folder_path: path,
        enabled: true,
        recursive,
      })
      message.success('已添加监听目录')
      setFolderPath('')
      await load()
    } catch {
      message.error('添加失败')
    }
  }

  const handleScan = async (watchId: string) => {
    setScanningId(watchId)
    try {
      const res = await syncApi.scanWatch(watchId)
      const r = res.data
      message.success(`扫描完成：新增 ${r.imported}，更新 ${r.updated}，跳过 ${r.skipped}`)
      if (r.errors?.length) {
        message.warning(r.errors[0])
      }
      await load()
      onSynced?.()
    } catch {
      message.error('扫描失败')
    }
    setScanningId(null)
  }

  const handleScanAll = async () => {
    setScanningId('all')
    try {
      const list = (await syncApi.scanKb(kbId)).data
      const imported = list.reduce((s, x) => s + x.imported, 0)
      const updated = list.reduce((s, x) => s + x.updated, 0)
      message.success(`已扫描 ${list.length} 个目录：新增 ${imported}，更新 ${updated}`)
      await load()
      onSynced?.()
    } catch {
      message.error('扫描失败')
    }
    setScanningId(null)
  }

  const columns = [
    {
      title: '目录',
      dataIndex: 'folder_path',
      ellipsis: true,
      render: (v: string) => (
        <Space>
          <FolderOpenOutlined />
          <Typography.Text code style={{ fontSize: 12 }}>
            {v}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '递归',
      dataIndex: 'recursive',
      width: 72,
      render: (v: boolean, row: FolderWatch) => (
        <Switch
          size="small"
          checked={v}
          onChange={async (checked) => {
            await syncApi.updateWatch(row.id, { recursive: checked })
            await load()
          }}
        />
      ),
    },
    {
      title: '启用',
      dataIndex: 'enabled',
      width: 72,
      render: (v: boolean, row: FolderWatch) => (
        <Switch
          size="small"
          checked={v}
          onChange={async (checked) => {
            await syncApi.updateWatch(row.id, { enabled: checked })
            await load()
          }}
        />
      ),
    },
    {
      title: '上次扫描',
      dataIndex: 'last_scan_at',
      width: 160,
      render: (v: string | null) => formatDateTime(v),
    },
    {
      title: '操作',
      width: 140,
      render: (_: unknown, row: FolderWatch) => (
        <Space>
          <Button
            size="small"
            icon={<SyncOutlined />}
            loading={scanningId === row.id}
            onClick={() => handleScan(row.id)}
          >
            扫描
          </Button>
          <Button
            size="small"
            danger
            type="text"
            onClick={async () => {
              await syncApi.deleteWatch(row.id)
              message.success('已删除')
              await load()
            }}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ]

  return (
    <Space direction="vertical" style={{ width: '100%' }} size="middle">
      <Typography.Paragraph type="secondary" style={{ marginBottom: 0 }}>
        将本地文件夹与知识库同步：新文件自动入库，已变更文件将重新处理。后台定时扫描需服务端开启{' '}
        <Typography.Text code>SYNC_WATCH_ENABLED=true</Typography.Text>。
      </Typography.Paragraph>
      <Space.Compact style={{ width: '100%', maxWidth: 720 }}>
        <Input
          placeholder="例如 D:\知识文档\inbox"
          value={folderPath}
          onChange={(e) => setFolderPath(e.target.value)}
          onPressEnter={handleAdd}
        />
        <Button type="primary" onClick={handleAdd}>
          添加监听
        </Button>
      </Space.Compact>
      <Space>
        <Typography.Text type="secondary">包含子目录</Typography.Text>
        <Switch checked={recursive} onChange={setRecursive} />
        <Button icon={<ReloadOutlined />} onClick={load}>
          刷新
        </Button>
        <Button
          icon={<SyncOutlined />}
          loading={scanningId === 'all'}
          disabled={watches.length === 0}
          onClick={handleScanAll}
        >
          扫描全部
        </Button>
      </Space>
      <Table
        rowKey="id"
        size="small"
        loading={loading}
        columns={columns}
        dataSource={watches}
        locale={{ emptyText: '暂无监听目录，请添加本地文件夹路径' }}
        expandable={{
          expandedRowRender: (row) =>
            row.last_error ? (
              <Typography.Text type="danger">{row.last_error}</Typography.Text>
            ) : null,
          rowExpandable: (row) => Boolean(row.last_error),
        }}
      />
    </Space>
  )
}
