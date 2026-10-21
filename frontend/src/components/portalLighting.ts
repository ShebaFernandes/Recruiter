/** Short-lived, resolution-capped lighting pass; geometry stays in CSS 3D. */
export function portalLighting(canvas: HTMLCanvasElement, scene: HTMLElement, door: HTMLElement) {
  const ctx = canvas.getContext('2d')
  if (!ctx) return null
  let width = 0, height = 0, doorWidth = 0, doorHeight = 0
  const resize = () => {
    width = scene.clientWidth; height = scene.clientHeight
    doorWidth = door.offsetWidth; doorHeight = door.offsetHeight
    const ratio = Math.min(window.devicePixelRatio || 1, 1.5)
    canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio)
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0)
  }
  resize()
  const observer = new ResizeObserver(resize)
  observer.observe(scene)
  return {
    draw(open: number, depth: number) {
      ctx.clearRect(0, 0, width, height)
      if (!width || !height || !open) return
      const projection = 1100 / (1100 - depth)
      const w = doorWidth * projection, h = doorHeight * projection
      const x = width / 2, y = height / 2
      // Bloom remains centered on the architectural opening, never a separate portal.
      ctx.save()
      ctx.translate(x, y)
      ctx.scale(1, Math.max(1, h / w))
      const halo = ctx.createRadialGradient(0, 0, w * .25, 0, 0, w * 1.2)
      halo.addColorStop(0, `rgba(255,255,255,${open * .34})`)
      halo.addColorStop(.45, `rgba(247,249,252,${open * .12})`)
      halo.addColorStop(1, 'rgba(247,249,252,0)')
      ctx.fillStyle = halo
      ctx.fillRect(-w * 1.2, -w * 1.2, w * 2.4, w * 2.4)
      ctx.restore()
      // Soft floor spill opens with the hinge, rather than flashing on as a rectangle.
      const floor = y + h / 2
      if (floor < height) {
        const light = ctx.createLinearGradient(0, floor, 0, height)
        light.addColorStop(0, `rgba(255,255,255,${open * .28})`)
        light.addColorStop(1, 'rgba(247,249,252,0)')
        ctx.fillStyle = light
        ctx.save()
        ctx.filter = 'blur(8px)'
        ctx.beginPath()
        ctx.moveTo(x - w * .44, floor)
        ctx.lineTo(x - w * .44 + w * .88 * open, floor)
        ctx.lineTo(x + w * (1 + open), height)
        ctx.lineTo(x - w * 1.8, height)
        ctx.closePath(); ctx.fill()
        ctx.restore()
      }
    },
    dispose() { observer.disconnect(); canvas.width = 0; canvas.height = 0 },
  }
}
