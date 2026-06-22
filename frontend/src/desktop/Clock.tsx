// Live taskbar clock (HH:MM:SS), updates each second.

import { useEffect, useState } from 'react';

function fmt(d: Date): string {
  return d.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

export function Clock() {
  const [now, setNow] = useState(() => fmt(new Date()));
  useEffect(() => {
    const id = setInterval(() => setNow(fmt(new Date())), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <time
      className="pixel-inset rounded-pixel bg-bg px-2 py-1 font-mono text-xs tabular-nums text-neon"
      aria-label="Current time"
    >
      {now}
    </time>
  );
}
