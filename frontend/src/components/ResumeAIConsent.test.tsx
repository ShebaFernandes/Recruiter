import '@testing-library/jest-dom/vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { ResumeAIConsent } from './CandidateExperience'

const document = {
  text: "Use AI to help extract my resume. I agree that the text extracted from this resume will be sent to Google's paid Gemini API, which may process it outside India, to create suggestions for my professional profile. I can leave this unchecked and use ENTER's rule-based extraction.\n",
  version: 'enter-resume-ai-consent-v1.1',
  sha256: 'a'.repeat(64),
  effective_date: '2026-10-24',
  unpublished: false,
}

it('renders the approved optional permission unchecked and records an affirmative choice', () => {
  const change = vi.fn()
  render(<ResumeAIConsent document={document} checked={false} disabled={false} change={change} />)
  const checkbox = screen.getByRole('checkbox', { name: document.text.trim() })
  expect(checkbox).not.toBeChecked()
  fireEvent.click(checkbox)
  expect(change).toHaveBeenCalledWith(true)
})
