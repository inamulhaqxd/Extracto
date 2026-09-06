'use client'

import { useRouter } from 'next/navigation'
import { ThemeProvider as NextThemesProvider } from 'next-themes'
import type { ReactNode } from 'react'
import { RouterProvider } from 'react-aria-components'
import { SidebarConfigProvider } from '@/contexts/sidebar-config-context'
import { CustomizerProvider } from '@/contexts/customizer-context'
import { CustomizerBootstrap } from '@/components/customizer/customizer-bootstrap'

declare module 'react-aria-components' {
  interface RouterConfig {
    routerOptions: NonNullable<Parameters<ReturnType<typeof useRouter>['push']>[1]>
  }
}

export function Providers({ children }: { children: ReactNode }) {
  const router = useRouter()

  return (
    <RouterProvider navigate={router.push}>
      <NextThemesProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <SidebarConfigProvider>
          <CustomizerProvider>
            <CustomizerBootstrap />
            {children}
          </CustomizerProvider>
        </SidebarConfigProvider>
      </NextThemesProvider>
    </RouterProvider>
  )
}
