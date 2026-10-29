import { CSSProperties, ReactNode } from 'react'

/**
 * Premium Skeleton UI Components — animated placeholders shown during lazy-load & data fetch.
 * Uses hardware-accelerated shimmer effects to prevent layout shift and elevate visual polish.
 */

export interface SkeletonProps {
  variant?: 'text' | 'circular' | 'rounded' | 'rectangular'
  width?: string | number
  height?: string | number
  className?: string
  style?: CSSProperties
  children?: ReactNode
}

/** Base atomic skeleton primitive with optional shimmer */
export function Skeleton({
  variant = 'rounded',
  width,
  height,
  className = '',
  style = {},
}: SkeletonProps) {
  const variantClass = {
    text: 'h-3.5 rounded-md',
    circular: 'rounded-full',
    rounded: 'rounded-lg',
    rectangular: 'rounded-none',
  }[variant]

  const inlineStyle: CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    ...style,
  }

  return (
    <div
      className={`skeleton-shimmer inline-block shrink-0 ${variantClass} ${className}`}
      style={inlineStyle}
      aria-hidden="true"
    />
  )
}

/** Multi-line paragraph skeleton with realistic varying line widths */
export function SkeletonText({
  lines = 3,
  className = 'space-y-2',
}: {
  lines?: number
  className?: string
}) {
  const widths = ['w-full', 'w-[92%]', 'w-[78%]', 'w-[85%]', 'w-[65%]']
  return (
    <div className={className} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton
          key={i}
          variant="text"
          className={`h-3 ${widths[i % widths.length]}`}
        />
      ))}
    </div>
  )
}

/** Small badge or pill placeholder */
export function SkeletonBadge({ width = 64 }: { width?: number | string }) {
  return <Skeleton variant="rounded" width={width} height={20} className="rounded-full" />
}

/** Button placeholder */
export function SkeletonButton({ width = 100, height = 36 }: { width?: number | string; height?: number }) {
  return <Skeleton variant="rounded" width={width} height={height} className="rounded-lg" />
}

/** Single skeleton table row with configurable column count */
export function SkeletonRow({ cols = 5 }: { cols?: number }) {
  const widths = ['w-24', 'w-44', 'w-32', 'w-20', 'w-28', 'w-16', 'w-36']
  return (
    <tr className="border-b border-[#F0F0F0]">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-6 py-4">
          <Skeleton
            variant="rounded"
            className={`h-3.5 ${widths[i % widths.length]}`}
          />
        </td>
      ))}
    </tr>
  )
}

