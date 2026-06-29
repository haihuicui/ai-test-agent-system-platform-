import { cn } from '@/lib/utils'
import { useBackendState } from '@/stores/state'
import { useEffect, useState } from 'react'
import StatusDialog from './StatusDialog'
import { useTranslation } from 'react-i18next'

const StatusIndicator = () => {
  const { t } = useTranslation()
  const health = useBackendState.use.health()
  const lastCheckTime = useBackendState.use.lastCheckTime()
  const status = useBackendState.use.status()
  const [animate, setAnimate] = useState(false)
  const [dialogOpen, setDialogOpen] = useState(false)

  // listen to health change
  useEffect(() => {
    const animTimer = setTimeout(() => setAnimate(true), 0)
    const timer = setTimeout(() => setAnimate(false), 300)
    return () => {
      clearTimeout(animTimer)
      clearTimeout(timer)
    }
  }, [lastCheckTime])

  return (
    <div className="fixed right-4 bottom-4 flex items-center gap-2 opacity-80 select-none dark:bg-black/30 dark:backdrop-blur-xl dark:rounded-lg dark:px-3 dark:py-2 dark:border dark:border-white/10">
      <div
        className="flex cursor-pointer items-center gap-2"
        onClick={() => setDialogOpen(true)}
      >
        <div
          className={cn(
            'h-3 w-3 rounded-full transition-all duration-300',
            'shadow-[0_0_8px_rgba(0,0,0,0.2)]',
            health ? 'bg-green-500' : 'bg-red-500',
            animate && 'scale-125',
            animate && health && 'shadow-[0_0_16px_rgba(34,197,94,0.6)]',
            animate && !health && 'shadow-[0_0_16px_rgba(239,68,68,0.6)]',
            health && 'dark:shadow-[0_0_14px_rgba(16,185,129,0.8)] dark:animate-neon-pulse',
            !health && 'dark:shadow-[0_0_14px_rgba(239,68,68,0.8)] dark:animate-neon-pulse'
          )}
        />
        <span className="text-muted-foreground text-xs font-medium">
          {health ? t('graphPanel.statusIndicator.connected') : t('graphPanel.statusIndicator.disconnected')}
        </span>
      </div>

      <StatusDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        status={status}
      />
    </div>
  )
}

export default StatusIndicator
