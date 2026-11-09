'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React, { Suspense, useEffect, useState } from 'react';
import { systemApi } from '@/lib/api';

function NavLinks() {
  const pathname = usePathname();
  return (
    <nav aria-label="Workspace Navigation" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
      <Link
        href="/app"
        style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: pathname === '/app' ? '#F0F3F6' : 'var(--text-muted)',
          padding: '6px 14px',
          borderRadius: '6px',
          background: pathname === '/app' ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
          border: pathname === '/app' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid transparent',
          transition: 'all 0.15s ease',
        }}
      >
        Workspaces
      </Link>
      <Link
        href="/app/providers"
        style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: pathname === '/app/providers' ? '#F0F3F6' : 'var(--text-muted)',
          padding: '6px 14px',
          borderRadius: '6px',
          background: pathname === '/app/providers' ? 'rgba(255, 255, 255, 0.08)' : 'transparent',
          border: pathname === '/app/providers' ? '1px solid rgba(255, 255, 255, 0.1)' : '1px solid transparent',
          transition: 'all 0.15s ease',
        }}
      >
        Capability Registry
      </Link>
    </nav>
  );
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean | null>(null);

  useEffect(() => {
    let isMounted = true;
    const checkHealth = () => {
      systemApi
        .health()
        .then((res) => {
          if (isMounted) setIsBackendHealthy(res.status === 'ok');
        })
        .catch(() => {
          if (isMounted) setIsBackendHealthy(false);
        });
    };

    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* ── App Top Navigation Bar ────────────────────────────────────────── */}
      <header
        style={{
          background: '#0E1116',
          borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          padding: '0 24px',
          height: '56px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          {/* Unified Geometric Logo */}
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '8px' }} aria-label="SYNQ Home">
            <div
              style={{
                width: '16px',
                height: '16px',
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 7px)',
                gap: '2px',
              }}
              aria-hidden="true"
            >
              <span style={{ width: '7px', height: '7px', backgroundColor: '#F5B841', borderRadius: '1px' }} />
              <span style={{ width: '7px', height: '7px', backgroundColor: '#1A212B', borderRadius: '1px', border: '1px solid rgba(255, 255, 255, 0.08)' }} />
              <span style={{ width: '7px', height: '7px', backgroundColor: '#1A212B', borderRadius: '1px', border: '1px solid rgba(255, 255, 255, 0.08)' }} />
              <span style={{ width: '7px', height: '7px', backgroundColor: 'rgba(240, 243, 246, 0.85)', borderRadius: '1px' }} />
            </div>
            <span style={{ fontSize: '1.05rem', fontWeight: 600, color: '#F0F3F6', letterSpacing: '-0.02em', fontFamily: 'var(--font-display)' }}>
              SYNQ
            </span>
            <span
              style={{
                fontSize: '0.68rem',
                fontWeight: 500,
                color: 'var(--text-muted)',
                background: 'rgba(255, 255, 255, 0.04)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                padding: '2px 6px',
                borderRadius: '4px',
                fontFamily: 'var(--font-mono)',
              }}
            >
              v0.1.0
            </span>
          </Link>

          <Suspense fallback={<nav style={{ width: '180px' }} />}>
            <NavLinks />
          </Suspense>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {/* Health indicator */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              fontSize: '0.75rem',
              fontFamily: 'var(--font-mono)',
              color: 'var(--text-secondary)',
              padding: '4px 8px',
              background: 'rgba(255, 255, 255, 0.03)',
              borderRadius: '4px',
              border: '1px solid rgba(255, 255, 255, 0.08)',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                background:
                  isBackendHealthy === null
                    ? '#E5A93C'
                    : isBackendHealthy
                    ? '#40C057'
                    : '#FA5252',
                display: 'inline-block',
              }}
            />
            <span>
              {isBackendHealthy === null
                ? 'Connecting...'
                : isBackendHealthy
                ? 'Coordinator online'
                : 'Coordinator offline'}
            </span>
          </div>

          <Link
            href="/"
            style={{
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              padding: '4px 8px',
              borderRadius: '4px',
              transition: 'color 0.15s ease',
            }}
          >
            Landing
          </Link>
        </div>
      </header>

      {/* ── Main App Content ─────────────────────────────────────────────── */}
      <main style={{ flex: 1, padding: '32px 24px', maxWidth: '1440px', margin: '0 auto', width: '100%' }}>
        <Suspense fallback={<div style={{ padding: '40px', color: 'var(--text-muted)' }}>Loading workspace...</div>}>
          {children}
        </Suspense>
      </main>
    </div>
  );
}
