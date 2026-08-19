import { useState, useCallback } from 'react'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'
import Badge from '@/components/ui/Badge'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/Popover'
import { Command, CommandGroup, CommandItem, CommandList } from '@/components/ui/Command'
import { useSettingsStore } from '@/stores/settings'
import { sanitizeWorkspace, switchWorkspace } from '@/services/workspace'
import { toast } from 'sonner'

import { DatabaseIcon, ChevronsUpDownIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'

/**
 * Always-visible workspace switcher. The current workspace is shown on the
 * trigger button so users can tell at a glance which workspace uploads,
 * graph browsing and retrieval will hit. Free-text input (the server has no
 * "list workspaces" API) with a live preview of the server-side sanitization
 * result and a collision warning when a name collapses to all underscores.
 */
export default function WorkspaceSwitcher() {
  const { t } = useTranslation()
  const workspace = useSettingsStore.use.workspace()
  const workspaceHistory = useSettingsStore.use.workspaceHistory()
  const [open, setOpen] = useState(false)
  const [input, setInput] = useState('')

  const sanitized = sanitizeWorkspace(input)
  const trimmed = input.trim()
  // Show routing preview only when sanitization would change the input
  const showPreview = trimmed !== '' && sanitized !== trimmed
  // Non-ASCII names (e.g. Chinese) collapse entirely to underscores and
  // different names can collide on the same workspace — warn about it
  const allUnderscores = sanitized !== '' && /^_+$/.test(sanitized)

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
          <Command>
            <CommandList>
              <CommandGroup heading={t('workspace.history')}>
                <CommandItem onSelect={() => apply('')}>
                  <span className="truncate">{t('workspace.default')}</span>
                  {!workspace && (
                    <Badge variant="secondary" className="ml-auto">
                      {t('workspace.current')}
                    </Badge>
                  )}
                </CommandItem>
                {workspaceHistory.map((ws) => (
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
          <Button size="sm" className="w-full" onClick={() => apply(input)}>
            {t('workspace.apply')}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  )
}
