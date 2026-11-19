'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { Moon, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'

function ThemeToggle() {
  const [dark, setDark] = useState(false)

  useEffect(() => {
    setDark(document.documentElement.classList.contains('dark'))
  }, [])

  function toggle() {
    const next = !dark
    document.documentElement.classList.toggle('dark', next)
    document.documentElement.style.colorScheme = next ? 'dark' : 'light'
    localStorage.setItem('theme', next ? 'dark' : 'light')
    setDark(next)
  }

  return (
    <Button
      size="sm"
      variant="ghost"
      className="w-8 h-8 p-0"
      onClick={toggle}
      aria-label="Alternar tema"
    >
      {dark ? <Sun size={14} /> : <Moon size={14} />}
    </Button>
  )
}

export function NavItems() {
  const pathname = usePathname()
  const inDocs = pathname.startsWith('/docs')
  const inHome = pathname === '/'

  return (
    <div className="flex items-center gap-2">
      <Link href="/">
        <Button
          size="sm"
          variant={inHome ? 'secondary' : 'outline'}
          className="hidden sm:inline-flex"
        >
          Início
        </Button>
      </Link>
      <Link href="/docs/foundations/why-maes-exists">
        <Button
          size="sm"
          variant={inDocs ? 'secondary' : 'outline'}
          className="hidden sm:inline-flex"
        >
          Documentação
        </Button>
      </Link>
      <ThemeToggle />
    </div>
  )
}
