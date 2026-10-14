/** Keeps the brand accessible as text while displaying the original ENTER logo. */
export default function EnterBrandText({ text }: { text: string }) {
  return <>{text.split(/(\bENTER\b)/).map((part, index) => part === 'ENTER'
    ? <span className="enter-inline-brand" key={index}><img src="/enter-wordmark.svg" alt="" aria-hidden="true" /><span className="sr-only">ENTER</span></span>
    : part)}</>
}
