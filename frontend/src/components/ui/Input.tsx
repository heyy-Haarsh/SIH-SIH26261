import { clsx } from 'clsx'
import type { InputHTMLAttributes, ReactNode, SelectHTMLAttributes } from 'react'

const BASE_INPUT =
  'w-full rounded-lg border bg-[#FAFAFA] px-3 text-sm text-[#111111] placeholder:text-[#AAAAAA] outline-none transition-colors'
  + ' border-[#E0E0E0] focus:border-[#E8622A] focus:ring-2 focus:ring-[#E8622A]/15'
  + ' disabled:opacity-50 disabled:cursor-not-allowed'

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={clsx(BASE_INPUT, 'h-9', className)}
      {...props}
    />
  )
}

export function Select({
  className,
  children,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { children: ReactNode }) {
  return (
    <select
      className={clsx(BASE_INPUT, 'h-9 cursor-pointer', className)}
      {...props}
    >
      {children}
    </select>
  )
}

export function Textarea({
  className,
  ...props
}: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={clsx(BASE_INPUT, 'py-2 min-h-[80px] resize-y', className)}
      {...props}
    />
  )
}

export function Label({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label
      htmlFor={htmlFor}
      className="mb-1.5 block text-xs font-medium"
      style={{ color: '#555555' }}
    >
      {children}
    </label>
  )
}
