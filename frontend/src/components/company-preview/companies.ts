import shiprocket from '../../../../design-references/prepared/trusted-by-review/assets/shiprocket-official.svg'
import wazirx from '../../../../design-references/prepared/trusted-by-review/assets/wazirx-official.svg'

// Owner approved public display of the existing row on 2026-10-12.
// Only verified usable artwork from the replacement list is included. Missing
// and ambiguous brands remain excluded; no substitute artwork is fabricated.
export const previewCompanies = [
  { id: 'shiprocket', name: 'Shiprocket', category: 'E-commerce logistics', description: 'Shipping and fulfilment tools for e-commerce businesses.', source: 'https://www.shiprocket.in/', logo: shiprocket, height: 31 },
  { id: 'wazirx', name: 'WazirX', category: 'Digital assets', description: 'A cryptocurrency trading platform based in India.', source: 'https://wazirx.com/', logo: wazirx, height: 48 },
] as const
