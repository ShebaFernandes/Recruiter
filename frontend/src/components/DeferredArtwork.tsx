import { useRef, type ReactNode } from 'react'
import useDeferredArtwork from './useDeferredArtwork'

export default function DeferredArtwork({ className, children }: { className: string; children: ReactNode }) {
  const target = useRef<HTMLDivElement>(null)
  const ready = useDeferredArtwork(target)
  return <div ref={target} className={className} data-artwork-ready={ready}>{children}</div>
}
