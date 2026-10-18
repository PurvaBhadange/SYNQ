import React from 'react';
import Link from 'next/link';
import { TileMosaic } from './TileMosaic';

export const Hero: React.FC = () => {
  return (
    <section className="landing-hero">
      {/* Layer 1: Tile Mosaic (z-0) */}
      <TileMosaic />

      {/* Layer 2: Reading Wash (z-1) */}
      <div className="landing-hero-wash" aria-hidden="true" />

      {/* Layer 3: Headline Block (z-10) */}
      <div className="landing-hero-content">
        <h1 className="landing-hero-title">
          Multiple AI agents. <br />
          <span className="landing-hero-title-amber">One continuous workflow.</span>
        </h1>

        <p className="landing-hero-sub">
          Coordinate AI models, share persistent project memory, and keep complex work moving across local and cloud providers.
        </p>

        <div className="landing-hero-actions">
          <Link href="/app" className="btn-landing-primary">
            Launch Workspace →
          </Link>
          <a href="#capabilities" className="btn-landing-outline">
            Explore Capabilities
          </a>
        </div>
      </div>

      {/* Layer 4: Hero Footer Row (z-20) */}
      <div className="landing-hero-footer">
        <div>
          <div className="hero-stat-val">Hybrid</div>
          <div className="hero-stat-desc">local &amp; cloud routing</div>
        </div>
        <div>
          <div className="hero-stat-val">FalkorDB</div>
          <div className="hero-stat-desc">persistent graph memory</div>
        </div>
        <div>
          <div className="hero-stat-val">DAG</div>
          <div className="hero-stat-desc">task orchestration</div>
        </div>
      </div>
    </section>
  );
};
