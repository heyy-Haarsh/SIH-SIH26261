import { clsx } from 'clsx'
import type { ButtonHTMLAttributes, ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline'
type Size = 'sm' | 'md' | 'lg'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  children: ReactNode
  leftIcon?: ReactNode
}

const variants: Record<Variant, string> = {
  primary: 'bg-[#E8622A] text-white hover:bg-[#D4541F]',
  secondary: 'bg-[#F5F5F5] text-[#333333] hover:bg-[#EEEEEE]',
  ghost: 'bg-transparent text-[#555555] hover:bg-[#F5F5F5]',
  danger: 'bg-[#B91C1C] text-white hover:bg-[#991B1B]',
  outline: 'bg-white border text-[#333333] hover:bg-[#F5F5F5]',
}

const outlineStyle: Record<Variant, string> = {
  primary: '',
  secondary: '',
  ghost: '',
  danger: '',
  outline: 'border-[#E0E0E0]',
}

const sizes: Record<Size, string> = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-3.5 text-sm gap-2',
  lg: 'h-10 px-4 text-sm gap-2',
}

export function Button({
  variant = 'primary',
  size = 'md',
  className,
  children,
  leftIcon,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center justify-center rounded-lg font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none',
        variants[variant],
        outlineStyle[variant],
        sizes[size],
        className,
      )}
      disabled={disabled}
      {...props}
    >
      {leftIcon}
      {children}
    </button>
  )
}
