'use client';

import React, { useEffect, useState } from 'react';
import { providersApi, ProviderInfo, RegistryStatus } from '@/lib/api';

export default function ProvidersPage() {
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingHealth, setTestingHealth] = useState<Record<string, boolean>>({});
  const [healthResults, setHealthResults] = useState<Record<string, { healthy: boolean; error?: string }>>({});

  const loadProviders = async () => {
    try {
      setLoading(true);
      const data = await providersApi.list();
      setRegistryStatus(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProviders();
  }, []);

  const handleTestHealth = async (providerId: string, modelId: string) => {
    const key = `${providerId}:${modelId}`;
    try {
      setTestingHealth((prev) => ({ ...prev, [key]: true }));
      const result = await providersApi.checkHealth(providerId, modelId);
      setHealthResults((prev) => ({ ...prev, [key]: result }));
    } catch (err: any) {
      setHealthResults((prev) => ({
        ...prev,
        [key]: { healthy: false, error: err.message },
      }));
    } finally {
      setTestingHealth((prev) => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div>
      <div style={{ marginBottom: '32px' }}>
        <h1 className="font-serif" style={{ fontSize: '2rem', color: '#fff', marginBottom: '8px' }}>
          Capability Registry & Model Health
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.95rem', maxWidth: '750px', lineHeight: 1.5 }}>
          Verified AI capabilities for local and cloud models. Router uses this registry for deterministic model matching,
          automatic degradation cooldowns, and seamless fallback cascades.
        </p>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          Loading capability registry...
        </div>
      ) : !registryStatus || registryStatus.providers.length === 0 ? (
        <div className="glass-panel" style={{ padding: '40px', textAlign: 'center' }}>
          No models registered yet.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {registryStatus.providers.map((p) => {
            const key = `${p.provider_id}:${p.model_id}`;
            const testResult = healthResults[key];
            const isTesting = testingHealth[key];

            return (
              <div
                key={key}
                className="glass-panel"
                style={{
                  padding: '24px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '20px',
                }}
              >
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                    <h3 style={{ fontSize: '1.25rem', color: '#fff' }}>{p.display_name}</h3>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: 700,
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: p.is_local ? 'rgba(81, 207, 102, 0.12)' : 'rgba(51, 154, 240, 0.12)',
                        color: p.is_local ? 'var(--status-completed)' : 'var(--status-running)',
                        border: `1px solid ${p.is_local ? 'rgba(81, 207, 102, 0.3)' : 'rgba(51, 154, 240, 0.3)'}`,
                      }}
                    >
                      {p.is_local ? 'LOCAL (Zero Cost)' : 'CLOUD (API)'}
                    </span>
                    <span className={`badge ${p.is_configured ? 'badge-completed' : 'badge-failed'}`}>
                      {p.is_configured ? 'Configured' : 'Missing Key'}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '12px' }}>
                    <span>Provider: <strong style={{ color: 'var(--text-secondary)' }}>{p.provider_id}</strong></span>
                    <span>Model: <strong style={{ color: 'var(--text-secondary)' }}>{p.model_id}</strong></span>
                    <span>Context Window: <strong style={{ color: 'var(--text-secondary)' }}>{p.context_window_tokens.toLocaleString()} tokens</strong></span>
                    <span>Streaming: <strong style={{ color: 'var(--text-secondary)' }}>{p.supports_streaming ? 'Yes' : 'No'}</strong></span>
                    <span>Verification: <strong style={{ color: 'var(--text-secondary)' }}>{p.capability_source}</strong></span>
                  </div>

                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    {p.supported_task_types.map((type) => (
                      <span
                        key={type}
                        style={{
                          fontSize: '0.75rem',
                          background: 'rgba(255, 255, 255, 0.05)',
                          padding: '3px 8px',
                          borderRadius: '4px',
                          color: 'var(--accent-orange-light)',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
                  <button
                    onClick={() => handleTestHealth(p.provider_id, p.model_id)}
                    disabled={isTesting}
                    className="btn-secondary"
                    style={{ padding: '8px 18px', fontSize: '0.85rem' }}
                  >
                    {isTesting ? 'Pinging Provider...' : 'Test Live Health'}
                  </button>

                  {testResult && (
                    <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                      {testResult.healthy ? (
                        <span style={{ color: 'var(--status-completed)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                          ✓ Healthy & Ready
                        </span>
                      ) : (
                        <span style={{ color: 'var(--status-failed)' }}>
                          ✕ Unreachable ({testResult.error || 'Connection failed'})
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
