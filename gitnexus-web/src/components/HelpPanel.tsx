
import React, { useState } from 'react';
import { X, GitBranch, Search, Filter, Zap, Keyboard, BarChart2, HelpCircle } from 'lucide-react';
// @ts-expect-error  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmtZeFVnPT06ZGJiZTVkMTM=

interface HelpPanelProps {
  isOpen: boolean;
  onClose: () => void;
  nodeCount: number;
  edgeCount: number;
}

type TabId = 'overview' | 'graph' | 'search' | 'ai' | 'shortcuts' | 'status';
// TODO  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmtZeFVnPT06ZGJiZTVkMTM=

interface Tab {
  id: TabId;
  label: string;
  icon: React.ReactNode;
}

const tabs: Tab[] = [
  { id: 'overview', label: '概览', icon: <HelpCircle className="h-4 w-4" /> },
  { id: 'graph', label: '图谱与节点', icon: <GitBranch className="h-4 w-4" /> },
  { id: 'search', label: '搜索与筛选', icon: <Search className="h-4 w-4" /> },
  { id: 'ai', label: '智能问答', icon: <Zap className="h-4 w-4" /> },
  { id: 'shortcuts', label: '快捷键', icon: <Keyboard className="h-4 w-4" /> },
  { id: 'status', label: '状态栏', icon: <BarChart2 className="h-4 w-4" /> },
];

const shortcuts = [
  { label: '搜索节点', mac: '⌘ K', win: 'Ctrl K' },
  { label: '取消选择 / 关闭', mac: 'Esc', win: 'Esc' },
];

const nodeColors = [
  { color: '#10b981', label: 'Function', desc: '函数声明' },
  { color: '#3b82f6', label: 'File', desc: '源文件' },
  { color: '#f59e0b', label: 'Class', desc: '类声明' },
  { color: '#14b8a6', label: 'Method', desc: '类方法' },
  { color: '#ec4899', label: 'Interface', desc: 'TypeScript 接口' },
  { color: '#6366f1', label: 'Folder', desc: '目录节点' },
];
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmtZeFVnPT06ZGJiZTVkMTM=

const getStatusItems = (nodeCount: number, edgeCount: number) => [
  {
    badge: (
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: '#34d399',
          display: 'inline-block',
          flexShrink: 0,
        }}
      />
    ),
    title: 'Ready',
    desc: 'Graph is fully loaded and interactive',
  },
  {
    badge: (
      <span style={{ fontSize: 12, fontWeight: 500, color: '#a78bfa', flexShrink: 0 }}>
        {nodeCount}
      </span>
    ),
    title: 'Nodes count',
    desc: 'Total files and symbols in the graph',
  },
  {
    badge: (
      <span style={{ fontSize: 12, fontWeight: 500, color: '#60a5fa', flexShrink: 0 }}>
        {edgeCount}
      </span>
    ),
    title: 'Edges count',
    desc: 'Import / dependency connections',
  },
  {
    badge: (
      <span
        style={{
          fontSize: 11,
          fontWeight: 500,
          color: '#34d399',
          flexShrink: 0,
          whiteSpace: 'nowrap',
        }}
      >
        Semantic Ready
      </span>
    ),
    title: 'AI index status',
    desc: 'Repo is fully indexed for AI queries',
  },
  // { badge: <span style={{ fontSize: 11, fontWeight: 500, color: '#9ca3af', flexShrink: 0 }}>typescript</span>, title: 'Language', desc: 'Primary language detected in the repo' },
];

const kbdStyle: React.CSSProperties = {
  fontSize: 11,
  background: 'rgba(255,255,255,0.08)',
  borderRadius: 4,
  padding: '2px 8px',
  color: 'var(--color-text-primary)',
  fontFamily: 'monospace',
  border: '0.5px solid rgba(255,255,255,0.12)',
  whiteSpace: 'nowrap',
};
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2YmtZeFVnPT06ZGJiZTVkMTM=

const kbdWinStyle: React.CSSProperties = {
  ...kbdStyle,
  color: '#93c5fd',
};

