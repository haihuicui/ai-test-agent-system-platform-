import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/Tooltip'
import { cn } from '@/lib/utils'

// eslint-disable-next-line react-refresh/only-export-components
export const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'bg-primary text-primary-foreground hover:bg-primary/90 dark:bg-gradient-to-r dark:from-cyan-500 dark:to-cyan-400 dark:shadow-[0_0_15px_rgba(6,182,212,0.4),0_0_30px_rgba(6,182,212,0.2)] dark:hover:shadow-[0_0_25px_rgba(6,182,212,0.6),0_0_50px_rgba(6,182,212,0.3)] dark:hover:-translate-y-0.5 dark:active:translate-y-0 dark:transition-all dark:duration-300',
        destructive:
          'bg-destructive text-destructive-foreground hover:bg-destructive/90 dark:shadow-[0_0_15px_rgba(239,68,68,0.4),0_0_30px_rgba(239,68,68,0.2)] dark:hover:shadow-[0_0_25px_rgba(239,68,68,0.6),0_0_50px_rgba(239,68,68,0.3)] dark:hover:-translate-y-0.5 dark:active:translate-y-0 dark:transition-all dark:duration-300',
        outline:
          'border border-input bg-background hover:bg-accent hover:text-accent-foreground dark:border-white/10 dark:bg-black/20 dark:hover:bg-white/5 dark:hover:border-cyan-500/30 dark:hover:text-cyan-400 dark:hover:shadow-[0_0_15px_rgba(6,182,212,0.15)] dark:transition-all dark:duration-300',
        secondary:
          'bg-secondary text-secondary-foreground hover:bg-secondary/80 dark:bg-white/5 dark:hover:bg-white/10 dark:border dark:border-white/10 dark:hover:shadow-[0_0_15px_rgba(255,255,255,0.08)] dark:transition-all dark:duration-300',
        ghost:
          'hover:bg-accent hover:text-accent-foreground dark:hover:bg-white/5 dark:hover:text-cyan-400 dark:hover:shadow-[0_0_10px_rgba(6,182,212,0.1)] dark:transition-all dark:duration-300',
        link: 'text-primary underline-offset-4 hover:underline dark:text-cyan-400 dark:hover:shadow-[0_0_10px_rgba(6,182,212,0.15)] dark:transition-all dark:duration-300'
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'size-8'
      }
    },
    defaultVariants: {
      variant: 'default',
      size: 'default'
    }
  }
)

interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
  VariantProps<typeof buttonVariants> {
  asChild?: boolean
  side?: 'top' | 'right' | 'bottom' | 'left'
  tooltip?: string
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, tooltip, size, side = 'right', asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    if (!tooltip) {
      return (
        <Comp
          className={cn(buttonVariants({ variant, size, className }), 'cursor-pointer')}
          ref={ref}
          {...props}
        />
      )
    }

    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <Comp
              className={cn(buttonVariants({ variant, size, className }), 'cursor-pointer')}
              ref={ref}
              {...props}
            />
          </TooltipTrigger>
          <TooltipContent side={side}>{tooltip}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    )
  }
)
Button.displayName = 'Button'

export type ButtonVariantType = Exclude<
  NonNullable<Parameters<typeof buttonVariants>[0]>['variant'],
  undefined
>

export default Button
