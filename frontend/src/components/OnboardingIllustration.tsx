/** Lightweight decorative artwork; never conveys processing completion. */
export default function OnboardingIllustration({ kind }: { kind: 'professional' | 'door' | 'document' | 'processing' }) {
  return <svg className={`onboarding-art onboarding-art-${kind}`} viewBox="0 0 320 300" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
    <path d="M35 213C6 145 43 51 123 41c89-12 174 41 174 131 0 68-47 105-131 102-68-2-110-14-131-61Z" fill="#F1ECFF" />
    <g stroke="#9480D4" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
      {kind === 'door' ? <>
        <path d="M89 258V76l124-39v221M102 258V87l98-30v201" />
        <path d="m200 57 25 17v184h-25V57Z" fill="#6446C6" /><path d="M210 166v17" stroke="#DDD3FF" />
        <path className="onboarding-door-path" pathLength="1" d="M18 266c44 10 82-4 130-35" stroke="#7047FF" />
        <path d="M43 257v-65m0 37c-26-5-32-24-27-37 19 2 29 16 27 37Zm1-17c2-24 16-34 29-29 1 17-11 28-29 29Z" fill="#DCD1FA" /><path d="m27 246 4 23h28l4-23H27Z" fill="#E6DEFA" />
      </> : kind === 'professional' ? <>
        <path d="M104 176h102v54H104z" fill="#DCD1FA" /><path d="m117 230-9 44m85-44 12 44M75 277h188" />
        <path d="M124 118c-17 9-25 32-25 66l69 3 15-47-59-22Z" fill="white" stroke="#27233F" />
        <path d="M131 115c-14-4-21-17-17-32s26-22 36-7c10 16 0 36-9 38" fill="white" stroke="#27233F" />
        <path d="M113 91c-8-17 6-31 20-28 6-9 20-3 20 6 14 11 6 24-2 28l-7-17-31 11Z" fill="#27233F" stroke="#27233F" />
        <path d="m119 142 20 27 40-7m-23-29 13 23" stroke="#27233F" /><path d="m162 165 15-39h58l-16 40h-57Z" fill="#F8F5FF" />
        <path d="M103 182c25-6 50-3 64 4l37 54-19 12-43-46-13 56-22-3 7-52" fill="#27233F" stroke="#27233F" />
        <path d="m185 251 13-12 26 14-4 9-35-11Zm-78 9 22 2 9 12-38 1 7-15Z" fill="white" stroke="#27233F" />
        <path d="M55 251v-86m0 54c-26-5-32-25-26-40 19 4 28 19 26 40Zm0-24c2-24 16-37 29-32 1 18-11 31-29 32Z" fill="#DCD1FA" /><path d="m39 244 4 31h27l4-31H39Z" fill="#E6DEFA" />
      </> : <>
        <rect x="100" y="68" width="137" height="184" rx="12" fill="#E5DCFC" transform="rotate(12 100 68)" />
        <rect x="71" y="48" width="144" height="190" rx="12" fill="#FFFEFF" />
        <circle cx="96" cy="77" r="7" fill="#DCD1FA" stroke="none" /><path d="M114 77h67M91 107h103M91 128h103M91 149h84M91 170h90M91 191h58" stroke="#D5C9F6" strokeWidth="3" />
        {kind === 'processing' && <g stroke="#7960C5" strokeWidth="5"><circle cx="215" cy="181" r="31" fill="#F3EFFF" fillOpacity=".65" /><path d="m238 205 34 35" strokeWidth="9" /></g>}
      </>}
    </g>
  </svg>
}
