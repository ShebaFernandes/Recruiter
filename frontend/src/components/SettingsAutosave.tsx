import { useEffect, useImperativeHandle, useRef, useState } from 'react'
import type { ReactNode, Ref, RefObject } from 'react'

export type SettingsAutosaveHandle = { flush: () => Promise<boolean>; changed: (immediate?: boolean) => void }

export default function SettingsAutosave({ ref, formRef, dirty: dirtyRef, flight: flightRef, save, close, field, children, errorText, onSaved, closeOnSave = false }: {
  ref: Ref<SettingsAutosaveHandle>; formRef: RefObject<HTMLFormElement | null>;
  dirty: RefObject<boolean>; flight: RefObject<boolean>;
  save: (data: FormData) => Promise<boolean>; close: () => void; field: string; children: ReactNode; errorText?: string;
  onSaved?: () => void; closeOnSave?: boolean;
}) {
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved' | 'invalid' | 'error'>('idle')
  const revision = useRef(0)
  const touched = useRef(new Set<string>())
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const pending = useRef<Promise<boolean> | null>(null)
  const exitRequested = useRef(false)
  const finalizeRequested = useRef(false)
  const lastSaved = useRef('')
  const closeTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const motion = useRef<Animation | null>(null)
  const hasSaved = useRef(false)
  const reduceMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? true
  function cancelClose() {
    if (closeTimer.current === undefined) return
    clearTimeout(closeTimer.current); closeTimer.current = undefined
    motion.current?.cancel(); motion.current = null
  }
  useEffect(() => { if (formRef.current) lastSaved.current = JSON.stringify([...new FormData(formRef.current)]) }, [formRef])
  const saveRef = useRef(save)
  const closeRef = useRef(close)
  const savedRef = useRef(onSaved)
  useEffect(() => { saveRef.current = save; closeRef.current = close; savedRef.current = onSaved })
  useEffect(() => {
    const preference = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    const changed = () => {
      if (!preference?.matches) return
      motion.current?.cancel()
      if (closeTimer.current !== undefined) {
        clearTimeout(closeTimer.current); closeTimer.current = undefined
        if (!dirtyRef.current && !flightRef.current) closeRef.current()
      }
    }
    preference?.addEventListener?.('change', changed)
    return () => preference?.removeEventListener?.('change', changed)
  }, [dirtyRef, flightRef])
  useEffect(() => {
    const form = formRef.current
    if (form?.animate && !reduceMotion()) {
      const height = form.getBoundingClientRect().height
      motion.current = form.animate([{ height: '0px', opacity: 0, overflow: 'hidden' }, { height: `${height}px`, opacity: 1, overflow: 'hidden' }], { duration: 160, easing: 'ease-out' })
    }
    return () => { clearTimeout(closeTimer.current); motion.current?.cancel() }
  }, [formRef])
  function requestClose() {
    if (closeTimer.current !== undefined) return
    const version = revision.current
    closeTimer.current = setTimeout(() => {
      const form = formRef.current
      if (!form || dirtyRef.current || flightRef.current || version !== revision.current) { cancelClose(); return }
      if (reduceMotion() || !form.animate) { closeRef.current(); return }
      motion.current?.cancel()
      const style = getComputedStyle(form)
      const animation = form.animate([
        { height: `${form.getBoundingClientRect().height}px`, opacity: 1, paddingTop: style.paddingTop, paddingBottom: style.paddingBottom, borderBottomWidth: style.borderBottomWidth, overflow: 'hidden' },
        { height: '0px', opacity: 0, paddingTop: '0px', paddingBottom: '0px', borderBottomWidth: '0px', overflow: 'hidden' },
      ], { duration: 180, easing: 'ease-in-out', fill: 'forwards' })
      motion.current = animation
      void animation.finished.then(() => {
        if (!dirtyRef.current && !flightRef.current && version === revision.current) closeRef.current()
      }).catch(() => { /* A new edit/focus cancels closing without losing its draft. */ })
    }, reduceMotion() ? 0 : hasSaved.current ? 250 : 0)
  }
  useEffect(() => {
    if (status !== 'saved') return
    const timeout = setTimeout(() => setStatus('idle'), 2500)
    return () => clearTimeout(timeout)
  }, [status])
  async function flush(finalize = true): Promise<boolean> {
    if (finalize) finalizeRequested.current = true
    clearTimeout(timer.current)
    if (pending.current) return pending.current
    if (!dirtyRef.current) return true
    const operation = (async () => {
      while (dirtyRef.current) {
        const form = formRef.current
        if (!form || !form.checkValidity()) { setStatus('invalid'); return false }
        // Empty dropdown placeholders and incomplete numeric/text entries are
        // drafts, not an instruction to erase saved values during typing.
        const incomplete = [...form.querySelectorAll<HTMLInputElement | HTMLSelectElement>('input[type=number],input[type=url],input[type=tel],input[type=email],select[name=notice],select[name=setup]')].some(input => touched.current.has(input.name) && !input.value.trim() && !(finalizeRequested.current && input instanceof HTMLInputElement && input.type !== 'email'))
        if (incomplete) { setStatus('invalid'); return false }
        const data = new FormData(form)
        const snapshot = JSON.stringify([...data])
        if (snapshot === lastSaved.current) { dirtyRef.current = false; setStatus('idle'); return true }
        const version = revision.current
        flightRef.current = true; setStatus('saving')
        let ok = false
        try { ok = await saveRef.current(data) } catch { /* Keep the draft and expose retry below. */ }
        finally { flightRef.current = false }
        if (!ok) { setStatus('error'); return false }
        lastSaved.current = snapshot
        if (version === revision.current) dirtyRef.current = false
      }
      setStatus('saved')
      hasSaved.current = true
      savedRef.current?.()
      return true
    })()
    pending.current = operation
    try {
      const ok = await operation
      if (ok && (closeOnSave || exitRequested.current)) requestClose()
      return ok
    } finally { pending.current = null }
  }
  function changed(immediate = false) {
    cancelClose()
    dirtyRef.current = true; revision.current++; finalizeRequested.current = false; setStatus('idle')
    clearTimeout(timer.current)
    // Next task lets React commit location-chip hidden inputs before reading.
    timer.current = setTimeout(() => { void flush(false) }, immediate ? 0 : 600)
  }
  useImperativeHandle(ref, () => ({ flush, changed }))
  const finishRef = useRef<() => void>(() => {})
  useEffect(() => { finishRef.current = () => { exitRequested.current = true; void flush().then(ok => { if (ok && exitRequested.current) requestClose() }) } })
  useEffect(() => {
    const outside = (event: PointerEvent) => {
      const target = event.target as Element
      if (!formRef.current?.contains(target) && !target.closest('[data-setting]')) finishRef.current()
      else { exitRequested.current = false; cancelClose() }
    }
    document.addEventListener('pointerdown', outside)
    return () => { clearTimeout(timer.current); document.removeEventListener('pointerdown', outside) }
  }, [formRef])
  return <form ref={formRef} id={`settings-editor-${field}`} className="cp-settings-editor cp-settings-inline-editor"
    onFocusCapture={() => { exitRequested.current = false; cancelClose() }}
    onChange={event => { const target = event.target; if (target instanceof HTMLInputElement || target instanceof HTMLSelectElement) touched.current.add(target.name); changed(target instanceof HTMLSelectElement) }}
    onSubmit={event => { event.preventDefault(); finishRef.current() }}
    onBlur={event => { const target = event.relatedTarget as Element | null; if (target && !event.currentTarget.contains(target) && !target.closest('[data-setting]')) finishRef.current() }}>
    {children}
    <p role="status" className="cp-autosave-status">{status === 'saving' ? 'Saving…' : status === 'saved' ? 'Saved' : status === 'invalid' ? 'Complete valid values to save your changes.' : ''}</p>
    {status === 'error' && <div role="alert">{errorText || 'Your changes couldn’t be saved.'} Your entries are kept here. <button type="button" onClick={() => {
      // Retry disappears while saving; keep keyboard focus in the editor so a
      // successful close can return it to the original Edit action.
      const finish = exitRequested.current
      formRef.current?.querySelector<HTMLElement>('input:not([type=hidden]), select')?.focus({ preventScroll: true })
      exitRequested.current = finish
      void flush()
    }}>Retry</button></div>}
  </form>
}