function TabContent({
  active,
  nodeCount,
  edgeCount,
}: {
  active: TabId;
  nodeCount: number;
  edgeCount: number;
}) {
  if (active === 'overview')
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <p
          style={{
            fontSize: 11,
            color: '#6b7280',
            margin: '0 0 4px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          入门指南
        </p>

        <div
          style={{
            background: 'rgba(255,255,255,0.04)',
            borderRadius: 10,
            padding: '12px 14px',
            borderLeft: '2px solid #a78bfa',
          }}
        >
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
            什么是智能代码分析平台？
          </p>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            一个交互式代码库图谱浏览器。每个文件、函数和导入都成为一个节点，您可以直观地探索、查询和导航。
          </p>
        </div>

        <div
          style={{
            background: 'rgba(255,255,255,0.04)',
            borderRadius: 10,
            padding: '12px 14px',
            borderLeft: '2px solid #34d399',
          }}
        >
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
            当前仓库
          </p>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            已加载：<span style={{ color: '#a78bfa', fontFamily: 'monospace' }}></span> {nodeCount}{' '}
            节点 · {edgeCount} 边
          </p>
        </div>

        <div
          style={{
            background: 'rgba(255,255,255,0.04)',
            borderRadius: 10,
            padding: '12px 14px',
            borderLeft: '2px solid #60a5fa',
          }}
        >
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
            三种探索方式
          </p>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            <strong style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>1.</strong> 点击节点查看详情
            <br />
            <strong style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>2.</strong> 按名称或类型搜索
            <br />
            <strong style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>3.</strong> 向智能问答提问自然语言问题
          </p>
        </div>

        <div
          style={{
            background: 'rgba(255,255,255,0.04)',
            borderRadius: 10,
            padding: '12px 14px',
            borderLeft: '2px solid #fbbf24',
          }}
        >
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 4px' }}>
            导航
          </p>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            · 滚动缩放 <br />
            · 点击拖拽平移 <br />· 双击节点聚焦其子图
          </p>
        </div>
      </div>
    );

  if (active === 'graph')
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p
          style={{
            fontSize: 11,
            color: '#6b7280',
            margin: '0 0 4px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          节点颜色图例
        </p>

        {nodeColors.map(({ color, label, desc }) => (
          <div key={label} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
            <span
              style={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                background: color,
                flexShrink: 0,
                marginTop: 2,
              }}
            />
            <div>
              <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 2px' }}>
                {label} 节点
              </p>
              <p style={{ fontSize: 12, color: '#9ca3af', margin: 0 }}>{desc}</p>
            </div>
          </div>
        ))}

        <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.08)', margin: '4px 0' }} />

        <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
          节点 <strong style={{ color: 'var(--color-text-primary)', fontWeight: 500 }}>大小</strong>反映连接数 — 
          越大的节点被越多文件依赖。边从导入者指向被导入者。
        </p>

        <div
          style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '10px 14px' }}
        >
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            点击任意节点打开详情面板 — 显示导入、导出和反向依赖。
          </p>
        </div>
      </div>
    );

  if (active === 'search')
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <p
          style={{
            fontSize: 11,
            color: '#6b7280',
            margin: '0 0 4px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          搜索与筛选
        </p>

        <div
          style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '12px 14px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <kbd style={kbdStyle}>⌘K</kbd>/<kbd style={kbdStyle}>Ctrl K</kbd>
            <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
              搜索节点
            </p>
          </div>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            按文件名、函数名或导入路径搜索。匹配的节点将在图谱中高亮显示。
          </p>
        </div>

        <div
          style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '12px 14px' }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <Filter style={{ width: 14, height: 14, color: '#a78bfa', flexShrink: 0 }} />
            <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)', margin: 0 }}>
              筛选面板
            </p>
          </div>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            使用左侧边栏的筛选图标来隔离特定节点类型、隐藏叶子节点或聚焦选定根节点的深度范围。
          </p>
        </div>

        <div
          style={{ background: 'rgba(255,255,255,0.04)', borderRadius: 10, padding: '12px 14px' }}
        >
          <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 6px' }}>
            搜索语法
          </p>
          {[
            { query: 'auth', hint: '按名称片段匹配' },
            { query: './utils/', hint: '按路径前缀匹配' },
            { query: 'type:config', hint: '按节点类型筛选' },
          ].map(({ query, hint }) => (
            <div
              key={query}
              style={{ display: 'flex', alignItems: 'baseline', gap: 8, marginBottom: 4 }}
            >
              <code
                style={{
                  fontSize: 11,
                  color: '#a78bfa',
                  background: 'rgba(167,139,250,0.1)',
                  borderRadius: 4,
                  padding: '1px 6px',
                  fontFamily: 'monospace',
                  flexShrink: 0,
                }}
              >
                {query}
              </code>
              <span style={{ fontSize: 12, color: '#6b7280' }}>{hint}</span>
            </div>
          ))}
        </div>
      </div>
    );

  if (active === 'ai')
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <p
          style={{
            fontSize: 11,
            color: '#6b7280',
            margin: '0 0 4px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          智能问答
        </p>

        <div
          style={{
            background: 'rgba(167,139,250,0.08)',
            border: '0.5px solid rgba(167,139,250,0.25)',
            borderRadius: 10,
            padding: '12px 14px',
          }}
        >
          <p style={{ fontSize: 12, fontWeight: 500, color: '#a78bfa', margin: '0 0 4px' }}>
            ✓ 语义就绪
          </p>
          <p style={{ fontSize: 12, color: '#9ca3af', margin: 0, lineHeight: 1.6 }}>
            您的仓库已索引并支持语义查询。智能问答理解代码结构和关系，而不仅仅是文件名。
          </p>
        </div>

        <p style={{ fontSize: 12, color: '#9ca3af', margin: '4px 0 2px' }}>尝试提问：</p>
        {[
          '"哪些文件依赖 auth 模块？"',
          '"在此仓库中查找循环依赖"',
          '"哪些组件连接最多？"',
          '"显示所有导入 useEffect 的文件"',
        ].map((q) => (
          <div
            key={q}
            style={{
              background: 'rgba(255,255,255,0.04)',
              borderRadius: 8,
              padding: '8px 12px',
              fontSize: 12,
              color: 'var(--color-text-primary)',
              fontStyle: 'italic',
            }}
          >
            {q}
          </div>
        ))}

        <div style={{ borderTop: '0.5px solid rgba(255,255,255,0.08)', margin: '4px 0' }} />

        <p style={{ fontSize: 12, color: '#6b7280', margin: 0, lineHeight: 1.6 }}>
          通过右上角的 <span style={{ color: 'var(--color-text-primary)' }}>智能问答</span> 按钮打开对话框。
        </p>
      </div>
    );

  if (active === 'shortcuts')
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
        {/* Column headers */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 80px 88px',
            gap: 8,
            padding: '0 0 8px',
            borderBottom: '0.5px solid rgba(255,255,255,0.08)',
            marginBottom: 4,
          }}
        >
          <span
            style={{
              fontSize: 11,
              color: '#6b7280',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}
          >
            操作
          </span>
          <span
            style={{
              fontSize: 11,
              color: '#6b7280',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              textAlign: 'center',
            }}
          >
            Mac
          </span>
          <span
            style={{
              fontSize: 11,
              color: '#93c5fd',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
              textAlign: 'center',
            }}
          >
            Windows
          </span>
        </div>

        {shortcuts.map(({ label, mac, win }, i) => (
          <div
            key={label}
            style={{
              display: 'grid',
              gridTemplateColumns: '1fr 80px 88px',
              gap: 8,
              alignItems: 'center',
              padding: '8px 0',
              borderBottom:
                i < shortcuts.length - 1 ? '0.5px solid rgba(255,255,255,0.05)' : 'none',
            }}
          >
            <span style={{ fontSize: 12, color: '#9ca3af' }}>{label}</span>
            <span style={{ display: 'flex', justifyContent: 'center' }}>
              <kbd style={kbdStyle}>{mac}</kbd>
            </span>
            <span style={{ display: 'flex', justifyContent: 'center' }}>
              <kbd style={kbdWinStyle}>{win}</kbd>
            </span>
          </div>
        ))}
      </div>
    );

  if (active === 'status')
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <p
          style={{
            fontSize: 11,
            color: '#6b7280',
            margin: '0 0 4px',
            textTransform: 'uppercase',
            letterSpacing: '0.08em',
          }}
        >
          状态栏说明
        </p>
        {getStatusItems(nodeCount, edgeCount).map(({ badge, title, desc }) => (
          <div
            key={title}
            style={{
              background: 'rgba(255,255,255,0.04)',
              borderRadius: 10,
              padding: '10px 14px',
              display: 'flex',
              gap: 12,
              alignItems: 'center',
            }}
          >
            {badge}
            <div>
              <p style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-text-primary)', margin: '0 0 2px' }}>
                {title}
              </p>
              <p style={{ fontSize: 12, color: '#9ca3af', margin: 0 }}>{desc}</p>
            </div>
          </div>
        ))}
      </div>
    );

  return null;
}

