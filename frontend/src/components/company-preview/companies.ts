import shiprocket from '../../../../design-references/prepared/trusted-by-review/assets/shiprocket-official.svg'
import wazirx from '../../../../design-references/prepared/trusted-by-review/assets/wazirx-official.svg'
import cred from '../../../../design-references/prepared/trusted-by-review/assets/expanded/cred-wordmark.png'
import nanonets from '../../../../design-references/prepared/trusted-by-review/assets/expanded/nanonets.svg'
import coindcx from '../../../../design-references/prepared/trusted-by-review/assets/expanded/coindcx.png'
import navi from '../../../../design-references/prepared/trusted-by-review/assets/expanded/navi.svg'
import mpl from '../../../../design-references/prepared/trusted-by-review/assets/expanded/mpl.webp'
import dream11 from '../../../../design-references/prepared/trusted-by-review/assets/expanded/dream11.svg'
import truefoundry from '../../../../design-references/prepared/trusted-by-review/assets/expanded/truefoundry.svg'
import kindred from '../../../../design-references/prepared/trusted-by-review/assets/expanded/kindred-transparent.svg'
import practo from '../../../../design-references/prepared/trusted-by-review/assets/expanded/practo.svg'
import arintra from '../../../../design-references/prepared/trusted-by-review/assets/expanded/arintra.svg'
import orangeHealth from '../../../../design-references/prepared/trusted-by-review/assets/expanded/orange-health.svg'
import zepto from '../../../../design-references/prepared/trusted-by-review/assets/expanded/zepto-wordmark.svg'
import coinswitch from '../../../../design-references/prepared/trusted-by-review/assets/expanded/coinswitch.svg'
import pagarbook from '../../../../design-references/prepared/trusted-by-review/assets/expanded/pagarbook.svg'
import hackerearth from '../../../../design-references/prepared/trusted-by-review/assets/expanded/hackerearth.svg'
import justanswer from '../../../../design-references/prepared/trusted-by-review/assets/expanded/justanswer.png'
import mindtickle from '../../../../design-references/prepared/trusted-by-review/assets/expanded/mindtickle.webp'
import commerceiq from '../../../../design-references/prepared/trusted-by-review/assets/expanded/commerceiq.avif'
import satsure from '../../../../design-references/prepared/trusted-by-review/assets/expanded/satsure.svg'
import spicejet from '../../../../design-references/prepared/trusted-by-review/assets/expanded/spicejet.svg'
import signeasy from '../../../../design-references/prepared/trusted-by-review/assets/expanded/signeasy.webp'
import locus from '../../../../design-references/prepared/trusted-by-review/assets/expanded/locus.svg'
import spoton from '../../../../design-references/prepared/trusted-by-review/assets/expanded/spoton.svg'
import parspec from '../../../../design-references/prepared/trusted-by-review/assets/expanded/parspec.svg'
import sentisum from '../../../../design-references/prepared/trusted-by-review/assets/expanded/sentisum.svg'

type CompanyLogo = {
  id: string
  name: string
  category: string
  description: string
  source: string
  logo: string
  height: number
  treatment?: 'silhouette' | 'original'
}

