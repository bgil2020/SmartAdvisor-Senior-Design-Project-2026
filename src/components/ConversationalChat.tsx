import React, { useState } from 'react';

interface Message {
  sender: 'user' | 'bot';
  text: string;
}

export const ConversationalChat: React.FC = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    { sender: 'bot', text: 'Hello! I am your SmartAdvisor assistant. Ask me about course schedules, conflicts, or overrides.' }
  ]);
  const [loading, setLoading] = useState(false);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { sender: 'user', text: userMsg }]);
    setLoading(true);

    try {
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: userMsg }),
      });

      if (!response.ok) {
        throw new Error('Failed to reach conversational service.');
      }

      const data = await response.json();
      setMessages((prev) => [...prev, { sender: 'bot', text: data.reply || 'Here are the details for your request.' }]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { 
          sender: 'bot', 
          text: `[Fallback Response] I received your message: "${userMsg}". (Ensure your backend chat endpoint is running, or check your schedule conflict results above!)` 
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '1.5rem', backgroundColor: '#ffffff', borderRadius: '8px', border: '1px solid #e5e7eb', marginTop: '1.5rem' }}>
      <h3 style={{ fontSize: '1.25rem', fontWeight: 'bold', marginBottom: '1rem' }}>
        SmartAdvisor Assistant Chat
      </h3>
      
      <div style={{ height: '180px', overflowY: 'auto', border: '1px solid #e5e7eb', padding: '0.75rem', borderRadius: '4px', backgroundColor: '#f9fafb', marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
        {messages.map((m, idx) => (
          <div key={idx} style={{ padding: '0.5rem', borderRadius: '4px', fontSize: '0.875rem', backgroundColor: m.sender === 'user' ? '#eff6ff' : '#f3f4f6', color: m.sender === 'user' ? '#1e40af' : '#1f2937', alignSelf: m.sender === 'user' ? 'flex-end' : 'flex-start', maxWidth: '80%' }}>
            <strong>{m.sender === 'user' ? 'You: ' : 'Advisor: '}</strong>
            {m.text}
          </div>
        ))}
        {loading && (
          <div style={{ color: '#6b7280', fontStyle: 'italic', fontSize: '0.75rem' }}>Assistant is typing...</div>
        )}
      </div>

      <form onSubmit={handleSendMessage} style={{ display: 'flex', gap: '0.5rem' }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question (e.g., 'Do I have a conflict with CS 101?')..."
          style={{ flex: 1, padding: '0.5rem', border: '1px solid #d1d5db', borderRadius: '4px', fontSize: '0.875rem' }}
        />
        <button
          type="submit"
          disabled={loading}
          style={{ padding: '0.5rem 1rem', backgroundColor: '#2563eb', color: '#fff', border: 'none', borderRadius: '4px', fontWeight: 'bold', cursor: 'pointer', fontSize: '0.875rem' }}
        >
          Send
        </button>
      </form>
    </div>
  );
};