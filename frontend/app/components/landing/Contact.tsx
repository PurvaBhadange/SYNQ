'use client';

import React, { useState } from 'react';
import Link from 'next/link';

export const Contact: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) return;
    setSubmitted(true);
  };

  return (
    <section id="contact" className="contact-section">
      <div className="contact-inner">
        {/* H2 */}
        <h2 className="contact-title">
          Ready to coordinate your AI workflow?
        </h2>

        {/* Form */}
        <form onSubmit={handleSubmit} className="contact-form">
          <label htmlFor="work-email" className="sr-only" style={{ position: 'absolute', width: '1px', height: '1px', padding: 0, margin: '-1px', overflow: 'hidden', clip: 'rect(0, 0, 0, 0)', border: 0 }}>
            Work email
          </label>
          <input
            id="work-email"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Work email"
            className="contact-input"
          />
          <button type="submit" className="contact-submit">
            Get Started
          </button>
        </form>

        {submitted && (
          <p className="contact-feedback" role="status">
            SYNQ coordinator ready. Configure your local and cloud models in the workspace.
          </p>
        )}

        <div style={{ marginTop: '28px' }}>
          <Link href="/app" className="btn-landing-primary" style={{ padding: '12px 24px', fontSize: '14px' }}>
            Open Workspace Dashboard →
          </Link>
        </div>

        {/* Footer line */}
        <footer className="contact-footer">
          &copy; SYNQ &middot; Autonomous Multi-Agent AI Orchestration
        </footer>
      </div>
    </section>
  );
};
