import { useState, useCallback, useEffect } from 'react'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/Popover'
import { Command, CommandGroup, CommandItem, CommandList } from '@/components/ui/Command'
import { useSettingsStore } from '@/stores/settings'
import { sanitizeWorkspace, switchWorkspace } from '@/services/workspace'
import { getWorkspaces } from '@/api/lightrag'
import { toast } from 'sonner'

import { DatabaseIcon, ChevronsUpDownIcon, PlusIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/**
 * Always-visible workspace switcher. The current workspace is shown on the
 * trigger button so users can tell at a glance which workspace uploads,
 * graph browsing and retrieval will hit.
 *
 * The dropdown lists every workspace known to the server (registry populated
 * on lazy-load) merged with the browser-local history. Typing a name that
 * matches no existing workspace shows a "will be created on first use"
 * notice — workspaces are created lazily by the server, no separate create
 * step exists.
 */
export default function WorkspaceSwitcher() {
  const { t } = useTranslation()
  const workspace = useSettingsStore.use.workspace()
  const workspaceHistory = useSettingsStore.use.workspaceHistory()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')
  const [serverWorkspaces, setServerWorkspaces] = useState<string[]>([])

  // Fetch the server-side workspace registry each time the popover opens, so
  // the list reflects workspaces created from other browsers / sessions.
  useEffect(() => {
    if (!open) return
    let cancelled = false
    getWorkspaces()
      .then((list) => {
        if (!cancelled) setServerWorkspaces(list)
      })
      .catch(() => {
        // Registry unavailable (older server) — fall back to local history only
      })
    return () => {
      cancelled = true
    }
  }, [open])

  // Server registry first (source of truth), then local history entries the
  // server doesn't know about (e.g. created before the registry existed)
  const knownWorkspaces = [
    ...serverWorkspaces,
    ...workspaceHistory.filter((ws) => !serverWorkspaces.includes(ws))
  ]

  const sanitized = sanitizeWorkspace(input)
  const trimmed = input.trim()
  // Show routing preview only when sanitization would change the input
  const showPreview = trimmed !== '' && sanitized !== trimmed
  // Non-ASCII names (e.g. Chinese) collapse entirely to underscores and
  // different names can collide on the same workspace — warn about it
  const allUnderscores = sanitized !== '' && /^_+$/.test(sanitized)
  // A non-empty sanitized name unknown to both lists will be created lazily
  const isNewWorkspace =
    sanitized !== '' && !knownWorkspaces.includes(sanitized)

  const apply = useCallback(
    (raw: string) => {
      const next = sanitizeWorkspace(raw)
      switchWorkspace(raw)
      setOpen(false)
      setInput('')
      toast.success(
        next
          ? t('workspace.switched', { workspace: next })
          : t('workspace.switchedToDefault')
      )
    },
    [t]
  )

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start"
          aria-label={t('workspace.label')}
        >
          <DatabaseIcon className="mr-2 shrink-0" />
          <span className="truncate">{workspace || t('workspace.default')}</span>
          <ChevronsUpDownIcon className="ml-auto size-3 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent side="top" align="start" className="w-64 p-2">
        <div className="flex flex-col gap-2">
          <Input
            value={input}
            placeholder={t('workspace.inputPlaceholder')}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault()
                apply(input)
              }
            }}
          />
          {showPreview && (
            <p className="text-muted-foreground px-1 text-xs">
              {t('workspace.sanitizedPreview', {
                sanitized: sanitized || t('workspace.default')
              })}
            </p>
          )}
          {allUnderscores && (
            <p className="px-1 text-xs text-amber-500">
              {t('workspace.sanitizeCollisionWarning')}
            </p>
          )}
          {isNewWorkspace && (
            <p className="text-muted-foreground flex items-center gap-1 px-1 text-xs">
              <PlusIcon className="size-3 shrink-0" />
              {t('workspace.createNotice', { workspace: sanitized })}
            </p>
          )}
          <Command>
            <CommandList>
              <CommandGroup heading={t('workspace.existing')}>
                <CommandItem onSelect={() => apply('')}>
                  <span className="truncate">{t('workspace.default')}</span>
                  {!workspace && (
                    <Badge variant="secondary" className="ml-auto">
                      {t('workspace.current')}
                    </Badge>
                  )}
                </CommandItem>
                {knownWorkspaces.map((ws) => (
                  <CommandItem key={ws} onSelect={() => apply(ws)}>
                    <span className="truncate">{ws}</span>
                    {workspace === ws && (
                      <Badge variant="secondary" className="ml-auto">
                        {t('workspace.current')}
                      </Badge>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            </CommandList>
          </Command>
          <Button
            size="sm"
            className="w-full"
            disabled={trimmed === ''}
            onClick={() => apply(input)}
          >
            {isNewWorkspace ? t('workspace.createAndSwitch') : t('workspace.apply')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
