import * as React from 'react'

import { cn } from '@/lib/utils'

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

function Skeleton({ className, ...props }: SkeletonProps) {
  return (
    <div
      className={cn('animate-pulse rounded-md bg-muted dark:bg-white/5 dark:bg-gradient-to-r dark:from-transparent dark:via-white/15 dark:to-transparent dark:bg-[length:200%_100%] dark:animate-shimmer', className)}
      {...props}
    />
  )
}

export { Skeleton }
