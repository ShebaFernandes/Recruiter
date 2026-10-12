import shiprocket from '../../../../design-references/prepared/trusted-by-review/assets/shiprocket-official.svg'
import wazirx from '../../../../design-references/prepared/trusted-by-review/assets/wazirx-official.svg'

// Partial private preview: only usable verified artwork from the replacement
// list. Other assets/brand guidance are pending, never substituted or fabricated.
// Public-display and monochrome usage permissions are not confirmed.
export const previewCompanies = [
  { id: 'shiprocket', name: 'Shiprocket', category: 'E-commerce logistics', description: 'Shipping and fulfilment tools for e-commerce businesses.', source: 'https://www.shiprocket.in/', logo: shiprocket, height: 31 },
  { id: 'wazirx', name: 'WazirX', category: 'Digital assets', description: 'A cryptocurrency trading platform based in India.', source: 'https://wazirx.com/', logo: wazirx, height: 48 },
] as const
