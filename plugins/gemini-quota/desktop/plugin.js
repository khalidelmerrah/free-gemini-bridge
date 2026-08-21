import { cn, haptic, STATUSBAR_AREAS, Tip, useQuery } from '@hermes/plugin-sdk'
import { jsx } from 'react/jsx-runtime'

const ID = 'gemini-quota'

function compactPercent(value) {
  return Number.isFinite(value) ? `${Math.round(value)}%` : '—'
}

function resetLabel(value) {
  if (!value) return 'reset unknown'
  const delta = new Date(value).getTime() - Date.now()
  if (!Number.isFinite(delta) || delta <= 0) return 'resets now'
  const minutes = Math.max(1, Math.round(delta / 60000))
  if (minutes < 60) return `resets in ${minutes}m`
  const hours = Math.round(minutes / 60)
  if (hours < 48) return `resets in ${hours}h`
  return `resets in ${Math.round(hours / 24)}d`
}

function tooltip(data, error) {
  if (error) return `Gemini quota unavailable: ${error.message || String(error)}`
  if (!data) return 'Loading Gemini quota…'
  if (!data.logged_in) {
    return 'Gemini: not logged in\nLogin (phone-completable): run login_gemini_quota.py'
  }
  const lines = [`Gemini${data.plan ? ` · ${data.plan}` : ''}`]
  for (const window of data.windows || []) {
    lines.push(`${window.label}: ${compactPercent(window.remaining_percent)} remaining · ${resetLabel(window.reset_at)}`)
  }
  for (const detail of data.details || []) lines.push(detail)
  lines.push('Click to refresh')
  return lines.join('\n')
}

function QuotaChip({ ctx }) {
  const query = useQuery({
    queryKey: [ID, 'quota'],
    queryFn: () => ctx.rest('/quota'),
    refetchInterval: 60000,
    retry: 1,
    staleTime: 45000
  })
  const windows = query.data?.windows || []
  const primary = windows[0]
  const label = query.isLoading
    ? 'Gemini …'
    : query.isError
      ? 'Gemini !'
      : !query.data?.logged_in
        ? 'Gemini —'
        : `Gemini ${compactPercent(primary?.remaining_percent)}`

  return jsx(Tip, {
    label: tooltip(query.data, query.error),
    children: jsx('button', {
      type: 'button',
      className: cn(
        'inline-flex h-full items-center gap-1 px-1.5 text-[0.6875rem] transition-colors',
        query.isError
          ? 'text-destructive hover:bg-(--chrome-action-hover)'
          : 'text-(--ui-text-tertiary) hover:bg-(--chrome-action-hover) hover:text-foreground'
      ),
      onClick: () => {
        haptic('tap')
        void query.refetch()
      },
      children: label
    })
  })
}

export default {
  id: ID,
  name: 'Gemini Quota',
  register(ctx) {
    ctx.register({
      id: 'status',
      area: STATUSBAR_AREAS.right,
      order: 1000,
      render: () => jsx(QuotaChip, { ctx })
    })
  }
}
