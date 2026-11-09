'use client';

import React, { useState } from 'react';
import Link from 'next/link';

export const Contact: React.FC = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!email || !emailRegex.test(email)) {
      setError('Please enter a valid work email address.');
      return;
    }
    setSubmitted(true);
  };

  return (
    <section id="contact" className="contact-section">
      <div className="contact-inner">
        {/* H2 */}
        <h2 className="contact-title">
          Ready to coordinate your AI workflow?
        </h2>

        <p className="contact-sub">
          Deploy multi-agent task execution on your local machine or in the cloud. Zero vendor lock-in with unified graph memory.
        </p>

        {/* Form */}
        {!submitted ? (
          <form onSubmit={handleSubmit} className="contact-form" noValidate>
            <label
              htmlFor="work-email"
              className="sr-only"
              style={{
                position: 'absolute',
                width: '1px',
                height: '1px',
                padding: 0,
                margin: '-1px',
                overflow: 'hidden',
                clip: 'rect(0, 0, 0, 0)',
                border: 0,
              }}
            >
              Work email
            </label>
            <input
              id="work-email"
              type="email"
              required
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (error) setError('');
              }}
              placeholder="Work email"
              className="contact-input"
              aria-invalid={error ? 'true' : 'false'}
              aria-describedby={error ? 'email-error' : undefined}
            />
            <button type="submit" className="contact-submit">
              Get started
            </button>
          </form>
        ) : (
          <div className="contact-feedback" role="status">
            Workspace coordinator ready. Launch the dashboard to configure model endpoints.
          </div>
        )}

        {error && (
          <p id="email-error" style={{ color: '#FA5252', fontSize: '13px', marginTop: '10px' }} role="alert">
            {error}
          </p>
        )}

        <div style={{ marginTop: '28px' }}>
          <Link href="/app" className="btn-landing-primary" style={{ padding: '12px 24px', fontSize: '14px' }}>
            Open workspace dashboard
          </Link>
        </div>

        {/* Footer line */}
        <footer className="contact-footer">
          &copy; SYNQ &middot; Multi-model DAG orchestration
        </footer>
      </div>
    </section>
  );
};

