import { readFileSync } from 'node:fs'
import { roles } from '../src/components/opportunityRoles.ts'
import { approvedPublicOpportunityIds } from '../src/publicationContract.ts'

const manifest = JSON.parse(readFileSync(new URL('../catalog/opportunity-publication.json', import.meta.url), 'utf8'))
const publicIds = approvedPublicOpportunityIds(manifest, roles.map(role => role.id), process.argv.includes('--require-reviewed'))
console.log(`Manifest contract valid. Review status: ${manifest.reviewStatus}. Confirmed public entries: ${publicIds.length}.`)
console.log('Publication enforcement is staged and is not yet connected to the public build.')
