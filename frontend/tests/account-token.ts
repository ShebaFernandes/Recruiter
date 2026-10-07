import { spawnSync } from 'node:child_process'
import path from 'node:path'

export function issueLocalAccountToken(email: string, purpose: 'verify_email' | 'reset_password') {
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
        DATABASE_URL: process.env.DATABASE_URL || 'postgresql://enter:enter@127.0.0.1:5433/enter',
      },
    },
  )
  if (result.status !== 0) throw new Error(result.stderr || 'Could not issue local account token.')
  return result.stdout.trim()
}
