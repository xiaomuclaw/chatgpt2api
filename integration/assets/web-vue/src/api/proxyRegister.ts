import apiClient from './client'
import type { ProxyGroup, ProxyTestResult } from './proxy'

// The register page (imported from GPTGrok2API) uses a simple
// {mode, value} proxy reference and a groups lister. ChatGPT2API's own
// api/proxy.ts models references differently, so keep the register page's
// needs in this dedicated module instead of forking the shared file.

export type { ProxyGroup, ProxyTestResult }

export interface ProxySampleAttempt extends ProxyTestResult {
  scheme: string
}

export interface ProxySampleTestResult extends ProxyTestResult {
  scheme: string
  sample_index: number
  sample_count: number
  attempts: ProxySampleAttempt[]
  normalized_urls?: string
  normalized_changed?: boolean
}

export type ProxyReferenceMode = 'global' | 'direct' | 'profile' | 'group' | 'custom'

export interface RegisterProxyReference {
  mode: ProxyReferenceMode
  value: string
}

export function parseProxyReference(value: unknown): RegisterProxyReference {
  const raw = String(value || '').trim()
  const lower = raw.toLowerCase()
  if (!raw) return { mode: 'global', value: '' }
  if (lower === 'direct') return { mode: 'direct', value: '' }
  if (lower.startsWith('profile:')) return { mode: 'profile', value: raw.slice('profile:'.length).trim() }
  if (lower.startsWith('group:')) return { mode: 'group', value: raw.slice('group:'.length).trim() }
  return { mode: 'custom', value: raw }
}

export function serializeProxyReference(mode: ProxyReferenceMode, value = ''): string {
  const raw = String(value || '').trim()
  if (mode === 'global') return ''
  if (mode === 'direct') return 'direct'
  if (mode === 'profile') return raw ? `profile:${raw}` : ''
  if (mode === 'group') return raw ? `group:${raw}` : ''
  return raw
}

export function proxyReferenceLabel(value: unknown): string {
  const reference = parseProxyReference(value)
  if (reference.mode === 'global') return '使用默认出口'
  if (reference.mode === 'direct') return '直连'
  if (reference.mode === 'profile') return `历史代理配置 ${reference.value || '-'}`
  if (reference.mode === 'group') return `代理组 ${reference.value || '-'}`
  return reference.value
}

export const proxyApi = {
  // chatgpt2api exposes the group list inside /api/proxy/view
  listGroups: async (): Promise<{ groups: ProxyGroup[] }> => {
    try {
      const view = await apiClient.get<never, { groups?: ProxyGroup[] }>('/api/proxy/view')
      return { groups: Array.isArray(view?.groups) ? view.groups : [] }
    } catch {
      return { groups: [] }
    }
  },

  // served by the register engine (nginx routes this one path there)
  testSample: (urls: string) =>
    apiClient.post<{ urls: string }, { result: ProxySampleTestResult }>('/api/proxy/sample-test', { urls }),
}
