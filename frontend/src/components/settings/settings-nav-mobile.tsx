'use client'

import { usePathname, useRouter } from 'next/navigation'
import { settingsTabs } from '@/config/settings'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

export function SettingsNavMobile() {
  const pathname = usePathname()
  const router = useRouter()
  const current = settingsTabs.find((tab) => tab.href === pathname) ?? settingsTabs[0]

  return (
    <Select
      value={current.href}
      onChange={(key) => key && router.push(String(key))}
      className="w-full"
    >
      <SelectTrigger>
        <SelectValue>
          <current.icon className="size-4" aria-hidden="true" />
          {current.title}
        </SelectValue>
      </SelectTrigger>
      <SelectContent>
        {settingsTabs.map((tab) => (
          <SelectItem key={tab.href} id={tab.href}>
            <tab.icon className="size-4" aria-hidden="true" />
            {tab.title}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
