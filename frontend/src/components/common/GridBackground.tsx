import './GridBackground.css'

export default function GridBackground() {
  return (
    <div className="grid-background" aria-hidden="true">
      <div className="grid-background__layer" />
      <div className="grid-background__vignette" />
    </div>
  )
}
