import type { CSSProperties } from 'react';

interface WelcomeScreenProps {
  onNavigate: (view: 'forms' | 'chat') => void;
}

const featureCard: CSSProperties = {
  background: 'rgba(0, 0, 0, 0.25)',
  border: '1px solid rgba(255, 255, 255, 0.08)',
  borderRadius: '16px',
  padding: '1.5rem',
};

export function WelcomeScreen({ onNavigate }: WelcomeScreenProps) {
  return (
    <main className="welcome-screen">
      <div className="welcome-card">
        <header className="welcome-heading">
          <span className="welcome-eyebrow">SmartAdvisor Academic Suite</span>
          <h1>Welcome to SmartAdvisor</h1>
          <p>
            Your intelligent companion for schedule conflict detection, course
            compatibility guidance, source-grounded answers, and academic overrides.
          </p>
        </header>

        <div className="welcome-features">
          <article style={featureCard}>
            <div className="welcome-feature-icon" aria-hidden="true">⚡</div>
            <h2>Forms &amp; Engine Suite</h2>
            <p>
              Build a real proposed schedule, detect conflicts, find alternatives,
              and run the compatibility engine against the local SmartAdvisor API.
            </p>
          </article>

          <article style={featureCard}>
            <div className="welcome-feature-icon" aria-hidden="true">💬</div>
            <h2>Conversational Assistant</h2>
            <p>
              Ask planning or policy questions, retain a bounded source session,
              inspect citations, and hand off override questions to the structured tool.
            </p>
          </article>
        </div>

        <aside className="welcome-disclaimer">
          <strong>Academic Disclaimer:</strong> SmartAdvisor is an assistive planning
          tool. Official registration and final override approvals remain subject to
          university policy.
        </aside>

        <div className="welcome-actions">
          <button type="button" className="welcome-primary" onClick={() => onNavigate('forms')}>
            Go to Forms &amp; Engines <span aria-hidden="true">→</span>
          </button>
          <button type="button" className="welcome-secondary" onClick={() => onNavigate('chat')}>
            Open SmartAdvisor Chat <span aria-hidden="true">💬</span>
          </button>
        </div>
      </div>
    </main>
  );
}
