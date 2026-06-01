/**
 * Ant Design 主题配置
 * 定义暗色/浅色 HUD 风格 token 与组件样式
 * 主要导出：darkTheme、lightTheme、getAntdTheme、hudTheme（已弃用）
 */
import type { ThemeConfig } from 'antd'
import type { ThemeMode } from '../stores/themeStore'

/** 暗色与浅色主题共享的组件级覆盖 */
const sharedComponents: ThemeConfig['components'] = {
  Button: {
    primaryShadow: '0 0 12px rgba(0, 212, 255, 0.2)',
  },
  Statistic: {
    titleFontSize: 12,
    contentFontSize: 28,
  },
}

/** 暗色 HUD 主题（默认） */
export const darkTheme: ThemeConfig = {
  token: {
    colorPrimary: '#00d4ff',
    colorBgContainer: '#111827',
    colorBgElevated: '#1e293b',
    colorBgLayout: '#0a0e17',
    colorBorder: 'rgba(0, 212, 255, 0.12)',
    colorBorderSecondary: 'rgba(0, 212, 255, 0.08)',
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    colorTextTertiary: '#64748b',
    colorTextQuaternary: '#475569',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#00d4ff',
    borderRadius: 8,
    fontFamily: "'Inter', -apple-system, sans-serif",
    fontSize: 14,
    controlHeight: 36,
    motionDurationMid: '0.25s',
  },
  components: {
    ...sharedComponents,
    Layout: {
      siderBg: '#0a0e17',
      headerBg: '#111827',
      bodyBg: 'transparent',
      triggerBg: '#1e293b',
    },
    Menu: {
      darkItemBg: 'transparent',
      darkItemSelectedBg: 'rgba(0, 212, 255, 0.12)',
      darkItemSelectedColor: '#00d4ff',
      darkItemHoverBg: 'rgba(0, 212, 255, 0.08)',
      darkItemColor: '#94a3b8',
      itemHeight: 44,
      iconSize: 16,
    },
    Card: {
      colorBgContainer: '#111827',
      colorBorderSecondary: 'rgba(0, 212, 255, 0.12)',
    },
    Table: {
      colorBgContainer: '#111827',
      headerBg: '#1e293b',
      rowHoverBg: 'rgba(0, 212, 255, 0.06)',
      borderColor: 'rgba(0, 212, 255, 0.08)',
    },
    Modal: {
      contentBg: '#111827',
      headerBg: '#111827',
      titleColor: '#e2e8f0',
    },
    Input: {
      colorBgContainer: '#0a0e17',
      activeBorderColor: '#00d4ff',
      hoverBorderColor: 'rgba(0, 212, 255, 0.4)',
    },
    Tag: {
      defaultBg: 'rgba(0, 212, 255, 0.08)',
      defaultColor: '#00d4ff',
    },
  },
}

/** 浅色主题 */
export const lightTheme: ThemeConfig = {
  token: {
    colorPrimary: '#0891b2',
    colorBgContainer: '#ffffff',
    colorBgElevated: '#f8fafc',
    colorBgLayout: '#f0f4f8',
    colorBorder: 'rgba(8, 145, 178, 0.18)',
    colorBorderSecondary: 'rgba(15, 23, 42, 0.08)',
    colorText: '#1e293b',
    colorTextSecondary: '#475569',
    colorTextTertiary: '#64748b',
    colorTextQuaternary: '#94a3b8',
    colorSuccess: '#059669',
    colorWarning: '#d97706',
    colorError: '#dc2626',
    colorInfo: '#0891b2',
    borderRadius: 8,
    fontFamily: "'Inter', -apple-system, sans-serif",
    fontSize: 14,
    controlHeight: 36,
    motionDurationMid: '0.25s',
  },
  components: {
    ...sharedComponents,
    Layout: {
      siderBg: '#ffffff',
      headerBg: '#ffffff',
      bodyBg: 'transparent',
      triggerBg: '#f1f5f9',
    },
    Card: {
      colorBgContainer: '#ffffff',
      colorBorderSecondary: 'rgba(8, 145, 178, 0.15)',
    },
    Table: {
      colorBgContainer: '#ffffff',
      headerBg: '#f8fafc',
      rowHoverBg: 'rgba(8, 145, 178, 0.06)',
      borderColor: 'rgba(15, 23, 42, 0.06)',
    },
    Modal: {
      contentBg: '#ffffff',
      headerBg: '#ffffff',
      titleColor: '#1e293b',
    },
    Input: {
      colorBgContainer: '#ffffff',
      activeBorderColor: '#0891b2',
      hoverBorderColor: 'rgba(8, 145, 178, 0.45)',
    },
    Tag: {
      defaultBg: 'rgba(8, 145, 178, 0.08)',
      defaultColor: '#0891b2',
    },
  },
}

/**
 * 按模式返回 Ant Design 主题配置
 * @param mode 暗色或浅色
 * @returns ThemeConfig
 */
export function getAntdTheme(mode: ThemeMode): ThemeConfig {
  return mode === 'dark' ? darkTheme : lightTheme
}

/** @deprecated 请使用 getAntdTheme('dark') */
export const hudTheme = darkTheme
