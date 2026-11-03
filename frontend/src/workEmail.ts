const personalDomains = new Set(['gmail.com', 'googlemail.com', 'yahoo.com', 'yahoo.co.in', 'ymail.com', 'rocketmail.com', 'outlook.com', 'hotmail.com', 'live.com', 'msn.com', 'icloud.com', 'me.com', 'mac.com', 'aol.com', 'proton.me', 'protonmail.com', 'pm.me', 'rediffmail.com', 'mail.com', 'gmx.com', 'gmx.net'])
export function validWorkEmail(value: string) {
  const email = value.trim()
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && !personalDomains.has(email.split('@')[1].toLowerCase())
}
export function validateWorkEmailInput(input: HTMLInputElement) {
  input.setCustomValidity(validWorkEmail(input.value) ? '' : 'Please use your work email address.')
}
