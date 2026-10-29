import { clsx } from 'clsx'

const NAME_FONT = '"Source Serif 4", Georgia, "Times New Roman", serif'

/** Logo with the full name set beside it, in the letterhead lockup. */
export function AicteMark({ compact = false }: { compact?: boolean }) {
  if (compact) {
    return (
      <img
        src="/aicte-logo.png"
        alt="All India Council for Technical Education"
        width={40}
        height={40}
        className="h-10 w-10 shrink-0 object-contain"
      />
    )
  }

  return (
    <div className="flex items-center gap-2.5" aria-label="All India Council for Technical Education">
      <img
        src="/aicte-logo.png"
        alt=""
        width={68}
        height={68}
        className="h-[68px] w-[68px] shrink-0 object-contain"
      />
      <span className="h-12 w-px shrink-0 bg-[#0B3A6E]/25" aria-hidden />
      <p
        className={clsx('min-w-0 text-left leading-tight text-[#1a1a1a]')}
        style={{ fontFamily: NAME_FONT }}
      >
        <span className="block text-[13px] font-semibold tracking-[-0.01em]">All India Council</span>
        <span className="mt-0.5 block text-[12px] font-medium leading-snug tracking-[-0.01em] text-[#2c2c2c]">
          for Technical Education
        </span>
      </p>
    </div>
  )
}