export const HelpPanel = ({ isOpen, onClose, nodeCount, edgeCount }: HelpPanelProps) => {
  const [active, setActive] = useState<TabId>('overview');

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {/* Backdrop */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(0,0,0,0.6)',
          backdropFilter: 'blur(4px)',
        }}
        onClick={onClose}
      />

      {/* Panel */}
      <div
        style={{
          position: 'relative',
          background: '#12121a',
          border: '0.5px solid rgba(255,255,255,0.12)',
          borderRadius: 16,
          boxShadow: '0 25px 60px rgba(0,0,0,0.7)',
          width: '100%',
          maxWidth: 680,
          margin: '0 16px',
          height: '60vh',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          fontFamily: 'var(--font-mono, monospace)',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            borderBottom: '0.5px solid rgba(255,255,255,0.08)',
            background: 'rgba(255,255,255,0.02)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div
              style={{
                width: 40,
                height: 40,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'rgba(167,139,250,0.15)',
                borderRadius: 12,
              }}
            >
              <HelpCircle style={{ width: 20, height: 20, color: '#a78bfa' }} />
            </div>
            <div>
              <h2 style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-text-primary)', margin: 0 }}>
                帮助与参考
              </h2>
              <p style={{ fontSize: 12, color: '#6b7280', margin: 0 }}>智能代码分析平台 — 图谱浏览器</p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              padding: 8,
              color: '#6b7280',
              background: 'transparent',
              border: 'none',
              borderRadius: 8,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'color 0.15s',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--color-text-primary)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = '#6b7280')}
          >
            <X style={{ width: 20, height: 20 }} />
          </button>
        </div>

        {/* Body: sidebar + content */}
        <div
          style={{ display: 'grid', gridTemplateColumns: '168px 1fr', flex: 1, overflow: 'hidden' }}
        >
          {/* Sidebar nav */}
          <div
            style={{
              borderRight: '0.5px solid rgba(255,255,255,0.08)',
              padding: '12px 8px',
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
            }}
          >
            {tabs.map(({ id, label, icon }) => {
              const isActive = active === id;
              return (
                <button
                  key={id}
                  onClick={() => setActive(id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    textAlign: 'left',
                    background: isActive ? 'rgba(167,139,250,0.12)' : 'transparent',
                    border: 'none',
                    borderRadius: 8,
                    padding: '8px 10px',
                    fontSize: 12,
                    fontFamily: 'inherit',
                    color: isActive ? '#a78bfa' : '#9ca3af',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    width: '100%',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.color = 'var(--color-text-primary)';
                      e.currentTarget.style.background = 'rgba(255,255,255,0.04)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.color = '#9ca3af';
                      e.currentTarget.style.background = 'transparent';
                    }
                  }}
                >
                  <span
                    style={{
                      color: isActive ? '#a78bfa' : '#6b7280',
                      display: 'flex',
                      flexShrink: 0,
                    }}
                  >
                    {icon}
                  </span>
                  {label}
                </button>
              );
            })}
          </div>

          {/* Content pane */}
          <div style={{ padding: '20px', overflowY: 'auto' }}>
            <TabContent active={active} nodeCount={nodeCount} edgeCount={edgeCount} />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '10px 20px',
            borderTop: '0.5px solid rgba(255,255,255,0.08)',
            background: 'rgba(255,255,255,0.01)',
          }}
        >
          <span style={{ fontSize: 11, color: '#4b5563' }}>
            智能代码分析平台 — 开源代码库图谱浏览器
          </span>
        </div>
      </div>
    </div>
  );
};
