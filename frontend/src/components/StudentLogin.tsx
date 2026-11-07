
import { useState, type FormEvent } from 'react';

interface StudentLoginProps {
  onLogin: () => void;
}

const STUDENT_EMAIL = 'student@fau.edu';
const STUDENT_PASSWORD = 'password';

export default function StudentLogin({ onLogin }: StudentLoginProps) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (
      email.trim().toLowerCase() === STUDENT_EMAIL &&
      password === STUDENT_PASSWORD
    ) {
      setError('');
      onLogin();
    } else {
      setError('Incorrect email or password.');
    }
  };

  return (
    <main style={{
      minHeight: '100vh',
      backgroundColor: '#f1f5f9',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      padding: '24px'
    }}>
      <div style={{
        width: '100%',
        maxWidth: '420px',
        padding: '36px',
        backgroundColor: '#ffffff',
        borderRadius: '14px',
        boxShadow: '0 8px 30px rgba(15,23,42,0.1)'
      }}>
        <h1 style={{
          color: '#17365d',
          marginBottom: '8px'
        }}>
          SmartAdvisor
        </h1>

        <p style={{
          color: '#64748b',
          marginBottom: '28px'
        }}>
          Student Login
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="student-email">
            School Email
          </label>

          <input
            id="student-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="student@fau.edu"
            required
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '12px',
              marginTop: '8px',
              marginBottom: '20px',
              border: '1px solid #cbd5e1',
              borderRadius: '8px'
            }}
          />

          <label htmlFor="student-password">
            Password
          </label>

          <input
            id="student-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            required
            style={{
              width: '100%',
              boxSizing: 'border-box',
              padding: '12px',
              marginTop: '8px',
              marginBottom: '20px',
              border: '1px solid #cbd5e1',
              borderRadius: '8px'
            }}
          />

          {error && (
            <p role="alert" style={{
              color: '#dc2626',
              fontSize: '14px'
            }}>
              {error}
            </p>
          )}

          <button type="submit" style={{
            width: '100%',
            padding: '13px',
            backgroundColor: '#17365d',
            color: '#ffffff',
            border: 'none',
            borderRadius: '8px',
            fontWeight: 600,
            cursor: 'pointer'
          }}>
            Log In to SmartAdvisor
          </button>
        </form>
      </div>
    </main>
  );
}
