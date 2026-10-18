import React from 'react';
import Link from 'next/link';

export const Navbar: React.FC = () => {
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
            How It Works
          </a>
          <a href="#capabilities" className="landing-nav-link">
            Capabilities
          </a>
          <a href="#architecture" className="landing-nav-link">
            Architecture
          </a>
          <a href="#contact" className="landing-nav-link">
            Get Started
          </a>
        </div>

        {/* Right: Workspace CTA */}
        <div>
          <Link href="/app" className="landing-nav-cta">
            Launch Workspace →
          </Link>
        </div>
      </nav>
    </header>
  );
};
