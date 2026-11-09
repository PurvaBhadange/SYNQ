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
                &ldquo;Different AI models, shared context, work that continues&rdquo;
              </p>
              <cite className="studio-quote-cite">SYNQ multi-model runtime architecture</cite>
            </blockquote>
          </div>

          {/* Right: Architecture details */}
          <div>
            <span className="landing-eyebrow">Architecture</span>

            <h2 className="landing-heading" style={{ fontSize: 'clamp(32px, 3.8vw, 44px)', marginTop: '12px' }}>
              One workspace, multiple AI models
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

              <div className="studio-specs-list">
                <div className="studio-spec-item">
                  <span className="studio-spec-dot" aria-hidden="true" />
                  <span>Kahn topological DAG</span>
                </div>
                <div className="studio-spec-item">
                  <span className="studio-spec-dot" aria-hidden="true" />
                  <span>FalkorDB graph context</span>
                </div>
                <div className="studio-spec-item">
                  <span className="studio-spec-dot" aria-hidden="true" />
                  <span>Real-time SSE streaming</span>
                </div>
                <div className="studio-spec-item">
                  <span className="studio-spec-dot" aria-hidden="true" />
                  <span>Local and cloud mesh</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

