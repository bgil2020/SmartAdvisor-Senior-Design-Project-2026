export type AppView = 'welcome' | 'forms' | 'chat';

const VIEW_PATHS: Record<AppView, string> = {
  welcome: '/',
  forms: '/forms',
  chat: '/chatbot',
};

export function viewFromPath(pathname: string): AppView {
  const normalized = `/${pathname.split(/[?#]/, 1)[0].replace(/^\/+|\/+$/g, '').toLowerCase()}`;

  if (normalized === '/forms') return 'forms';
  if (normalized === '/chat' || normalized === '/chatbot') return 'chat';
  return 'welcome';
}

export function pathForView(view: AppView): string {
  return VIEW_PATHS[view];
}
