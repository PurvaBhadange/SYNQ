'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import React, { Suspense, useEffect, useState } from 'react';
import { systemApi } from '@/lib/api';

function NavLinks() {
  const pathname = usePathname();
  return (
    <nav style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
      <Link
        href="/app"
        style={{
          fontSize: '0.9rem',
          fontWeight: 600,
          color: pathname === '/app' ? 'var(--accent-orange)' : 'var(--text-secondary)',
          padding: '6px 12px',
          borderRadius: '6px',
          background: pathname === '/app' ? 'var(--accent-orange-subtle)' : 'transparent',
        }}
      >
        Projects
      </Link>
      <Link
        href="/app/providers"
        style={{
          fontSize: '0.9rem',
          fontWeight: 600,
          color: pathname === '/app/providers' ? 'var(--accent-orange)' : 'var(--text-secondary)',
          padding: '6px 12px',
          borderRadius: '6px',
          background: pathname === '/app/providers' ? 'var(--accent-orange-subtle)' : 'transparent',
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
    systemApi
      .health()
      .then((res) => setIsBackendHealthy(res.status === 'ok'))
      .catch(() => setIsBackendHealthy(false));
  }, []);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh', background: 'var(--bg-primary)' }}>
      {/* ── App Top Navigation ────────────────────────────────────────────── */}
      <header
        style={{
          background: 'var(--bg-secondary)',
          borderBottom: '1px solid var(--border-subtle)',
          padding: '12px 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
          <Link href="/" style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '32px',
                height: '32px',
                borderRadius: '6px',
                background: 'linear-gradient(135deg, #f08c00, #ff922b)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
              }}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="18" cy="5" r="3"></circle>
                <circle cx="6" cy="12" r="3"></circle>
                <circle cx="18" cy="19" r="3"></circle>
                <line x1="8.59" y1="13.51" x2="15.42" y2="17.49"></line>
                <line x1="15.41" y1="6.51" x2="8.59" y2="10.49"></line>
              </svg>
            </div>
            <span style={{ fontSize: '1.25rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
              SYNQ
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
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
              padding: '4px 10px',
              background: 'rgba(255, 255, 255, 0.04)',
              borderRadius: 'var(--radius-full)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background:
                  isBackendHealthy === null
                    ? '#ffbd2e'
                    : isBackendHealthy
                    ? '#27c93f'
                    : '#ff5f56',
              }}
            ></span>
            <span>
              {isBackendHealthy === null
                ? 'Connecting...'
                : isBackendHealthy
                ? 'Backend Online'
                : 'Backend Offline'}
            </span>
          </div>

          <Link
            href="/app"
            className="btn-primary"
            style={{ padding: '8px 16px', fontSize: '0.85rem' }}
          >
            + New Project
          </Link>
        </div>
      </header>

      {/* ── Main App Content ─────────────────────────────────────────────── */}
      <main style={{ flex: 1, padding: '32px 24px', maxWidth: '1360px', margin: '0 auto', width: '100%' }}>
        <Suspense fallback={<div style={{ padding: '40px', color: 'var(--text-muted)' }}>Loading workspace...</div>}>
          {children}
        </Suspense>
      </main>
    </div>
  );
}
