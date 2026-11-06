import { lazy, Suspense, useState, type ComponentProps } from 'react'
import type Drawer from './HiringEnquiryDrawer'
import { cachedHiringDrawer, loadHiringDrawer } from './hiringDrawerLoader'

const LazyDrawer = lazy(loadHiringDrawer)
export default function DeferredHiringEnquiryDrawer(props: ComponentProps<typeof Drawer>) {
  const [Cached] = useState(cachedHiringDrawer)
  if (Cached) return <Cached {...props} />
  return <Suspense fallback={null}><LazyDrawer {...props} /></Suspense>
}
