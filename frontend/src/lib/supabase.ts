
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseKey = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY;

export const supabaseConfigured = Boolean(supabaseUrl && supabaseKey);

// Home, Forms, and Chatbot are usable without account persistence. A local,
// non-routable client keeps the shared component imports stable while auth and
// semester-history controls remain disabled until real public config is built.
export const supabase = createClient(
  supabaseUrl || 'http://127.0.0.1:9',
  supabaseKey || 'smartadvisor-unconfigured-publishable-key',
  {
    auth: {
      persistSession: supabaseConfigured,
      autoRefreshToken: supabaseConfigured,
      detectSessionInUrl: supabaseConfigured,
    },
  },
);
