type EnterLogoProps = {
  alt?: string
  className?: string
  decorative?: boolean
}

/**
 * The official ENTER wordmark, cropped only to its transparent artwork bounds.
 * The source asset remains untouched and the fixed viewBox preserves its proportions.
 */
export default function EnterLogo({
  alt = 'ENTER',
  className = '',
  decorative = false,
}: EnterLogoProps) {
  const classes = ['enter-logo-mark', className].filter(Boolean).join(' ')

  return <svg
    className={classes}
    viewBox="145 145 1110 310"
    preserveAspectRatio="xMidYMid meet"
    role={decorative ? undefined : 'img'}
    aria-label={decorative ? undefined : alt}
    aria-hidden={decorative || undefined}
    focusable="false"
  >
    <image href="/enter-wordmark.svg" width="1400" height="600" />
  </svg>
}
