'use client';

import React, { useState } from 'react';
import Link from 'next/link';

export const Navbar: React.FC = () => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const closeMenu = () => setMobileMenuOpen(false);

  return (
    <header className="landing-navbar">
      <nav aria-label="Main Navigation" className="landing-max-w landing-nav-inner">
        {/* Left: 14px mini mosaic (2x2 squares, one amber) + SYNQ */}
        <Link href="/" className="landing-logo" aria-label="SYNQ Home">
          <div className="landing-logo-grid" aria-hidden="true">
            <span className="logo-dot-amber" />
            <span className="logo-dot-tile" />
            <span className="logo-dot-tile" />
            <span className="logo-dot-bone" />
          </div>
          <span className="landing-logo-text">SYNQ</span>
        </Link>

        {/* Centre: Process, Capabilities, Architecture, Get Started */}
        <div className="landing-nav-links">
          <a href="#process" className="landing-nav-link">
            How it works
          </a>
          <a href="#capabilities" className="landing-nav-link">
            Capabilities
          </a>
          <a href="#architecture" className="landing-nav-link">
            Architecture
          </a>
          <a href="#contact" className="landing-nav-link">
            Get started
          </a>
        </div>

        {/* Right: Workspace CTA & Mobile Menu Button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link href="/app" className="landing-nav-cta">
            Launch workspace
          </Link>

          <button
            type="button"
            className="landing-menu-btn"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {mobileMenuOpen ? (
                <path d="M18 6L6 18M6 6l12 12" />
              ) : (
                <path d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>
      </nav>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className="landing-mobile-menu" role="menu">
          <a href="#process" className="landing-mobile-link" onClick={closeMenu}>
            How it works
          </a>
          <a href="#capabilities" className="landing-mobile-link" onClick={closeMenu}>
            Capabilities
          </a>
          <a href="#architecture" className="landing-mobile-link" onClick={closeMenu}>
            Architecture
          </a>
          <a href="#contact" className="landing-mobile-link" onClick={closeMenu}>
            Get started
          </a>
          <Link href="/app" className="btn-landing-primary" onClick={closeMenu} style={{ marginTop: '8px', textAlign: 'center' }}>
            Open workspace
          </Link>
        </div>
      )}
    </header>
  );
};

