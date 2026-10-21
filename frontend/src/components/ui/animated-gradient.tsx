import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'

type PatternShape = 'Checks' | 'Stripes' | 'Edge'
interface Params {
  color1: string; color2: string; color3: string; rotation: number; proportion: number
  scale: number; speed: number; distortion: number; swirl: number; swirlIterations: number
  softness: number; offset: number; shape: PatternShape; shapeSize: number
}
type PresetName = 'Prism' | 'Lava' | 'Plasma' | 'Pulse' | 'Vortex' | 'Mist'
type GradientConfig = ({ preset: 'custom' } & Pick<Params, 'color1' | 'color2' | 'color3'> & Partial<Params>) | { preset: PresetName; speed?: number }
const defaults: Params = { color1: '#F7F9FC', color2: '#B7C9DE', color3: '#142B50', rotation: 0, proportion: 35, scale: 1, speed: 25, distortion: 12, swirl: 80, swirlIterations: 10, softness: 100, offset: 0, shape: 'Checks', shapeSize: 10 }
const presets: Record<PresetName, Params> = {
  Prism: { ...defaults, color1: '#050505', color2: '#66B3FF', color3: '#FFFFFF', rotation: -50, proportion: 1, scale: .01, speed: 30, distortion: 0, swirl: 50, swirlIterations: 16, softness: 47, offset: -299, shapeSize: 45 },
  Lava: { ...defaults, color1: '#FF9F21', color2: '#FF0303', color3: '#000000', rotation: 114, proportion: 100, scale: .52, speed: 30, distortion: 7, swirl: 18, swirlIterations: 20, offset: 717, shape: 'Edge', shapeSize: 12 },
  Plasma: { ...defaults, color1: '#B566FF', color2: '#000000', color3: '#000000', proportion: 63, scale: .75, speed: 30, distortion: 5, swirl: 61, swirlIterations: 5, offset: -168, shapeSize: 28 },
  Pulse: { ...defaults, color1: '#66FF85', color2: '#000000', color3: '#000000', rotation: -167, proportion: 92, scale: 0, speed: 20, distortion: 54, swirl: 75, swirlIterations: 3, softness: 28, offset: -813, shapeSize: 79 },
  Vortex: { ...defaults, color1: '#000000', color2: '#FFFFFF', color3: '#000000', rotation: 50, proportion: 41, scale: .4, speed: 20, distortion: 0, swirl: 100, swirlIterations: 3, softness: 5, offset: -744, shape: 'Stripes', shapeSize: 80 },
  Mist: { ...defaults, color1: '#050505', color2: '#FF66B8', color3: '#050505', proportion: 33, scale: .48, speed: 39, distortion: 4, swirl: 65, swirlIterations: 5, offset: -235, shape: 'Edge', shapeSize: 48 },
}
interface Props {
  config?: GradientConfig; noise?: { opacity: number; scale?: number }
  radius?: string; style?: CSSProperties; className?: string; paused?: boolean
}
// Parse CSS colors once, never per frame.
function rgba(color: string): [number, number, number, number] {
  const parser = document.createElement('canvas').getContext('2d')
  if (!parser) return [0, 0, 0, 1]
  parser.fillStyle = color; parser.fillRect(0, 0, 1, 1)
  const c = parser.getImageData(0, 0, 1, 1).data
  return [c[0] / 255, c[1] / 255, c[2] / 255, c[3] / 255]
}
export default function AnimatedGradient({ config = { preset: 'Prism' }, noise, radius = '0px', style, className, paused = false }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const pauseRef = useRef<(() => void) | null>(null)
  const pausedRef = useRef(paused)
  const params = config.preset === 'custom' ? { ...defaults, ...config } : { ...presets[config.preset], speed: config.speed ?? presets[config.preset].speed }
  // Equal values, including inline objects, must not recreate the GPU program.
  const settings = JSON.stringify(params)
  useEffect(() => { pausedRef.current = paused; pauseRef.current?.() }, [paused])
  useEffect(() => {
    const canvas = canvasRef.current!, container = containerRef.current!
    const p: Params = JSON.parse(settings)
    const motion = window.matchMedia?.('(prefers-reduced-motion: reduce)')
    let gl: WebGL2RenderingContext | null = null
    let program: WebGLProgram | null = null, buffer: WebGLBuffer | null = null
    let vertex: WebGLShader | null = null, fragment: WebGLShader | null = null
    let raf: number | undefined, lastTime: number | undefined
    let visible = true, lost = false, elapsed = 0
    let timeLocation: WebGLUniformLocation | null = null
    const state = (value: string) => { container.dataset.renderState = value }
    const stop = () => { if (raf !== undefined) cancelAnimationFrame(raf); raf = undefined; lastTime = undefined }
    const dispose = () => {
      stop(); canvas.hidden = true; state('fallback')
      if (gl) {
        if (!lost) { gl.useProgram(null); gl.bindBuffer(gl.ARRAY_BUFFER, null) }
        if (buffer) gl.deleteBuffer(buffer)
        if (program) gl.deleteProgram(program)
        if (vertex) gl.deleteShader(vertex)
        if (fragment) gl.deleteShader(fragment)
      }
      buffer = program = vertex = fragment = null
    }
    const draw = () => {
      if (!gl || !program || lost) return
      gl.uniform1f(timeLocation, elapsed * p.speed / 20 + p.offset * .01)
      gl.drawArrays(gl.TRIANGLES, 0, 6); canvas.hidden = false
    }
    const active = () => !document.hidden && visible && !motion?.matches && !pausedRef.current && !lost
    const tick = (now: number) => {
      raf = undefined
      if (!active() || !program) return
      if (lastTime === undefined) lastTime = now
      const delta = now - lastTime
      if (delta >= 1000 / 30) { const remainder = delta % (1000 / 30); elapsed += Math.min(delta - remainder, 100) / 1000; lastTime = now - remainder; draw() }
      raf = requestAnimationFrame(tick)
    }
    const sync = () => { stop(); if (!program) return; state(active() ? 'running' : 'paused'); if (active()) raf = requestAnimationFrame(tick) }
    const resize = () => {
      if (!gl || !program || lost) return
      const width = Math.max(1, container.clientWidth), height = Math.max(1, container.clientHeight)
      const ratio = Math.min(window.devicePixelRatio || 1, 1.5, Math.sqrt(1_200_000 / (width * height)))
      canvas.width = Math.max(1, Math.round(width * ratio)); canvas.height = Math.max(1, Math.round(height * ratio))
      gl.viewport(0, 0, canvas.width, canvas.height)
      gl.uniform2f(gl.getUniformLocation(program, 'u_resolution'), canvas.width, canvas.height)
      gl.uniform1f(gl.getUniformLocation(program, 'u_pixelRatio'), ratio)
      if (!document.hidden && visible) draw()
    }
    const initialize = () => {
      dispose()
      if (!motion || motion.matches || lost) return
      try {
        gl = canvas.getContext('webgl2', { alpha: false, antialias: false, powerPreference: 'low-power' })
        if (!gl) return
        const compile = (kind: number, source: string) => {
          const shader = gl!.createShader(kind)
          if (!shader) throw new Error('Shader allocation failed')
          gl!.shaderSource(shader, source); gl!.compileShader(shader)
          if (!gl!.getShaderParameter(shader, gl!.COMPILE_STATUS)) { gl!.deleteShader(shader); throw new Error('Shader compilation failed') }
          return shader
        }
        vertex = compile(gl.VERTEX_SHADER, '#version 300 es\nin vec4 a_position; void main(){gl_Position=a_position;}')
        fragment = compile(gl.FRAGMENT_SHADER, FRAGMENT_SHADER)
        program = gl.createProgram()
        if (!program) throw new Error('Program allocation failed')
        gl.attachShader(program, vertex); gl.attachShader(program, fragment); gl.linkProgram(program)
        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) throw new Error('Program linking failed')
        gl.useProgram(program)
        buffer = gl.createBuffer()
        if (!buffer) throw new Error('Buffer allocation failed')
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1,1,-1,-1,1,-1,1,1,-1,1,1]), gl.STATIC_DRAW)
        const position = gl.getAttribLocation(program, 'a_position')
        if (position < 0) throw new Error('Missing vertex attribute')
        gl.enableVertexAttribArray(position); gl.vertexAttribPointer(position, 2, gl.FLOAT, false, 0, 0)
        const uniforms: Record<string, number> = { u_scale: p.scale, u_rotation: p.rotation * Math.PI / 180, u_proportion: p.proportion / 100, u_softness: p.softness / 100, u_shape: { Checks: 0, Stripes: 1, Edge: 2 }[p.shape], u_shapeScale: p.shapeSize / 100, u_distortion: p.distortion / 50, u_swirl: p.swirl / 100, u_swirlIterations: p.swirl === 0 ? 0 : p.swirlIterations }
        for (const [key, value] of Object.entries(uniforms)) gl.uniform1f(gl.getUniformLocation(program, key), value)
        for (const [i, color] of [p.color1, p.color2, p.color3].entries()) gl.uniform4f(gl.getUniformLocation(program, `u_color${i+1}`), ...rgba(color))
        timeLocation = gl.getUniformLocation(program, 'u_time')
        resize(); sync()
      } catch { dispose() }
    }
    const contextLost = (event: Event) => { event.preventDefault(); lost = true; dispose() }
    const contextRestored = () => { lost = false; initialize() }
    canvas.addEventListener('webglcontextlost', contextLost); canvas.addEventListener('webglcontextrestored', contextRestored)
    document.addEventListener('visibilitychange', sync); motion?.addEventListener('change', initialize)
    const observer = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null
    observer?.observe(container)
    const intersection = typeof IntersectionObserver !== 'undefined' ? new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; sync() }) : null
    intersection?.observe(container)
    pauseRef.current = sync; initialize()
    return () => {
      pauseRef.current = null; observer?.disconnect(); intersection?.disconnect()
      document.removeEventListener('visibilitychange', sync); motion?.removeEventListener('change', initialize)
      canvas.removeEventListener('webglcontextlost', contextLost); canvas.removeEventListener('webglcontextrestored', contextRestored)
      dispose()
    }
  }, [settings])
  return <div ref={containerRef} className={className} aria-hidden="true" style={{ position: 'absolute', inset: 0, pointerEvents: 'none', borderRadius: radius, overflow: 'hidden', background: `linear-gradient(130deg, ${params.color1}, ${params.color2} 55%, ${params.color3})`, ...style }}>
    <canvas ref={canvasRef} hidden style={{ width: '100%', height: '100%' }} />
    {noise && noise.opacity > 0 && <div style={{ position: 'absolute', inset: 0, opacity: Math.min(1, Math.max(0, noise.opacity)) / 2, backgroundSize: `${(noise.scale ?? 1) * 200}px`, backgroundImage: 'url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAADAAAAAwBAMAAAClLOS0AAAAElBMVEUAAAAAAAAAAAAAAAAAAAAAAADgKxmiAAAABnRSTlMCCgkGBAVJOAVJAAAASklEQVQ4y2NgGAWjYBSMglEwCgY/YGRgZBQUYmJiZGQEkYwMjIyMgoKCjIyMIJKBgRFIMjIyAklGRkYGRkFBYEcwMDIyMjAOUQAA1I4HwVwZAkYAAAAASUVORK5CYII=")' }} />}
  </div>
}

