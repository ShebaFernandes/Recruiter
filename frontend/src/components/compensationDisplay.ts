// Display only: trim fractional zeroes without converting decimal strings to
// floating point, rounding amounts, or changing API/storage precision.
export function compensationDisplay(value: string | number | null | undefined): string {
  return String(value ?? '').replace(/(\.\d*?)0+$/, '$1').replace(/\.$/, '')
}
