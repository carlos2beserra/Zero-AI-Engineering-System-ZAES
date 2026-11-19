import Link from 'next/link'
import { Badge } from '@/components/ui/badge'
import { Logo } from '@/components/brand/Logo'
import { NavItems } from '@/components/layout/NavItems'

interface Props {
  section?: 'docs' | 'init'
}

export function SiteHeader({ section }: Props) {
  return (
    <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-sm border-b border-border/40">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2">
          <Logo size={22} />
          <span className="font-bold text-sm tracking-tight">MAES</span>
          {section === 'docs' && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
              Docs
            </Badge>
          )}
          {section === 'init' && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
              init
            </Badge>
          )}
        </Link>
        <NavItems />
      </div>
    </header>
  )
}
