import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded-md border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
  {
    variants: {
      variant: {
        default:
          'border-transparent bg-primary text-primary-foreground shadow hover:bg-primary/80 dark:shadow-[0_0_15px_rgba(6,182,212,0.5),0_0_30px_rgba(6,182,212,0.25)]',
        secondary:
          'border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80 dark:border-white/10 dark:bg-white/5 dark:shadow-[0_0_15px_rgba(255,255,255,0.15),0_0_30px_rgba(255,255,255,0.08)]',
        destructive:
          'border-transparent bg-destructive text-destructive-foreground shadow hover:bg-destructive/80 dark:shadow-[0_0_15px_rgba(239,68,68,0.5),0_0_30px_rgba(239,68,68,0.25)] dark:border-red-500/30',
        outline: 'text-foreground dark:border-white/10 dark:bg-black/20',
        success:
          'border-transparent bg-green-100 text-green-700 dark:bg-green-900/40 dark:text-green-300 dark:shadow-[0_0_15px_rgba(16,185,129,0.5),0_0_30px_rgba(16,185,129,0.25)] dark:border-emerald-500/30',
        warning:
          'border-transparent bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-300 dark:shadow-[0_0_15px_rgba(234,179,8,0.5),0_0_30px_rgba(234,179,8,0.25)] dark:border-yellow-500/30',
        info:
          'border-transparent bg-blue-100 text-blue-700 dark:bg-blue-900/40 dark:text-blue-300 dark:shadow-[0_0_15px_rgba(59,130,246,0.5),0_0_30px_rgba(59,130,246,0.25)] dark:border-blue-500/30',
        cyan:
          'border-transparent bg-cyan-100 text-cyan-700 dark:bg-cyan-900/40 dark:text-cyan-300 dark:shadow-[0_0_15px_rgba(6,182,212,0.5),0_0_30px_rgba(6,182,212,0.25)] dark:border-cyan-500/30',
        indigo:
          'border-transparent bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300 dark:shadow-[0_0_15px_rgba(99,102,241,0.5),0_0_30px_rgba(99,102,241,0.25)] dark:border-indigo-500/30',
        purple:
          'border-transparent bg-purple-100 text-purple-700 dark:bg-purple-900/40 dark:text-purple-300 dark:shadow-[0_0_15px_rgba(168,85,247,0.5),0_0_30px_rgba(168,85,247,0.25)] dark:border-purple-500/30'
      }
    },
    defaultVariants: {
      variant: 'default'
    }
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
  VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export default Badge
