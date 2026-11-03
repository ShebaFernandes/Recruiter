import { spawnSync } from 'node:child_process'
import path from 'node:path'

export function issueLocalAccountToken(email: string, purpose: 'verify_email' | 'reset_password') {
  if (!/\/test_enter_e2e_[a-f0-9]+$/.test(process.env.DATABASE_URL || '')) {
    throw new Error('Account tokens may only be issued in the disposable E2E database.')
  }
  const backend = path.resolve('../backend')
  const python = process.env.PYTHON_BIN || path.resolve('../.venv/bin/python')
  const result = spawnSync(
    python,
    ['manage.py', 'issue_local_account_token', email, purpose],
    {
      cwd: backend,
      encoding: 'utf8',
      env: {
        ...process.env,
        DEBUG: 'true',
        DATABASE_URL: process.env.DATABASE_URL,
      },
    },
  )
  if (result.status !== 0) throw new Error(result.stderr || 'Could not issue local account token.')
  return result.stdout.trim()
}
