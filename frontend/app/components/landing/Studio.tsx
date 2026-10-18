import React from 'react';

export const Studio: React.FC = () => {
  return (
    <section id="architecture" className="landing-section">
      <div className="landing-max-w" style={{ width: '100%' }}>
        <div className="studio-grid">
          {/* Left: Pull Quote */}
          <div>
            <blockquote className="studio-quote">
              <p className="studio-quote-text">
                &ldquo;Different AI models. Shared context. Work that continues.&rdquo;
              </p>
            </blockquote>
          </div>

          {/* Right: Architecture details */}
          <div>
            <span className="landing-eyebrow">Architecture</span>

            <h2 className="landing-heading" style={{ fontSize: 'clamp(32px, 3.8vw, 44px)', marginTop: '12px' }}>
              One workspace. Multiple AI agents.
            </h2>

            <div className="studio-body">
              <p>
                SYNQ coordinates autonomous AI models across local and cloud environments into a unified, dependency-aware workflow.
              </p>
              <p>
                Persistent project memory powered by FalkorDB graph storage keeps context, architectural decisions, and generated artifacts intact across tasks and sessions.
              </p>
              <p>
                Tasks decompose into directed graphs where models execute concurrently, save checkpoints, and cleanly recover when individual providers fail or degrade.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
