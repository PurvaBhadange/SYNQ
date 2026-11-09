'use client';

import React from 'react';
import { useInView } from './useInView';

interface Stage {
  number: string;
  pill: string;
  title: string;
  description: string;
}

const STAGES: Stage[] = [
  {
    number: '01',
    pill: 'DAG scheduling',
    title: 'Decompose',
    description:
      'Turn complex objectives into manageable tasks with explicit dependencies and deterministic topological DAG ordering.',
  },
  {
    number: '02',
    pill: 'Capability mesh',
    title: 'Coordinate',
    description:
      'Route tasks to eligible AI models according to capabilities, privacy, availability, and configured token limits.',
  },
  {
    number: '03',
    pill: 'Graph checkpoints',
    title: 'Continue',
    description:
      'Preserve checkpoints and project context in FalkorDB graph memory so work recovers from failures and continues seamlessly.',
  },
];

export const Process: React.FC = () => {
  const { ref, isInView } = useInView<HTMLElement>({ threshold: 0.25 });

  return (
    <section id="process" ref={ref} className="landing-section">
      <div className="landing-max-w" style={{ width: '100%' }}>
        {/* Eyebrow */}
        <span className="landing-eyebrow">How SYNQ works</span>

        {/* H2 */}
        <h2 className="landing-heading">Plan, coordinate, execute</h2>

        {/* Three columns */}
        <div className="process-grid">
          {STAGES.map((stage, idx) => (
            <div
              key={stage.number}
              className={`process-card reveal-item ${isInView ? 'is-in' : ''}`}
              style={{ transitionDelay: `${idx * 140}ms` }}
            >
              <div className="process-num">{stage.number}</div>

              <span className="process-pill">{stage.pill}</span>

              <h3 className="process-title">{stage.title}</h3>

              <p className="process-desc">{stage.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

