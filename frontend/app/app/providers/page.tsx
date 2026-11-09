'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { providersApi, RegistryStatus } from '@/lib/api';

export default function ProvidersPage() {
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testingHealth, setTestingHealth] = useState<Record<string, boolean>>({});
  const [healthResults, setHealthResults] = useState<Record<string, { healthy: boolean; error?: string; latencyMs?: number }>>({});

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [filterType, setFilterType] = useState<'all' | 'local' | 'cloud' | 'configured'>('all');

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
    const startTime = performance.now();
    try {
      setTestingHealth((prev) => ({ ...prev, [key]: true }));
      const result = await providersApi.checkHealth(providerId, modelId);
      const latency = Math.round(performance.now() - startTime);
      setHealthResults((prev) => ({
        ...prev,
        [key]: { healthy: result.healthy, error: result.error, latencyMs: latency },
      }));
    } catch (err: any) {
      const latency = Math.round(performance.now() - startTime);
      setHealthResults((prev) => ({
        ...prev,
        [key]: { healthy: false, error: err.message, latencyMs: latency },
      }));
    } finally {
      setTestingHealth((prev) => ({ ...prev, [key]: false }));
    }
  };

  const filteredProviders = useMemo(() => {
    if (!registryStatus) return [];
    return registryStatus.providers.filter((p) => {
      const matchesSearch =
        searchQuery === '' ||
        p.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.provider_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        p.model_id.toLowerCase().includes(searchQuery.toLowerCase());

      if (!matchesSearch) return false;

      if (filterType === 'local') return p.is_local;
      if (filterType === 'cloud') return !p.is_local;
      if (filterType === 'configured') return p.is_configured;
      return true;
    });
  }, [registryStatus, searchQuery, filterType]);

  return (
    <div>
      {/* ── Top Header Toolbar ─────────────────────────────────────────── */}
      <div style={{ marginBottom: '24px' }}>
        <h1
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: '1.75rem',
            fontWeight: 600,
            color: '#F0F3F6',
            letterSpacing: '-0.02em',
            marginBottom: '4px',
          }}
        >
          Capability registry &amp; model topology
        </h1>
        <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', maxWidth: '780px', lineHeight: 1.5 }}>
          Verified AI capabilities across local Ollama instances and frontier cloud providers. The router uses this registry
          for deterministic capability matching, token budgeting, and automatic fallback cascades.
        </p>
      </div>

      {/* ── Filter & Search Toolbar ─────────────────────────────────────── */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '12px',
          background: 'var(--bg-card)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-sm)',
          padding: '12px 16px',
          marginBottom: '20px',
        }}
      >
        {/* Search */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: '1', minWidth: '240px' }}>
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search models..."
            style={{
              background: 'transparent',
              border: 'none',
              color: '#F0F3F6',
              fontSize: '0.875rem',
              width: '100%',
            }}
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '2px 6px' }}
            >
              Clear
            </button>
          )}
        </div>

        {/* Filter Pills */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
          {[
            { id: 'all', label: 'All models' },
            { id: 'local', label: 'Local (Ollama)' },
            { id: 'cloud', label: 'Cloud providers' },
            { id: 'configured', label: 'Configured only' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterType(tab.id as any)}
              style={{
                fontSize: '0.8rem',
                fontWeight: 500,
                fontFamily: 'var(--font-mono)',
                padding: '4px 10px',
                borderRadius: 'var(--radius-xs)',
                background: filterType === tab.id ? 'rgba(245, 184, 65, 0.1)' : 'transparent',
                color: filterType === tab.id ? '#F5B841' : 'var(--text-muted)',
                border: filterType === tab.id ? '1px solid rgba(245, 184, 65, 0.28)' : '1px solid transparent',
                transition: 'background-color 0.15s ease, color 0.15s ease',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Model Count Indicator */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px', fontSize: '0.8rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
        <span>
          Showing {filteredProviders.length} of {registryStatus?.total_registered ?? 0} registered models
        </span>
      </div>

      {/* ── Providers List ──────────────────────────────────────────────── */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-muted)' }}>
          Loading capability registry...
        </div>
      ) : filteredProviders.length === 0 ? (
        <div
          style={{
            padding: '50px 24px',
            textAlign: 'center',
            background: 'var(--bg-card)',
            border: '1px dashed var(--border-subtle)',
            borderRadius: '8px',
          }}
        >
          <h3 style={{ fontSize: '1.1rem', color: '#F0F3F6', marginBottom: '6px' }}>
            No models match your search criteria
          </h3>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
            Try clearing the search query or selecting a different filter.
          </p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          {filteredProviders.map((p) => {
            const key = `${p.provider_id}:${p.model_id}`;
            const testResult = healthResults[key];
            const isTesting = testingHealth[key];

            return (
              <div
                key={key}
                style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                  padding: '18px 22px',
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  flexWrap: 'wrap',
                  gap: '16px',
                  transition: 'border-color 0.15s ease',
                }}
              >
                <div style={{ flex: '1', minWidth: '300px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px', flexWrap: 'wrap' }}>
                    <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#F0F3F6' }}>
                      {p.display_name}
                    </h3>
                    <span
                      style={{
                        fontSize: '0.72rem',
                        fontWeight: 500,
                        fontFamily: 'var(--font-mono)',
                        padding: '2px 6px',
                        borderRadius: 'var(--radius-xs)',
                        background: p.is_local ? 'rgba(64, 192, 87, 0.1)' : 'rgba(77, 171, 247, 0.1)',
                        color: p.is_local ? '#40C057' : '#4DABF7',
                        border: `1px solid ${p.is_local ? 'rgba(64, 192, 87, 0.24)' : 'rgba(77, 171, 247, 0.24)'}`,
                      }}
                    >
                      {p.is_local ? 'Local (zero cost)' : 'Cloud (API)'}
                    </span>
                    <span className={`badge ${p.is_configured ? 'badge-completed' : 'badge-failed'}`}>
                      {p.is_configured ? 'Configured' : 'Missing key'}
                    </span>
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      gap: '16px',
                      flexWrap: 'wrap',
                      fontSize: '0.8rem',
                      fontFamily: 'var(--font-mono)',
                      fontVariantNumeric: 'tabular-nums',
                      color: 'var(--text-muted)',
                      marginBottom: '10px',
                    }}
                  >
                    <span>ID: <strong style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{p.provider_id}:{p.model_id}</strong></span>
                    <span>Context: <strong style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{p.context_window_tokens.toLocaleString()} tokens</strong></span>
                    <span>Streaming: <strong style={{ color: 'var(--text-secondary)', fontWeight: 500 }}>{p.supports_streaming ? 'Yes' : 'No'}</strong></span>
                  </div>

                  <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {p.supported_task_types.map((type) => (
                      <span
                        key={type}
                        style={{
                          fontSize: '0.72rem',
                          fontFamily: 'var(--font-mono)',
                          background: 'rgba(255, 255, 255, 0.04)',
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-xs)',
                          color: 'var(--text-secondary)',
                          border: '1px solid rgba(255, 255, 255, 0.06)',
                        }}
                      >
                        {type}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Health Check Action & Results */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
                  <button
                    onClick={() => handleTestHealth(p.provider_id, p.model_id)}
                    disabled={isTesting}
                    className="btn-secondary"
                    style={{ padding: '6px 12px', fontSize: '0.8rem' }}
                  >
                    {isTesting ? 'Testing...' : 'Test health'}
                  </button>

                  {testResult && (
                    <div
                      style={{
                        fontSize: '0.75rem',
                        fontFamily: 'var(--font-mono)',
                        fontVariantNumeric: 'tabular-nums',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        color: testResult.healthy ? '#40C057' : '#FA5252',
                      }}
                    >
                      <span>{testResult.healthy ? '● Online' : '▲ Offline'}</span>
                      {testResult.latencyMs && <span>({testResult.latencyMs} ms)</span>}
                      {testResult.error && (
                        <span style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          &middot; {testResult.error}
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