// Supplied shader, with bounded loops and defined (ascending) smoothsteps.
const FRAGMENT_SHADER = `#version 300 es
precision highp float;
uniform float u_time,u_pixelRatio,u_scale,u_rotation,u_proportion,u_softness,u_shape,u_shapeScale,u_distortion,u_swirl,u_swirlIterations;
uniform vec2 u_resolution;
uniform vec4 u_color1,u_color2,u_color3;
out vec4 fragColor;
#define TWO_PI 6.28318530718
vec2 rotate(vec2 uv,float th){return mat2(cos(th),sin(th),-sin(th),cos(th))*uv;}
float random(vec2 st){return fract(sin(dot(st,vec2(12.9898,78.233)))*43758.5453123);}
float noise(vec2 st){vec2 i=floor(st),f=fract(st),u=f*f*(3.-2.*f);return mix(mix(random(i),random(i+vec2(1.,0.)),u.x),mix(random(i+vec2(0.,1.)),random(i+vec2(1.,1.)),u.x),u.y);}
vec4 blend_colors(vec4 c1,vec4 c2,vec4 c3,float mixer,float edgesWidth,float edge_blur){
 float r1=smoothstep(.35*edgesWidth,.7-.35*edgesWidth+.5*edge_blur,mixer),r2=smoothstep(.3+.35*edgesWidth,1.-.35*edgesWidth+edge_blur,mixer);
 return vec4(mix(mix(c1.rgb*c1.a,c2.rgb*c2.a,r1),c3.rgb*c3.a,r2),mix(mix(c1.a,c2.a,r1),c3.a,r2));}
void main(){
 vec2 uv=gl_FragCoord.xy/u_resolution;float t=.5*u_time,noise_scale=.0005+.006*u_scale;
 uv-=.5;uv*=noise_scale*u_resolution;uv=rotate(uv,u_rotation);uv/=u_pixelRatio;uv+=.5;
 float n1=noise(uv+t),n2=noise(uv*2.-t),angle=n1*TWO_PI;
 uv.x+=4.*u_distortion*n2*cos(angle);uv.y+=4.*u_distortion*n2*sin(angle);
 for(int j=1;j<=30;j++){float i=float(j);if(i>ceil(clamp(u_swirlIterations,0.,30.)))break;uv.x+=clamp(u_swirl,0.,2.)/i*cos(t+i*1.5*uv.y);uv.y+=clamp(u_swirl,0.,2.)/i*cos(t+i*uv.x);}
 float proportion=clamp(u_proportion,0.,1.),shape=0.,mixer=0.;
 if(u_shape<.5){vec2 q=uv*(.5+3.5*u_shapeScale);shape=.5+.5*sin(q.x)*cos(q.y);mixer=shape+.48*sign(proportion-.5)*pow(abs(proportion-.5),.5);}
 else if(u_shape<1.5){float f=fract((uv*(.25+3.*u_shapeScale)).y);shape=smoothstep(0.,.55,f)*(1.-smoothstep(.45,1.,f));mixer=shape+.48*sign(proportion-.5)*pow(abs(proportion-.5),.5);}
 else{float sh=(.5-uv.y)/(noise_scale*u_resolution.y)+.5;float k=max(.001,.2*(1.-u_shapeScale));shape=smoothstep(.45-k,.55+k,sh+.3*(proportion-.5));mixer=shape;}
 fragColor=blend_colors(u_color1,u_color2,u_color3,mixer,1.-clamp(u_softness,0.,1.),.01+.01*u_scale);
}`
