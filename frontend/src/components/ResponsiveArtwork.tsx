import { useRef, useState, type ImgHTMLAttributes } from 'react'
import useDeferredArtwork from './useDeferredArtwork'

type Artwork = {
  width: number; height: number; original: string; preview: string
  webp: string; webpSrcSet: string; avif: string; avifSrcSet: string
}
type Props = Omit<ImgHTMLAttributes<HTMLImageElement>, 'src' | 'srcSet' | 'width' | 'height' | 'onError'> & {
  artwork: Artwork; eager?: boolean; introPreview?: boolean; detailReady?: boolean
}

/** Same artwork at the required size, with a persistent preview and bounded fallbacks. */
export default function ResponsiveArtwork({ artwork, eager = false, introPreview = false, detailReady = true, style, ...props }: Props) {
  const image = useRef<HTMLImageElement>(null)
  const nearby = useDeferredArtwork(image, !eager)
  const ready = (eager || nearby) && (!introPreview || detailReady)
  const preview = introPreview ? artwork.webpSrcSet.split(',')[0].trim().split(' ')[0] : artwork.preview
  const avif = introPreview && !detailReady ? artwork.avifSrcSet.split(',')[0].trim() : artwork.avifSrcSet
  const [format, setFormat] = useState<'avif' | 'webp' | 'original' | 'preview'>('avif')
  return <picture style={{ display: 'contents' }}>
    {(ready || introPreview) && format === 'avif' && <source style={{ display: 'none' }} type="image/avif" srcSet={avif} sizes={props.sizes} />}
    <img {...props} ref={image} width={artwork.width} height={artwork.height}
      src={format === 'preview' ? artwork.preview : format === 'original' ? artwork.original : !ready ? preview : artwork.webp}
      srcSet={ready && (format === 'avif' || format === 'webp') ? artwork.webpSrcSet : undefined}
      loading={eager ? 'eager' : 'lazy'} decoding="async" fetchPriority={eager ? 'low' : 'auto'}
      style={{ backgroundImage: `url("${artwork.preview}")`, backgroundSize: 'cover', backgroundPosition: 'center', ...style }}
      onError={() => { if (ready || introPreview) setFormat(current => current === 'avif' ? 'webp' : current === 'webp' ? 'original' : 'preview') }} />
  </picture>
}
