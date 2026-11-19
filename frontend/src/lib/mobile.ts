import { onBeforeUnmount, ref } from 'vue'

/** Schmale Bildschirme (Smartphone). Gleiche Schwelle wie die @media-Regeln (max-width: 700px). */
export const MOBILE_QUERY = '(max-width: 700px)'

export function useMobile() {
  const mq = typeof window !== 'undefined' && window.matchMedia ? window.matchMedia(MOBILE_QUERY) : null
  const isMobile = ref(!!mq?.matches)
  const on = () => { isMobile.value = !!mq?.matches }
  mq?.addEventListener('change', on)
  onBeforeUnmount(() => mq?.removeEventListener('change', on))
  return isMobile
}
