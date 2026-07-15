import { useState, useCallback } from 'react'
import Button from '@/components/ui/Button'
import { ScrollArea } from '@/components/ui/ScrollArea'
import { Dialog, DialogContent, DialogTrigger } from '@/components/ui/Dialog'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip'
import { SiteInfo, webuiPrefix } from '@/lib/constants'
import AppSettings from '@/components/AppSettings'
import { useSettingsStore } from '@/stores/settings'
import { useAuthStore } from '@/stores/state'
import { navigationService } from '@/services/navigation'
import { cn } from '@/lib/utils'
import { useTranslation } from 'react-i18next'
import {
  FileTextIcon,
  NetworkIcon,
  SearchIcon,
  MenuIcon,
  LogOutIcon
} from 'lucide-react'
import LogoIcon from '@/components/icons/LogoIcon'

const navItems = [
  { id: 'documents', titleKey: 'header.documents', icon: FileTextIcon },
  { id: 'knowledge-graph', titleKey: 'header.knowledgeGraph', icon: NetworkIcon },
  { id: 'retrieval', titleKey: 'header.retrieval', icon: SearchIcon }
] as const

type Tab = (typeof navItems)[number]['id']

function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useTranslation()
  const currentTab = useSettingsStore.use.currentTab()
  const setCurrentTab = useSettingsStore.use.setCurrentTab()
  const { isGuestMode, username } = useAuthStore()

  const handleLogout = useCallback(() => {
    navigationService.navigateToLogin()
  }, [])

  const handleNav = useCallback(
    (id: Tab) => {
      setCurrentTab(id)
      onNavigate?.()
    },
    [setCurrentTab, onNavigate]
  )

  return (
    <div className="flex h-full w-60 flex-col border-r bg-card dark:bg-black/50 dark:backdrop-blur-xl dark:border-white/10">
      {/* Logo */}
      <div className="flex h-16 flex-col justify-center border-b px-4 dark:border-white/10">
        <a href={webuiPrefix} className="flex items-center gap-2">
          <LogoIcon size={26} />
          <span className="truncate font-semibold tech-font tracking-cyber dark:text-cyan-50 dark:drop-shadow-[0_0_8px_rgba(6,182,212,0.5)]">{SiteInfo.name}</span>
        </a>
        <span className="truncate uppercase-tracked mt-0.5">
          {t('header.tagline')}
        </span>
      </div>

      {/* Navigation */}
      <ScrollArea className="flex-1 px-3 py-2">
        <nav className="flex flex-col gap-1" aria-label={t('header.documents')}>
          {navItems.map((item) => {
            const isActive = currentTab === item.id
            const Icon = item.icon
            return (
              <Button
                key={item.id}
                variant={isActive ? 'secondary' : 'ghost'}
                className={cn(
                  'w-full justify-start relative overflow-hidden transition-all duration-200',
                  isActive && 'font-medium dark:bg-cyan-950/20 dark:text-cyan-100',
                  isActive && 'dark:before:absolute dark:before:left-0 dark:before:top-1/2 dark:before:-translate-y-1/2 dark:before:h-6 dark:before:w-[3px] dark:before:rounded-r-sm dark:before:bg-cyan-400 dark:before:shadow-[0_0_12px_rgba(6,182,212,0.8)] dark:before:animate-pulse',
                  !isActive && 'dark:hover:bg-white/5 dark:hover:text-cyan-200 dark:hover:translate-x-1 dark:hover:drop-shadow-[0_0_6px_rgba(6,182,212,0.5)]'
                )}
                onClick={() => handleNav(item.id)}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon className="mr-2 size-4 shrink-0" aria-hidden="true" />
                {t(item.titleKey)}
              </Button>
            )
          })}
        </nav>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t p-3 dark:border-white/10 dark:bg-black/30">
        <div className="flex items-center">
          <AppSettings />
        </div>

        {!isGuestMode && (
          <div className="mt-2">
            <Button
              variant="ghost"
              className="w-full justify-start dark:hover:bg-white/5 dark:hover:text-cyan-200"
              onClick={handleLogout}
              tooltip={username ? `${t('header.logout')} (${username})` : t('header.logout')}
              side="top"
            >
              <LogOutIcon className="mr-2 size-4 shrink-0" aria-hidden="true" />
              <span className="truncate">{t('header.logout')}</span>
              {username && <span className="ml-auto truncate text-xs text-muted-foreground">({username})</span>}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Sidebar() {
  const [mobileOpen, setMobileOpen] = useState(false)

  const closeMobile = useCallback(() => setMobileOpen(false), [])

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="hidden md:flex dark:bg-black/50 dark:backdrop-blur-xl dark:border-white/10" aria-label="Main navigation">
        <SidebarContent />
      </aside>

      {/* Mobile hamburger + drawer */}
      <div className="md:hidden">
        <Dialog open={mobileOpen} onOpenChange={setMobileOpen}>
          <DialogTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="fixed top-3 left-3 z-50 dark:bg-black/50 dark:backdrop-blur-xl dark:border-white/10"
              aria-label="Open navigation menu"
            >
              <MenuIcon className="size-5" aria-hidden="true" />
            </Button>
          </DialogTrigger>
          <DialogContent
            className={cn(
              'fixed inset-y-0 left-0 h-full w-60 max-w-none translate-x-0 translate-y-0 rounded-none border-0 p-0 shadow-xl',
              'dark:bg-black/50 dark:backdrop-blur-xl dark:border-white/10',
              '[&>button:last-child]:hidden'
            )}
            aria-describedby={undefined}
          >
            <SidebarContent onNavigate={closeMobile} />
          </DialogContent>
        </Dialog>
      </div>
    </>
  )
}