// Owner approved public display of the existing row on 2026-10-12.
// Only verified usable artwork from the replacement list is included. Missing
// and ambiguous brands remain excluded; no substitute artwork is fabricated.
// Keep the existing first two logos; append only companies from the user's list.
// Source URLs and unresolved identities are recorded in expanded/sources.json.
export const previewCompanies: readonly CompanyLogo[] = [
  { id: 'shiprocket', name: 'Shiprocket', category: 'E-commerce logistics', description: 'Shipping and fulfilment tools for e-commerce businesses.', source: 'https://www.shiprocket.in/', logo: shiprocket, height: 31 },
  { id: 'wazirx', name: 'WazirX', category: 'Digital assets', description: 'A cryptocurrency trading platform based in India.', source: 'https://wazirx.com/', logo: wazirx, height: 48 },
  { id: 'cred', name: 'CRED', category: 'Financial services', description: 'Credit card payments and financial services for members.', source: 'https://cred.club/', logo: cred, height: 38, treatment: 'silhouette' },
  { id: 'nanonets', name: 'Nanonets', category: 'Document automation', description: 'AI tools for extracting and processing business documents.', source: 'https://nanonets.com/', logo: nanonets, height: 40 },
  { id: 'coindcx', name: 'CoinDCX', category: 'Digital assets', description: 'A cryptocurrency investment and trading platform.', source: 'https://coindcx.com/', logo: coindcx, height: 30, treatment: 'silhouette' },
  { id: 'navi', name: 'Navi', category: 'Financial services', description: 'Digital payments, lending and investment services.', source: 'https://navi.com/', logo: navi, height: 30 },
  { id: 'mpl', name: 'MPL', category: 'Gaming', description: 'A platform for mobile games and competitions.', source: 'https://www.mpl.live/', logo: mpl, height: 38, treatment: 'silhouette' },
  { id: 'dream11', name: 'Dream11', category: 'Sports', description: 'A digital platform for sports fans.', source: 'https://www.dream11.com/', logo: dream11, height: 32, treatment: 'silhouette' },
  { id: 'truefoundry', name: 'TrueFoundry', category: 'AI infrastructure', description: 'Infrastructure for deploying and managing AI applications.', source: 'https://www.truefoundry.com/', logo: truefoundry, height: 30 },
  { id: 'kindred', name: 'Kindred Group', category: 'Online gaming', description: 'An online gaming group, now part of FDJ UNITED.', source: 'https://www.kindredgroup.com/', logo: kindred, height: 38 },
  { id: 'practo', name: 'Practo', category: 'Healthcare', description: 'A platform connecting patients with healthcare providers.', source: 'https://www.practo.com/', logo: practo, height: 30 },
  { id: 'arintra', name: 'Arintra', category: 'Healthcare technology', description: 'AI-powered medical coding and revenue-cycle automation.', source: 'https://www.arintra.com/', logo: arintra, height: 30, treatment: 'silhouette' },
  { id: 'orange-health', name: 'Orange Health', category: 'Diagnostics', description: 'Diagnostic lab testing with at-home sample collection.', source: 'https://www.orangehealth.in/', logo: orangeHealth, height: 30 },
  { id: 'zepto', name: 'Zepto', category: 'Quick commerce', description: 'Delivery of groceries and everyday essentials.', source: 'https://www.zepto.com/', logo: zepto, height: 32, treatment: 'silhouette' },
  { id: 'coinswitch', name: 'CoinSwitch', category: 'Digital assets', description: 'A cryptocurrency investment and trading platform.', source: 'https://coinswitch.co/', logo: coinswitch, height: 30, treatment: 'silhouette' },
  { id: 'pagarbook', name: 'PagarBook', category: 'Workforce software', description: 'Staff attendance and payroll management software.', source: 'https://pagarbook.com/', logo: pagarbook, height: 30 },
  { id: 'hackerearth', name: 'HackerEarth', category: 'Developer hiring', description: 'Technical assessments and developer hiring tools.', source: 'https://www.hackerearth.com/', logo: hackerearth, height: 30, treatment: 'silhouette' },
  { id: 'justanswer', name: 'JustAnswer', category: 'Expert services', description: 'Online questions and answers from professional experts.', source: 'https://www.justanswer.com/info/press', logo: justanswer, height: 38 },
  { id: 'mindtickle', name: 'Mindtickle', category: 'Sales enablement', description: 'Sales training, coaching and revenue enablement software.', source: 'https://www.mindtickle.com/', logo: mindtickle, height: 30 },
  { id: 'commerceiq', name: 'CommerceIQ', category: 'Retail e-commerce', description: 'Software for retail e-commerce operations and advertising.', source: 'https://www.commerceiq.ai/', logo: commerceiq, height: 30, treatment: 'silhouette' },
  { id: 'satsure', name: 'SatSure', category: 'Geospatial intelligence', description: 'Satellite-data analytics for business decision-making.', source: 'https://www.satsure.co/', logo: satsure, height: 27, treatment: 'silhouette' },
  { id: 'spicejet', name: 'SpiceJet', category: 'Aviation', description: 'An Indian airline providing passenger flight services.', source: 'https://www.spicejet.com/', logo: spicejet, height: 34, treatment: 'silhouette' },
  { id: 'signeasy', name: 'Signeasy', category: 'Electronic signatures', description: 'Electronic signatures and contract management software.', source: 'https://signeasy.com/', logo: signeasy, height: 30 },
  { id: 'locus', name: 'Locus', category: 'Logistics technology', description: 'Logistics planning and delivery optimization software.', source: 'https://locus.sh/', logo: locus, height: 32 },
  { id: 'spoton', name: 'SpotOn', category: 'Restaurant technology', description: 'Point-of-sale and business software for restaurants.', source: 'https://www.spoton.com/', logo: spoton, height: 32 },
  { id: 'parspec', name: 'Parspec', category: 'Construction technology', description: 'AI quoting software for building-product distributors.', source: 'https://www.parspec.io/', logo: parspec, height: 30, treatment: 'silhouette' },
  { id: 'sentisum', name: 'SentiSum', category: 'Customer intelligence', description: 'AI analysis of customer feedback and support conversations.', source: 'https://www.sentisum.com/', logo: sentisum, height: 42 },
]