/** Multiple skeleton rows for a table body */
export function SkeletonTable({
  rows = 5,
  cols = 5,
  withHeader = false,
}: {
  rows?: number
  cols?: number
  withHeader?: boolean
}) {
  return (
    <div className="w-full overflow-hidden">
      {withHeader && (
        <div className="flex border-b border-[#F0F0F0] px-6 py-3 bg-[#FAFAFA]">
          {Array.from({ length: cols }).map((_, i) => (
            <div key={i} className="flex-1">
              <Skeleton variant="text" className="h-3 w-20" />
            </div>
          ))}
        </div>
      )}
      <table className="w-full text-left">
        <tbody>
          {Array.from({ length: rows }).map((_, i) => (
            <SkeletonRow key={i} cols={cols} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** A card-shaped skeleton for metric or summary boxes */
export function SkeletonCard({ lines = 3 }: { lines?: number }) {
  return (
    <div
      className="rounded-xl p-5"
      style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
    >
      <Skeleton variant="rounded" className="h-3 w-24 mb-3" />
      <Skeleton variant="rounded" className="h-7 w-14 mb-3" />
      {lines > 2 && <Skeleton variant="rounded" className="h-2.5 w-36" />}
    </div>
  )
}

/** Metric row placeholder for dashboards (borderless, with dividers) */
export function SkeletonMetricRow({ cells = 4 }: { cells?: number }) {
  return (
    <div
      className="flex flex-wrap overflow-hidden rounded-xl mb-6"
      style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
    >
      {Array.from({ length: cells }).map((_, i) => (
        <div
          key={i}
          className="flex-1 px-6 py-5 metric-divider"
          style={{ minWidth: '140px' }}
        >
          <Skeleton variant="rounded" className="h-3 w-20 mb-3" />
          <Skeleton variant="rounded" className="h-7 w-12 mb-2" />
          <Skeleton variant="rounded" className="h-2.5 w-28" />
        </div>
      ))}
    </div>
  )
}

/** Grid of cards (for Categories, Requirements, Rules, etc.) */
export function SkeletonCardGrid({ count = 6 }: { count?: number }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl p-5 space-y-3"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="flex items-center justify-between">
            <Skeleton variant="rounded" className="h-4 w-32" />
            <SkeletonBadge width={56} />
          </div>
          <SkeletonText lines={2} />
          <div className="pt-2 flex items-center justify-between border-t border-[#F0F0F0]">
            <Skeleton variant="rounded" className="h-3 w-20" />
            <Skeleton variant="rounded" className="h-3 w-16" />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Feed/list skeleton for notifications, audit logs, or deficiency notices */
export function SkeletonFeed({ count = 4 }: { count?: number }) {
  return (
    <div
      className="rounded-xl overflow-hidden divide-y divide-[#F0F0F0]"
      style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
    >
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="flex items-start gap-4 p-5">
          <Skeleton variant="circular" width={36} height={36} className="shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton variant="rounded" className="h-4 w-48" />
              <Skeleton variant="rounded" className="h-3 w-20" />
            </div>
            <SkeletonText lines={2} />
          </div>
        </div>
      ))}
    </div>
  )
}

/** Detail view skeleton: Split/2-column layout (sidebar metadata + main workspace) */
export function SkeletonDetailLayout() {
  return (
    <div className="space-y-6 animate-fade-in">
      {/* Top Header */}
      <div
        className="rounded-xl p-6"
        style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
      >
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <Skeleton variant="rounded" className="h-3 w-24" />
              <SkeletonBadge width={60} />
            </div>
            <Skeleton variant="rounded" className="h-6 w-64" />
            <Skeleton variant="rounded" className="h-3.5 w-96" />
          </div>
          <div className="flex gap-2">
            <SkeletonButton width={110} />
            <SkeletonButton width={130} />
          </div>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-6">
        <div
          className="rounded-xl p-6 space-y-6"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="flex gap-3 border-b border-[#F0F0F0] pb-3">
            <Skeleton variant="rounded" className="h-7 w-24" />
            <Skeleton variant="rounded" className="h-7 w-24" />
            <Skeleton variant="rounded" className="h-7 w-24" />
          </div>
          <SkeletonText lines={4} />
          <div className="h-64 rounded-xl skeleton-shimmer" />
        </div>

        <div
          className="rounded-xl p-6 space-y-4"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <Skeleton variant="rounded" className="h-4 w-32" />
          <div className="space-y-3 pt-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex justify-between py-2 border-b border-[#F0F0F0]">
                <Skeleton variant="rounded" className="h-3 w-24" />
                <Skeleton variant="rounded" className="h-3 w-28" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Full-page Suspense fallback for route-level lazy loading */
export function PageSkeleton() {
  return (
    <div className="min-h-screen bg-[#F5F5F5] animate-fade-in">
      {/* Top Bar placeholder */}
      <div
        className="h-14 border-b border-[#F0F0F0] bg-white px-6 flex items-center justify-between"
      >
        <div className="flex items-center gap-3">
          <Skeleton variant="circular" width={28} height={28} />
          <Skeleton variant="rounded" className="h-4 w-32" />
        </div>
        <div className="flex items-center gap-3">
          <Skeleton variant="rounded" className="h-7 w-28 rounded-full" />
          <Skeleton variant="circular" width={28} height={28} />
        </div>
      </div>

      {/* Content Canvas */}
      <main className="max-w-7xl mx-auto px-6 py-8 space-y-6">
        {/* Header bar */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-2">
            <Skeleton variant="rounded" className="h-3 w-36" />
            <Skeleton variant="rounded" className="h-6 w-56" />
            <Skeleton variant="rounded" className="h-3 w-80" />
          </div>
          <SkeletonButton width={120} height={38} />
        </div>

        {/* Metric Row */}
        <SkeletonMetricRow cells={4} />

        {/* Main Card/Table */}
        <div
          className="rounded-xl overflow-hidden"
          style={{ background: '#FFFFFF', border: '1px solid #F0F0F0' }}
        >
          <div className="p-5 border-b border-[#F0F0F0] flex items-center justify-between">
            <Skeleton variant="rounded" className="h-4 w-40" />
            <Skeleton variant="rounded" className="h-8 w-60 rounded-lg" />
          </div>
          <SkeletonTable rows={6} cols={5} withHeader />
        </div>
      </main>
    </div>
  )
}
