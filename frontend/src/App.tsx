// App root: boot the auth store, then render the auth gate or the desktop.

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { AuthGate } from '@/windows/AuthGate';
import { Desktop } from '@/desktop/Desktop';

export function App() {
  const status = useAuthStore((s) => s.status);
  const hydrate = useAuthStore((s) => s.hydrate);

  useEffect(() => {
    void hydrate();
  }, [hydrate]);

  if (status === 'booting') {
    return (
      <div className="flex h-full w-full items-center justify-center bg-bg">
        <span className="caret font-mono text-sm uppercase tracking-widest text-neon-dim">
          booting promptgate
        </span>
      </div>
    );
  }

  return status === 'authenticated' ? <Desktop /> : <AuthGate />;
}
