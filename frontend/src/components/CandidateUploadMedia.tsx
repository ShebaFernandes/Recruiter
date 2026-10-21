import { useState } from 'react'
import { Pause, Play } from 'lucide-react'
import AnimatedGradient from './ui/animated-gradient'

const config = {
  preset: 'custom' as const, color1: '#F7F9FC', color2: '#DCDCF0', color3: '#163B65',
  speed: 2, scale: .6, rotation: -25, proportion: 36, distortion: 3,
  swirl: 24, swirlIterations: 4, softness: 100, offset: 35,
  shape: 'Checks' as const, shapeSize: 20,
}
export default function CandidateUploadMedia() {
  const [paused, setPaused] = useState(false)
  return <>
    <AnimatedGradient className="upload-background" config={config} paused={paused} />
    <button type="button" className="upload-motion-toggle" aria-label={paused ? 'Play background animation' : 'Pause background animation'} onClick={() => setPaused(value => !value)}>
      {paused ? <Play aria-hidden="true" /> : <Pause aria-hidden="true" />}
    </button>
  </>
}
