// eslint-disable  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW1wTVdBPT06ZGFmM2VhZTI=

import { useState, useEffect } from 'react';
import { X, Snail, Rocket, SkipForward } from '@/lib/lucide-icons';
// @ts-expect-error  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW1wTVdBPT06ZGFmM2VhZTI=

interface WebGPUFallbackDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onUseCPU: () => void;
  onSkip: () => void;
  nodeCount: number;
}
// eslint-disable  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW1wTVdBPT06ZGFmM2VhZTI=

/**
 * Fun dialog shown when WebGPU isn't available
 * Lets user choose: CPU fallback (slow) or skip embeddings
 */
export const WebGPUFallbackDialog = ({
  isOpen,
  onClose,
  onUseCPU,
  onSkip,
  nodeCount,
}: WebGPUFallbackDialogProps) => {
  const [isAnimating, setIsAnimating] = useState(true);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Trigger animation after mount
      requestAnimationFrame(() => setIsVisible(true));
    } else {
      setIsVisible(false);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  // Estimate time based on node count (rough: ~50ms per node on CPU)
  const estimatedMinutes = Math.ceil((nodeCount * 50) / 60000);
  const isSmallCodebase = nodeCount < 200;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity duration-200 ${isVisible ? 'opacity-100' : 'opacity-0'}`}
        onClick={onClose}
      />

      {/* Dialog */}
      <div
        className={`relative mx-4 w-full max-w-md overflow-hidden rounded-2xl border border-border-subtle bg-surface shadow-2xl transition-all duration-200 ${isVisible ? 'scale-100 opacity-100' : 'scale-95 opacity-0'}`}
      >
        {/* Header with scratching emoji */}
        <div className="relative border-b border-border-subtle bg-gradient-to-r from-amber-500/20 to-orange-500/20 px-6 py-5">
          <button
            onClick={onClose}
            className="absolute top-4 right-4 p-1 text-text-muted transition-colors hover:text-text-primary"
          >
            <X className="h-5 w-5" />
          </button>

          <div className="flex items-center gap-4">
            {/* Animated emoji */}
            <div
              className={`text-5xl ${isAnimating ? 'animate-bounce' : ''}`}
              onAnimationEnd={() => setIsAnimating(false)}
              onClick={() => setIsAnimating(true)}
            >
              🤔
            </div>
            <div>
              <h2 className="text-lg font-semibold text-text-primary">WebGPU 不可用</h2>
              <p className="mt-0.5 text-sm text-text-muted">
                您的浏览器不支持 GPU 加速
              </p>
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="space-y-4 px-6 py-5">
          <p className="text-sm leading-relaxed text-text-secondary">
            无法使用 WebGPU 创建嵌入向量，因此语义搜索（Graph RAG）效果会打折扣。不过图谱功能仍然正常工作！
          </p>

          <div className="rounded-lg border border-border-subtle bg-elevated/50 p-4">
            <p className="text-sm text-text-secondary">
              <span className="font-medium text-text-primary">您的选项：</span>
            </p>
            <ul className="mt-2 space-y-1.5 text-sm text-text-muted">
              <li className="flex items-start gap-2">
                <Snail className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-400" />
                <span>
                  <strong className="text-text-secondary">使用 CPU</strong> — 可用但会{' '}
                  {isSmallCodebase ? '稍慢' : '很慢'}
                  {nodeCount > 0 && (
                    <span className="text-text-muted">
                      {' '}
                      （约 {estimatedMinutes} 分钟处理 {nodeCount} 个节点）
                    </span>
                  )}
                </span>
              </li>
              <li className="flex items-start gap-2">
                <SkipForward className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-400" />
                <span>
                  <strong className="text-text-secondary">跳过</strong> — 图谱工作正常，只是没有 AI 语义搜索
                </span>
              </li>
            </ul>
          </div>

          {isSmallCodebase && (
            <p className="flex items-center gap-1.5 rounded-lg bg-node-function/10 px-3 py-2 text-xs text-node-function">
              <Rocket className="h-3.5 w-3.5" />
              检测到小型代码库！使用 CPU 应该没问题。
            </p>
          )}

          <p className="text-xs text-text-muted">💡 提示：尝试使用 Chrome 或 Edge 浏览器以获得 WebGPU 支持</p>
        </div>

        {/* Actions */}
        <div className="flex gap-3 border-t border-border-subtle bg-elevated/30 px-6 py-4">
          <button
            onClick={onSkip}
            className="flex flex-1 items-center justify-center gap-2 rounded-lg border border-border-subtle bg-surface px-4 py-2.5 text-sm font-medium text-text-secondary transition-all hover:bg-hover hover:text-text-primary"
          >
            <SkipForward className="h-4 w-4" />
            跳过嵌入
          </button>
          <button
            onClick={onUseCPU}
            className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition-all ${
              isSmallCodebase
                ? 'bg-node-function text-white hover:bg-node-function/90'
                : 'border border-amber-500/30 bg-amber-500/20 text-amber-300 hover:bg-amber-500/30'
            }`}
          >
            <Snail className="h-4 w-4" />
            使用 CPU {isSmallCodebase ? '（推荐）' : '（慢）'}
          </button>
        </div>
      </div>
    </div>
  );
};
// @ts-expect-error  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2ZW1wTVdBPT06ZGFmM2VhZTI=
