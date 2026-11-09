import React from 'react';
import Link from 'next/link';

interface CapabilityCard {
  tag: string;
  title: string;
  description: string;
  bgColor: string;
  textColor: string;
  borderColor?: string;
  href: string;
}

const CAPABILITIES: CapabilityCard[] = [
  {
    tag: '01 / Model routing',
    title: 'Intelligent Routing',
    description: 'Deterministic capability-based model selection with fallback chains',
    bgColor: '#F5B841',
    textColor: '#0E1116',
    href: '/app/providers',
  },
  {
    tag: '02 / Graph memory',
    title: 'Shared Memory',
    description: 'Continuous FalkorDB graph memory preserving entities and decisions',
    bgColor: '#1B2430',
    textColor: '#F2EFE8',
    href: '/app',
  },
  {
    tag: '03 / DAG coordination',
    title: 'Multi-Agent Execution',
    description: 'Dependency-aware DAG task coordination with real-time SSE streaming',
    bgColor: '#F2EFE8',
    textColor: '#0E1116',
    href: '/app',
  },
  {
    tag: '04 / Local hardware',
    title: 'Local AI',
    description: 'Private zero-cost execution on your hardware through Ollama',
    bgColor: '#22303D',
    textColor: '#F2EFE8',
    href: '/app/providers',
  },
  {
    tag: '05 / Cloud mesh',
    title: 'Hybrid AI',
    description: 'Seamless integration with cloud providers (Gemini, Anthropic, OpenAI)',
    bgColor: '#E8D9BC',
    textColor: '#0E1116',
    href: '/app/providers',
  },
  {
    tag: '06 / Resilient state',
    title: 'Resilient Workflows',
    description: 'Automated validation, execution checkpoints, and graceful recovery',
    bgColor: '#0B0E13',
    textColor: '#F5B841',
    borderColor: '1px solid #F5B841',
    href: '/app',
  },
];

export const Work: React.FC = () => {
  return (
    <section id="capabilities" className="landing-section">
      <div className="landing-max-w" style={{ width: '100%' }}>
        {/* Eyebrow */}
        <span className="landing-eyebrow">Core capabilities</span>

        {/* H2 */}
        <h2 className="landing-heading">Six pillars in production</h2>

        {/* Grid */}
        <div className="capabilities-grid">
          {CAPABILITIES.map((cap) => (
            <Link
              key={cap.title}
              href={cap.href}
              className="cap-card"
              style={{
                backgroundColor: cap.bgColor,
                color: cap.textColor,
                border: cap.borderColor || '1px solid transparent',
              }}
              aria-label={`${cap.title} — ${cap.description}`}
            >
              {/* Subtle architectural grid pattern accent inside each card */}
              <div
                style={{
                  position: 'absolute',
                  inset: 0,
                  opacity: 0.05,
                  pointerEvents: 'none',
                  backgroundImage:
                    'linear-gradient(currentColor 1px, transparent 1px), linear-gradient(to right, currentColor 1px, transparent 1px)',
                  backgroundSize: '24px 24px',
                }}
                aria-hidden="true"
              />

              {/* Card Header: Tag + Hover arrow */}
              <div className="cap-card-header">
                <span className="cap-card-tag">{cap.tag}</span>
                <div className="cap-card-arrow" aria-hidden="true">
                  <span>Open</span>
                  <span>→</span>
                </div>
              </div>

              {/* Card Bottom Content */}
              <div className="cap-card-content">
                <h3 className="cap-card-title">{cap.title}</h3>
                <p className="cap-card-desc">{cap.description}</p>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
};

