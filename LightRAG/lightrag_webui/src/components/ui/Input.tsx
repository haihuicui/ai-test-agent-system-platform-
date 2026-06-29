import * as React from 'react'
import { cn } from '@/lib/utils'

const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<'input'>>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          'border-input file:text-foreground placeholder:text-muted-foreground focus-visible:ring-ring flex h-9 rounded-md border bg-transparent px-3 py-1 text-base shadow-sm transition-all file:border-0 file:bg-transparent file:text-sm file:font-medium focus-visible:ring-1 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm [&::-webkit-inner-spin-button]:opacity-50 [&::-webkit-outer-spin-button]:opacity-50 dark:bg-black/30 dark:border-white/10 dark:focus-visible:border-cyan-400/50 dark:focus-visible:shadow-[0_0_15px_rgba(6,182,212,0.3)] dark:focus-visible:ring-cyan-400/30',
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = 'Input'

export default Input
