
import { useState, type FormEvent } from 'react';
import { supabase } from '../lib/supabase';

interface StudentLoginProps {
  onLogin: (name: string) => void;
}

const inputStyle = {
  width: '100%',
  boxSizing: 'border-box' as const,
  padding: '12px',
  fontSize: '16px',
  border: '1px solid #cbd5e1',
  borderRadius: '8px'
};

export default function StudentLogin({ onLogin }: StudentLoginProps) {
  const [isRegistering, setIsRegistering] = useState(false);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setLoading(true);

    try {
      if (isRegistering) {
        if (!name.trim()) {
          setError('Please enter your full name.');
          return;
        }

        const { data, error: signUpError } = await supabase.auth.signUp({
          email: email.trim(),
          password,
          options: {
            data: {
              full_name: name.trim()
            }
          }
        });

        if (signUpError) throw signUpError;

        if (data.session && data.user) {
          onLogin(
            String(data.user.user_metadata?.full_name || name.trim())
          );
        } else {
          setMessage(
            'Account created. Check your email to confirm your account, then log in.'
          );
        }
      } else {
        const { data, error: signInError } =
          await supabase.auth.signInWithPassword({
            email: email.trim(),
            password
          });

        if (signInError) throw signInError;

        onLogin(
          String(data.user.user_metadata?.full_name || 'Student')
        );
      }
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Something went wrong.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main
      style={{
        minHeight: '100vh',
        backgroundColor: '#f1f5f9',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        padding: '24px',
        boxSizing: 'border-box'
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '420px',
          padding: '36px',
          boxSizing: 'border-box',
          backgroundColor: '#ffffff',
          borderRadius: '14px',
          boxShadow: '0 8px 30px rgba(15,23,42,0.1)'
        }}
      >
        <h1
          style={{
            color: '#17365d',
            textAlign: 'center',
            marginBottom: '8px'
          }}
        >
          SmartAdvisor
        </h1>

        <p
          style={{
            color: '#64748b',
            textAlign: 'center',
            marginBottom: '28px'
          }}
        >
          {isRegistering ? 'Create Your Account' : 'Student Login'}
        </p>

        <form
          onSubmit={handleSubmit}
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '10px',
            textAlign: 'left'
          }}
        >
          {isRegistering && (
            <>
              <label htmlFor="student-name">
                Full Name
              </label>

              <input
                id="student-name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Enter your full name"
                autoComplete="name"
                required
                style={inputStyle}
              />
            </>
          )}

          <label htmlFor="student-email">
            Email Address
          </label>

          <input
            id="student-email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="Enter your email"
            autoComplete="email"
            required
            style={inputStyle}
          />

          <label htmlFor="student-password">
            Password
          </label>

          <input
            id="student-password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder={
              isRegistering
                ? 'Create a password'
                : 'Enter your password'
            }
            autoComplete={
              isRegistering
                ? 'new-password'
                : 'current-password'
            }
            minLength={6}
            required
            style={inputStyle}
          />

          {error && (
            <p
              role="alert"
              style={{
                color: '#dc2626',
                fontSize: '14px'
              }}
            >
              {error}
            </p>
          )}

          {message && (
            <p
              role="status"
              style={{
                color: '#166534',
                fontSize: '14px'
              }}
            >
              {message}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              padding: '13px',
              marginTop: '16px',
              backgroundColor: '#17365d',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              fontWeight: 600,
              fontSize: '16px',
              cursor: loading ? 'wait' : 'pointer',
              opacity: loading ? 0.7 : 1
            }}
          >
            {loading
              ? 'Please wait...'
              : isRegistering
                ? 'Create Account'
                : 'Log In'}
          </button>
        </form>

        <button
          type="button"
          onClick={() => {
            setIsRegistering(!isRegistering);
            setError('');
            setMessage('');
            setPassword('');
          }}
          style={{
            width: '100%',
            marginTop: '18px',
            padding: '8px',
            background: 'none',
            border: 'none',
            color: '#17365d',
            fontSize: '14px',
            cursor: 'pointer'
          }}
        >
          {isRegistering
            ? 'Already have an account? Log In'
            : "Don't have an account? Register"}
        </button>
      </div>
    </main>
  );
}
