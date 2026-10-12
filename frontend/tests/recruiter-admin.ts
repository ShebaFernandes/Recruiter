import { spawnSync } from 'node:child_process'
import path from 'node:path'
import { randomUUID } from 'node:crypto'

export function createTestAdministrator() {
  const username = `admin-${randomUUID()}`
  const password = randomUUID()
  const result = spawnSync(process.env.PYTHON_BIN || path.resolve('../.venv/bin/python'), ['-c', `
import json, sys, django
django.setup()
from django.conf import settings
assert '_e2e' in settings.DATABASES['default']['NAME']
from django.contrib.auth.models import User
data = json.load(sys.stdin)
User.objects.create_superuser(username=data['username'], password=data['password'])
`], {
    cwd: path.resolve('../backend'), encoding: 'utf8', input: JSON.stringify({ username, password }),
    env: { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings', TESTING: 'true' },
  })
  if (result.status !== 0) throw new Error('Isolated test administrator setup failed.')
  return { username, password }
}

// Test setup only: no HTTP provisioning endpoint and no production account changes.
export function provisionRecruiter(email: string, password: string) {
  const script = `
import json, sys, django
django.setup()
from django.conf import settings
assert '_e2e' in settings.DATABASES['default']['NAME'], 'Use an isolated _e2e database'
from rest_framework.test import APIClient
from tests.recruiter_helpers import provision_recruiter
data = json.load(sys.stdin)
response = provision_recruiter(APIClient(), {**data, 'full_name': 'Test Recruiter', 'company': 'ENTER'})
assert response.status_code == 200
`
  const result = spawnSync(process.env.PYTHON_BIN || path.resolve('../.venv/bin/python'), ['-c', script], {
    cwd: path.resolve('../backend'), encoding: 'utf8', input: JSON.stringify({ email, password }),
    env: { ...process.env, DJANGO_SETTINGS_MODULE: 'config.settings', TESTING: 'true' },
  })
  if (result.status !== 0) throw new Error('Test recruiter provisioning failed. Check the isolated database configuration.')
}
