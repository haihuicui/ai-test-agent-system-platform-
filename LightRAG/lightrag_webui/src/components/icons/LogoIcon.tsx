import { cn } from '@/lib/utils'

interface LogoIconProps {
  className?: string
  size?: number
}

export default function LogoIcon({ className, size = 32 }: LogoIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={cn('dark:animate-glow-breathe dark:drop-shadow-[0_0_10px_rgba(6,182,212,0.7)]', className)}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="logo-gradient" x1="4" y1="4" x2="28" y2="28" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#34d399" />
          <stop offset="50%" stopColor="#0ea5e9" />
          <stop offset="100%" stopColor="#6366f1" />
        </linearGradient>
        <filter id="logo-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="2" result="coloredBlur" />
          <feMerge>
            <feMergeNode in="coloredBlur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      {/* Hexagon frame */}
      <path
        d="M16 2L28 9V23L16 30L4 23V9L16 2Z"
        stroke="url(#logo-gradient)"
        strokeWidth="2.5"
        fill="none"
        strokeLinejoin="round"
        className="dark:drop-shadow-[0_0_6px_rgba(6,182,212,0.6)]"
      />
      {/* Central document / node */}
      <rect x="12" y="11" width="8" height="10" rx="1.5" fill="url(#logo-gradient)" opacity="0.15" />
      <rect x="12" y="11" width="8" height="10" rx="1.5" stroke="url(#logo-gradient)" strokeWidth="1.5" fill="none" />
      <path d="M14 14H18" stroke="url(#logo-gradient)" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M14 17H18" stroke="url(#logo-gradient)" strokeWidth="1.2" strokeLinecap="round" />
      <path d="M14 20H16.5" stroke="url(#logo-gradient)" strokeWidth="1.2" strokeLinecap="round" />
      {/* Connection nodes */}
      <circle cx="22" cy="9" r="2" fill="url(#logo-gradient)" />
      <circle cx="10" cy="9" r="2" fill="url(#logo-gradient)" />
      <circle cx="16" cy="25" r="2" fill="url(#logo-gradient)" />
      {/* Connection lines */}
      <path d="M16 21V25" stroke="url(#logo-gradient)" strokeWidth="1.2" />
      <path d="M15.2 12.3L11.4 9.8" stroke="url(#logo-gradient)" strokeWidth="1.2" />
      <path d="M16.8 12.3L20.6 9.8" stroke="url(#logo-gradient)" strokeWidth="1.2" />
    </svg>
  )
}
