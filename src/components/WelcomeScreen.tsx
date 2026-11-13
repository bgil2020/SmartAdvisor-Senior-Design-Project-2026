import React from 'react';

interface WelcomeScreenProps {
  onNavigate: (view: 'forms' | 'chat') => void;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({ onNavigate }) => {
  return (
    <div style={{
      minHeight: '100vh',
      background: 'linear-gradient(135deg, #0f172a 0%, #1e3a8a 50%, #0f172a 100%)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '2rem',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      color: '#ffffff'
    }}>
      <div style={{
        maxWidth: '750px',
        width: '100%',
        background: 'rgba(255, 255, 255, 0.05)',
        backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255, 255, 255, 0.15)',
        borderRadius: '24px',
        boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
        padding: '3rem 2.5rem',
        boxSizing: 'border-box'
      }}>
        
        {/* Header / Brand */}
        <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
          <span style={{
            display: 'inline-block',
            padding: '0.35rem 1rem',
            background: 'rgba(59, 130, 246, 0.2)',
            border: '1px solid rgba(96, 165, 250, 0.4)',
            color: '#93c5fd',
            borderRadius: '50px',
            fontSize: '0.75rem',
            fontWeight: '700',
            letterSpacing: '0.05em',
            textTransform: 'uppercase',
            marginBottom: '1rem'
          }}>
            SmartAdvisor Academic Suite
          </span>
          <h1 style={{
            fontSize: '2.75rem',
            fontWeight: '800',
            letterSpacing: '-0.025em',
            margin: '0 0 1rem 0',
            color: '#ffffff'
          }}>
            Welcome to SmartAdvisor
          </h1>
          <p style={{
            color: '#94a3b8',
            fontSize: '1.05rem',
            lineHeight: '1.6',
            maxWidth: '560px',
            margin: '0 auto'
          }}>
            Your intelligent companion for automated schedule conflict detection, prerequisite verification, and streamlined academic overrides.
          </p>
        </div>

        {/* Feature Cards Grid */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))',
          gap: '1.25rem',
          marginBottom: '2rem'
        }}>
          <div style={{
            background: 'rgba(0, 0, 0, 0.25)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '1.5rem',
            transition: 'transform 0.2s ease'
          }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>⚡</div>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#60a5fa', margin: '0 0 0.5rem 0' }}>
              Form & Engine Suite
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.5', margin: 0 }}>
              Input your major, modality, and course selections into our multi-engine system to run live risk scoring and alternative lookups.
            </p>
          </div>

          <div style={{
            background: 'rgba(0, 0, 0, 0.25)',
            border: '1px solid rgba(255, 255, 255, 0.08)',
            borderRadius: '16px',
            padding: '1.5rem'
          }}>
            <div style={{ fontSize: '1.5rem', marginBottom: '0.75rem' }}>💬</div>
            <h3 style={{ fontSize: '1rem', fontWeight: '700', color: '#60a5fa', margin: '0 0 0.5rem 0' }}>
              Conversational Assistant
            </h3>
            <p style={{ fontSize: '0.85rem', color: '#cbd5e1', lineHeight: '1.5', margin: 0 }}>
              Ask natural-language questions about schedule overlaps, policy guidelines, or graduation tracks in a ChatGPT-style interface.
            </p>
          </div>
        </div>

        {/* Academic Disclaimer */}
        <div style={{
          background: 'rgba(245, 158, 11, 0.1)',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          borderRadius: '12px',
          padding: '1rem 1.25rem',
          fontSize: '0.8rem',
          color: '#fde68a',
          lineHeight: '1.5',
          marginBottom: '2.5rem'
        }}>
          <strong style={{ color: '#fef3c7', fontWeight: '700' }}>Academic Disclaimer:</strong> SmartAdvisor is an assistive planning tool. Official course registration and final override approvals remain subject to university policy.
        </div>

        {/* Action Buttons */}
        <div style={{
          display: 'flex',
          gap: '1rem',
          flexWrap: 'wrap'
        }}>
          <button
            onClick={() => onNavigate('forms')}
            style={{
              flex: 1,
              minWidth: '220px',
              padding: '1rem 1.5rem',
              background: '#2563eb',
              color: '#ffffff',
              border: 'none',
              borderRadius: '12px',
              fontSize: '0.95rem',
              fontWeight: '700',
              cursor: 'pointer',
              boxShadow: '0 10px 15px -3px rgba(37, 99, 235,.4)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              transition: 'background 0.2s ease'
            }}
            onMouseOver={(e) => e.currentTarget.style.background = '#1d4ed8'}
            onMouseOut={(e) => e.currentTarget.style.background = '#2563eb'}
          >
            <span>Go to Forms & Engines</span>
            <span>→</span>
          </button>

          <button
            onClick={() => onNavigate('chat')}
            style={{
              flex: 1,
              minWidth: '220px',
              padding: '1rem 1.5rem',
              background: 'rgba(255, 255, 255, 0.1)',
              color: '#ffffff',
              border: '1px solid rgba(255, 255, 255, 0.2)',
              borderRadius: '12px',
              fontSize: '0.95rem',
              fontWeight: '700',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              transition: 'background 0.2s ease'
            }}
            onMouseOver={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)'}
            onMouseOut={(e) => e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)'}
          >
            <span>Open SmartAdvisor Chat</span>
            <span>💬</span>
          </button>
        </div>

      </div>
    </div>
  );
};