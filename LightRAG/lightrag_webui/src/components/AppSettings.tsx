import { useState, useCallback } from 'react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger
} from '@/components/ui/Dialog'
import Button from '@/components/ui/Button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/Select'
import { useSettingsStore } from '@/stores/settings'
import { PaletteIcon } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { cn } from '@/lib/utils'

interface AppSettingsProps {
  className?: string
}

export default function AppSettings({ className }: AppSettingsProps) {
  const [opened, setOpened] = useState<boolean>(false)
  const { t } = useTranslation()

  const language = useSettingsStore.use.language()
  const setLanguage = useSettingsStore.use.setLanguage()

  const theme = useSettingsStore.use.theme()
  const setTheme = useSettingsStore.use.setTheme()

  const handleLanguageChange = useCallback(
    (value: string) => {
      setLanguage(value as 'en' | 'zh' | 'fr' | 'ar' | 'zh_TW' | 'ru' | 'ja' | 'de' | 'uk' | 'ko' | 'vi')
    },
    [setLanguage]
  )

  const handleThemeChange = useCallback(
    (value: string) => {
      setTheme(value as 'light' | 'dark' | 'system')
    },
    [setTheme]
  )

  return (
    <Dialog open={opened} onOpenChange={setOpened}>
      <DialogTrigger asChild>
        <Button variant="ghost" size="icon" className={cn('h-9 w-9 dark:hover:bg-white/5 dark:hover:text-cyan-200 dark:hover:shadow-[0_0_10px_rgba(6,182,212,0.3)] transition-all duration-200', className)}>
          <PaletteIcon className="h-5 w-5" />
        </Button>
      </DialogTrigger>
      <DialogContent className="w-80 dark:glass-card dark:border-white/10">
        <DialogHeader>
          <DialogTitle className="dark:text-cyan-100">{t('settings.title')}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-4 py-4">
          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium dark:text-cyan-100 uppercase-tracked">{t('settings.language')}</label>
            <Select value={language} onValueChange={handleLanguageChange}>
              <SelectTrigger className="dark:bg-black/30 dark:border-white/10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="dark:bg-black/80 dark:backdrop-blur-xl dark:border-white/10">
                <SelectItem value="en">English</SelectItem>
                <SelectItem value="zh">中文</SelectItem>
                <SelectItem value="fr">Français</SelectItem>
                <SelectItem value="ar">العربية</SelectItem>
                <SelectItem value="zh_TW">繁體中文</SelectItem>
                <SelectItem value="ru">Русский</SelectItem>
                <SelectItem value="ja">日本語</SelectItem>
                <SelectItem value="de">Deutsch</SelectItem>
                <SelectItem value="uk">Українська</SelectItem>
                <SelectItem value="ko">한국어</SelectItem>
                <SelectItem value="vi">Tiếng Việt</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="flex flex-col gap-2">
            <label className="text-sm font-medium dark:text-cyan-100 uppercase-tracked">{t('settings.theme')}</label>
            <Select value={theme} onValueChange={handleThemeChange}>
              <SelectTrigger className="dark:bg-black/30 dark:border-white/10">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="dark:bg-black/80 dark:backdrop-blur-xl dark:border-white/10">
                <SelectItem value="light">{t('settings.light')}</SelectItem>
                <SelectItem value="dark">{t('settings.dark')}</SelectItem>
                <SelectItem value="system">{t('settings.system')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
