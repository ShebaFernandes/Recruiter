# ENTER Gemini resume-AI legal change — approval required

Status: **PENDING PRIVACY-OWNER AND QUALIFIED LEGAL APPROVAL**

This draft replaces the earlier unapproved Anthropic-specific proposal. It does
not change any published document, infer legal approval, activate resume AI, or
authorize candidate data to be sent to Google.

Proposed versions and exact public-text SHA-256 values:

- Privacy `enter-candidate-privacy-v1.2`:
  `6549ab6514b940459b8b853ee63643fc97c91f9dfc2d62aac511083c6b1bf574`
- Terms `enter-candidate-terms-v1.2`:
  `c545340b49350c664d0073e081dd4314a6464238adc6a61f9fc8a87b5647dd53`
- Resume-AI consent `enter-resume-ai-consent-v1.1`:
  `e9ba89892b3b29aa738ef7dc7ff2913149be87c44080a058ddfa3cc677041040`

The complete pending copies remain in `PRIVACY_POLICY_PUBLICATION.txt`,
`TERMS_PUBLICATION.txt`, and `RESUME_AI_CONSENT_PUBLICATION.txt`. Their
`PUBLICATION STATUS` lines must remain `PENDING REVIEW` until the exact documents
and provider configuration have been approved.

## Exact optional checkbox copy

> Use AI to help extract my resume. I agree that the text extracted from this resume will be sent to Google's paid Gemini API, which may process it outside India, to create suggestions for my professional profile. I can leave this unchecked and use ENTER's rule-based extraction.

The checkbox remains optional and unchecked. Permission is scoped to the newly
uploaded resume and is recorded with this consent version, exact hash, and a
server timestamp. Existing resumes and earlier provider-specific permissions do
not qualify for the new Gemini version and are not reprocessed.

## Provider and data-handling facts requiring approval

Google's current Gemini API terms distinguish unpaid and paid services:

- Unpaid-service inputs and outputs may be used to improve Google products and
  may be reviewed by people; Google says not to submit sensitive, confidential,
  or personal information to unpaid services.
- For Paid Services, Google states that prompts and responses are not used to
  improve its products and are processed under the applicable Data Processing
  Addendum.
- Security, abuse-monitoring, legal, logging, or enabled-service retention may
  still apply. ENTER must verify the exact production account and settings; it
  must not describe paid service as automatic zero data retention without that
  verification.

Production therefore must use a separately approved paid Gemini project. The
Free-tier key remains restricted to explicitly authorized fictional documents.
Before activation, verify and record:

1. Google project and API-key owner authorization for ENTER production use.
2. Active Paid Service status and the applicable Data Processing Addendum.
3. Qualified review of overseas processing and Google subprocessors.
4. Generate Content logging/storage disabled, no shared feedback or datasets,
   and the approved abuse-monitoring/retention position.
5. The exact initial daily/monthly budgets and current token prices.
6. Privacy-owner and qualified legal approval of all three exact hashes above.

## Smallest release behavior

- Keep rule-based extraction as the unchecked fallback.
- Use `gemini-3.5-flash-lite`, one attempt, no automatic paid retry, strict
  evidence validation, manual-edit protection, and the existing review flow.
- Mount the Gemini API key only into the worker through a root-owned Docker
  secret; do not place it in Git, the frontend, `.env.production`, or web.
- Start in `canary` mode with one explicitly selected synthetic or consented
  resume ID. No other upload or historical resume may invoke Gemini.
- Keep recruiter access blocked and private S3/SQS behavior unchanged.

## Approval evidence required

Record the approver's name and authority, approval timestamp, approved versions,
the three exact hashes, qualified legal clearance, paid-project/DPA review,
overseas-processing decision, logging/retention review, API-key owner approval,
and approved initial budget. Only then mark the publication files approved and
load their immutable values into production.
