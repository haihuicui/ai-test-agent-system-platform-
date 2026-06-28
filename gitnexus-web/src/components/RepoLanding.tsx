// @ts-expect-error  MC80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pReWR3PT06YTc4YTRhZTM=

/**
 * RepoLanding
 *
 * Unified landing screen shown when the backend is connected and at least one
 * repository is indexed. Displays pre-indexed repos as selectable cards, plus
 * an "Analyze a New Repository" section powered by RepoAnalyzer.
 *
 * Rendering context:
 *   DropZone (Crossfade, phase="landing")
 *     └─ RepoLanding
 *          ├─ RepoCard (× N)
 *          └─ RepoAnalyzer (variant="onboarding")
 */

import { Sparkles, ArrowRight, GitBranch, FileCode, Layers } from '@/lib/lucide-icons';
import { RepoAnalyzer } from './RepoAnalyzer';
import type { BackendRepo } from '../services/backend-client';

// ── Helpers ──────────────────────────────────────────────────────────────────
// eslint-disable  MS80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pReWR3PT06YTc4YTRhZTM=

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  if (diffMins < 1) return '刚刚';
  if (diffMins < 60) return `${diffMins}分钟前`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}小时前`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays}天前`;
  return date.toLocaleDateString('zh-CN');
}

// ── Repo card ────────────────────────────────────────────────────────────────

function RepoCard({ repo, onClick }: { repo: BackendRepo; onClick: () => void }) {
  const stats = repo.stats;

  return (
    <button
      onClick={onClick}
      data-testid="landing-repo-card"
      className="group w-full cursor-pointer rounded-xl border border-border-default bg-elevated p-4 text-left transition-all duration-200 hover:border-accent/40 hover:bg-hover hover:shadow-glow-soft"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <GitBranch className="h-4 w-4 shrink-0 text-accent" />
            <h3 className="truncate text-sm font-semibold text-text-primary transition-colors group-hover:text-accent">
              {repo.name}
            </h3>
          </div>
          {repo.indexedAt && (
            <p className="mt-1 pl-6 text-xs text-text-muted">
              Indexed {formatRelativeTime(repo.indexedAt)}
            </p>
          )}
        </div>
        <ArrowRight className="h-4 w-4 shrink-0 text-text-muted opacity-0 transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-accent group-hover:opacity-100" />
      </div>

      {stats && (stats.files || stats.nodes) && (
        <div className="mt-3 flex flex-wrap gap-2 pl-6">
          {stats.files != null && (
            <span className="inline-flex items-center gap-1 rounded-md bg-void px-2 py-0.5 text-[11px] text-text-muted">
              <FileCode className="h-3 w-3" /> {stats.files.toLocaleString()} 文件
            </span>
          )}
          {stats.nodes != null && (
            <span className="inline-flex items-center gap-1 rounded-md bg-void px-2 py-0.5 text-[11px] text-text-muted">
              <Layers className="h-3 w-3" /> {stats.nodes.toLocaleString()} 符号
            </span>
          )}
          {stats.processes != null && stats.processes > 0 && (
            <span className="inline-flex items-center gap-1 rounded-md bg-void px-2 py-0.5 text-[11px] text-text-muted">
              <Sparkles className="h-3 w-3" /> {stats.processes} 流程
            </span>
          )}
        </div>
      )}
    </button>
  );
}
// NOTE  Mi80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pReWR3PT06YTc4YTRhZTM=

// ── RepoLanding ──────────────────────────────────────────────────────────────
// eslint-disable  My80OmFIVnBZMlhsdEpUbXRiZm92b2s2U3pReWR3PT06YTc4YTRhZTM=

interface RepoLandingProps {
  repos: BackendRepo[];
  onSelectRepo: (repoName: string) => void;
  onAnalyzeComplete: (repoName: string) => void;
}

export const RepoLanding = ({ repos, onSelectRepo, onAnalyzeComplete }: RepoLandingProps) => {
  return (
    <div className="relative animate-fade-in overflow-hidden rounded-3xl border border-border-default bg-surface p-7">
      {/* Ambient glows — mirrors OnboardingGuide aesthetic */}
      <div className="pointer-events-none absolute -top-28 -right-28 h-72 w-72 rounded-full bg-accent/6 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-24 h-56 w-56 rounded-full bg-node-function/6 blur-3xl" />

      {/* Header */}
      <div className="relative mb-6">
        <div className="text-center">
          <div className="mb-2 inline-flex items-center gap-1.5">
            <Sparkles className="h-3.5 w-3.5 text-accent/70" />
            <span className="text-[11px] font-medium tracking-widest text-accent/80 uppercase">
              GitNexus
            </span>
          </div>

          <h2 className="text-lg leading-snug font-semibold text-text-primary">
            选择仓库
          </h2>
          <p className="mx-auto mt-1.5 max-w-xs text-sm leading-relaxed text-text-secondary">
            选择一个已索引的仓库进行探索，或分析新仓库。
          </p>
        </div>
      </div>

      {/* Repo list */}
      <div className="relative mb-5 space-y-2">
        {repos.map((repo) => (
          <RepoCard key={repo.name} repo={repo} onClick={() => onSelectRepo(repo.name)} />
        ))}
      </div>

      {/* Divider */}
      <div className="mb-5 flex items-center gap-3">
        <div className="h-px flex-1 bg-border-subtle" />
        <span className="text-[11px] tracking-widest text-text-muted uppercase">
          或分析新仓库
        </span>
        <div className="h-px flex-1 bg-border-subtle" />
      </div>

      {/* Analyzer form */}
      <div className="relative">
        <RepoAnalyzer variant="onboarding" onComplete={onAnalyzeComplete} />
      </div>

      {/* Footer hint */}
      <p className="mt-5 text-center text-[11px] leading-relaxed text-text-muted">
        公共和私有仓库 &middot; 由服务器本地克隆 &middot; 数据不会离开您的机器
      </p>
    </div>
  );
};
