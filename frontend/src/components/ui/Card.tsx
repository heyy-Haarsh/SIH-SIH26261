import { clsx } from 'clsx'
import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  padding?: boolean
}

/** Lintel-style card: white background, 1px #F0F0F0 border, no shadow, rounded-xl */
export function Card({ children, className, padding = true }: CardProps) {
  return (
    <div
      className={clsx('rounded-xl bg-white', padding && 'p-5', className)}
      style={{ border: '1px solid #F0F0F0' }}
    >
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-4 flex items-start justify-between gap-3">
      <div>
        <h2 className="text-sm font-semibold" style={{ color: '#111111' }}>
          {title}
        </h2>
        {description && (
          <p className="mt-0.5 text-xs" style={{ color: '#888888' }}>
            {description}
          </p>
        )}
      </div>
      {action}
    </div>
  )
}
