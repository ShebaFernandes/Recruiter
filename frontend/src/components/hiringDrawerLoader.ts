type DrawerModule = typeof import('./HiringEnquiryDrawer')
let drawer: Promise<DrawerModule> | undefined
let loaded: DrawerModule['default'] | undefined
export function cachedHiringDrawer() { return loaded }
export function loadHiringDrawer() {
  return drawer ??= import('./HiringEnquiryDrawer').then(module => {
    loaded = module.default
    return module
  }).catch(error => { drawer = undefined; throw error })
}
