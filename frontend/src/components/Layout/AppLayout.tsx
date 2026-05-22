import { useState } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import { Layout, Menu, Typography } from 'antd'
import { BookOutlined, DatabaseOutlined } from '@ant-design/icons'

const { Sider, Content, Header } = Layout

const menuItems = [
  { key: '/knowledge-bases', icon: <DatabaseOutlined />, label: '知识库管理' },
]

export default function AppLayout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [collapsed, setCollapsed] = useState(false)

  const selectedKey = '/' + location.pathname.split('/')[1]

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible collapsed={collapsed} onCollapse={setCollapsed} theme="dark">
        <div style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <BookOutlined style={{ fontSize: 24, color: '#fff' }} />
          {!collapsed && (
            <Typography.Text style={{ color: '#fff', marginLeft: 8, fontSize: 16, fontWeight: 600 }}>
              KnowledgeBase AI
            </Typography.Text>
          )}
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header style={{ background: '#fff', padding: '0 24px', borderBottom: '1px solid #f0f0f0' }}>
          <Typography.Title level={4} style={{ margin: '16px 0' }}>
            知识库管理平台
          </Typography.Title>
        </Header>
        <Content style={{ margin: 24, minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
