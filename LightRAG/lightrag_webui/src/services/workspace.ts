import { useSettingsStore } from '@/stores/settings'
import { useGraphStore } from '@/stores/graph'
import { useBackendState } from '@/stores/state'
import { abortAllDocumentsPaginated } from '@/api/lightrag'

/**
 * Sanitize a workspace identifier with the exact same rule as the
 * server-side _sanitize_workspace_header (see
 * local-patches/workspace-request-routing.patch): trim, then replace every
 * character outside [a-zA-Z0-9_] with '_'. Empty result = default workspace.
 */
export const sanitizeWorkspace = (value: string): string =>
  (value ?? '').trim().replace(/[^a-zA-Z0-9_]/g, '_')

/**
 * Single entry point for switching the active workspace.
 *
 * Invalidation chain, in order:
 * 1) persist the new value — every new request (axios interceptor and
 *    streaming headers) picks up the new header automatically
 * 2) abort in-flight paginated document requests — responses from the old
 *    workspace must never land in the new list
 * 3) graph store reset + version bump — fetch signature changes so the graph
 *    is re-queried under the new workspace
 * 4) clear retrieval history (an in-flight stream is blocked from writing
 *    back by the workspace guard in RetrievalView)
 * 5) refresh the graph label dropdown (labels are per-workspace)
 * 6) re-check /health under the new workspace (pipelineBusy/pipelineActive
 *    drive the document page polling cadence)
 *
 * DocumentManager remounts via key={workspace} in App.tsx and refetches on
 * mount, so it is intentionally not touched here.
 */
export const switchWorkspace = (rawInput: string): void => {
  const next = sanitizeWorkspace(rawInput)
  const settings = useSettingsStore.getState()
  if (next === settings.workspace) return

  settings.setWorkspace(next)
  if (next) settings.addWorkspaceToHistory(next)

  abortAllDocumentsPaginated()

  const graph = useGraphStore.getState()
  graph.reset()
  graph.setGraphDataFetchAttempted(false)
  graph.setLabelsFetchAttempted(false)
  graph.setLastSuccessfulQueryLabel('')
  graph.incrementGraphDataVersion()

  settings.setRetrievalHistory([])
  settings.triggerSearchLabelDropdownRefresh()

  useBackendState.getState().check().catch(() => undefined)
}
