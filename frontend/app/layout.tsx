import type { Metadata } from 'next';
import React from 'react';
import './globals.css';
import './landing.css';

export const metadata: Metadata = {
  title: 'SYNQ — Multi-Agent AI Orchestration with Continuous Project Memory',
  description:
    'One workspace. Multiple AI agents. Continuous shared memory in FalkorDB. Deterministic routing and automatic recovery.',
  icons: {
    icon: '/favicon.ico',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
        {children}
      </body>
    </html>
  );
}
