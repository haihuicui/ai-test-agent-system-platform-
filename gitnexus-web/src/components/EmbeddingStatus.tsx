// FIXME  MC8zOmFIVnBZMlhsdEpUbXRiZm92b2s2WmxSWFRRPT06M2QwYzcwYWM=

import { Brain, Loader2, Check, AlertCircle, Zap } from '@/lib/lucide-icons';
import { useAppState } from '../hooks/useAppState';
import { useState } from 'react';
import { WebGPUFallbackDialog } from './WebGPUFallbackDialog';
// FIXME  MS8zOmFIVnBZMlhsdEpUbXRiZm92b2s2WmxSWFRRPT06M2QwYzcwYWM=

/**
 * Embedding status indicator and trigger button
 * Shows in header when graph is loaded
 */
export const EmbeddingStatus = () => {
  const { embeddingStatus, embeddingProgress, startEmbeddings, graph, viewMode, serverBaseUrl } =
    useAppState();

  const [showFallbackDialog, setShowFallbackDialog] = useState(false);

  // Only show when exploring a loaded graph; hide in backend mode (no WASM DB)
  if (viewMode !== 'exploring' || !graph || serverBaseUrl) return null;

  const nodeCount = graph.nodes.length;

  const handleStartEmbeddings = async (_forceDevice?: 'webgpu' | 'wasm') => {
    try {
      await startEmbeddings();
    } catch (error: any) {
      // Check if it's a WebGPU not available error
      if (
        error?.name === 'WebGPUNotAvailableError' ||
        error?.message?.includes('WebGPU not available')
      ) {
        setShowFallbackDialog(true);
      } else {
        console.error('Embedding failed:', error);
      }
    }
  };

  const handleUseCPU = () => {
    setShowFallbackDialog(false);
    handleStartEmbeddings('wasm');
  };

  const handleSkipEmbeddings = () => {
    setShowFallbackDialog(false);
    // Just close - user can try again later if they want
  };

  // WebGPU fallback dialog - rendered independently of state
  const fallbackDialog = (
    <WebGPUFallbackDialog
      isOpen={showFallbackDialog}
      onClose={() => setShowFallbackDialog(false)}
      onUseCPU={handleUseCPU}
      onSkip={handleSkipEmbeddings}
      nodeCount={nodeCount}
    />
  );

  // Idle state - show button to start
  if (embeddingStatus === 'idle') {
    return (
      <>
        <div className="flex items-center gap-2">
          <button
            onClick={() => handleStartEmbeddings()}
            className="group flex items-center gap-2 rounded-lg border border-border-subtle bg-surface px-3 py-1.5 text-sm text-text-secondary transition-all hover:border-accent/50 hover:bg-hover hover:text-text-primary"
            title="生成嵌入向量以支持语义搜索"
          >
            <Brain className="h-4 w-4 text-node-interface transition-colors group-hover:text-accent" />
            <span className="hidden sm:inline">启用语义搜索</span>
            <Zap className="h-3 w-3 text-text-muted" />
          </button>
        </div>
        {fallbackDialog}
      </>
    );
  }

  // Loading model
  if (embeddingStatus === 'loading') {
    const downloadPercent = embeddingProgress?.percent ?? 0;
    return (
      <>
        <div className="flex items-center gap-2.5 rounded-lg border border-accent/30 bg-surface px-3 py-1.5 text-sm">
          <Loader2 className="h-4 w-4 animate-spin text-accent" />
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-text-secondary">加载 AI 模型...</span>
            <div className="h-1 w-24 overflow-hidden rounded-full bg-elevated">
              <div
                className="h-full rounded-full bg-gradient-to-r from-accent to-node-interface transition-all duration-300"
                style={{ width: `${downloadPercent}%` }}
              />
            </div>
          </div>
        </div>
        {fallbackDialog}
      </>
    );
  }

  // Embedding in progress
  if (embeddingStatus === 'embedding') {
    const processed = 0;
    const total = 0;
    const percent = embeddingProgress?.percent ?? 0;

    return (
      <div className="flex items-center gap-2.5 rounded-lg border border-node-function/30 bg-surface px-3 py-1.5 text-sm">
        <Loader2 className="h-4 w-4 animate-spin text-node-function" />
        <div className="flex flex-col gap-0.5">
          <span className="text-xs text-text-secondary">
            嵌入 {processed}/{total} 节点
          </span>
          <div className="h-1 w-24 overflow-hidden rounded-full bg-elevated">
            <div
              className="h-full rounded-full bg-gradient-to-r from-node-function to-accent transition-all duration-300"
              style={{ width: `${percent}%` }}
            />
          </div>
        </div>
      </div>
    );
  }

  // Indexing
  if (embeddingStatus === 'indexing') {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-node-interface/30 bg-surface px-3 py-1.5 text-sm text-text-secondary">
        <Loader2 className="h-4 w-4 animate-spin text-node-interface" />
        <span className="text-xs">创建向量索引...</span>
      </div>
    );
  }

  // Ready
  if (embeddingStatus === 'ready') {
    return (
      <div
        className="flex items-center gap-2 rounded-lg border border-node-function/30 bg-node-function/10 px-3 py-1.5 text-sm text-node-function"
        title="语义搜索已就绪！在 AI 对话中使用自然语言。"
      >
        <Check className="h-4 w-4" />
        <span className="text-xs font-medium">语义就绪</span>
      </div>
    );
  }

  // Error
  if (embeddingStatus === 'error') {
    return (
      <>
        <button
          onClick={() => handleStartEmbeddings()}
          className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm text-red-400 transition-colors hover:bg-red-500/20"
          title="嵌入失败。点击重试。"
        >
          <AlertCircle className="h-4 w-4" />
          <span className="text-xs">失败 - 重试</span>
        </button>
        {fallbackDialog}
      </>
    );
  }

  return null;
};
// @ts-expect-error  Mi8zOmFIVnBZMlhsdEpUbXRiZm92b2s2WmxSWFRRPT06M2QwYzcwYWM=
