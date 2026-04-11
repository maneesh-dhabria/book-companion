import { onMounted, onUnmounted, ref } from 'vue'

export function useBreakpoint() {
  const isMobile = ref(false)
  const isTablet = ref(false)
  const isDesktop = ref(true)

  let mobileQuery: MediaQueryList
  let tabletQuery: MediaQueryList

  function update() {
    isMobile.value = mobileQuery.matches
    isTablet.value = tabletQuery.matches && !mobileQuery.matches
    isDesktop.value = !mobileQuery.matches && !tabletQuery.matches
  }

  onMounted(() => {
    mobileQuery = window.matchMedia('(max-width: 767px)')
    tabletQuery = window.matchMedia('(max-width: 1023px)')
    update()
    mobileQuery.addEventListener('change', update)
    tabletQuery.addEventListener('change', update)
  })

  onUnmounted(() => {
    mobileQuery?.removeEventListener('change', update)
    tabletQuery?.removeEventListener('change', update)
  })

  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1280)

  function updateWidth() {
    width.value = window.innerWidth
  }

  onMounted(() => {
    window.addEventListener('resize', updateWidth)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', updateWidth)
  })

  return { isMobile, isTablet, isDesktop, width }
}
