// The four metric cards for a completed validation run, each with a per-metric
// color grade (spec §8.2). Determinism is a %; the rest are 0–10 — hallucination
// is explicitly labelled "lower is better" since it inverts the usual reading.

import { ColorDot } from '@/components/ColorDot';
import { StatCard } from '@/components/StatCard';
import {
  gradeComprehension,
  gradeDeterminism,
  gradeHallucination,
} from '@/lib/quality';
import type { ValidationRun } from '@/lib/types';

export function MetricCards({ run }: { run: ValidationRun }) {
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      <Card
        label="Determinism"
        value={`${Math.round(run.determinism)}%`}
        color={gradeDeterminism(run.determinism)}
        hint="answer stability across repeats"
      />
      <Card
        label="Comprehension"
        value={`${run.comprehension.toFixed(1)}/10`}
        color={gradeComprehension(run.comprehension)}
        hint="judge score · higher is better"
      />
      <Card
        label="Hallucination"
        value={`${run.hallucination.toFixed(1)}/10`}
        color={gradeHallucination(run.hallucination)}
        hint="lower is better"
        warn
      />
      <Card
        label="Latency"
        value={`${run.latency_ms} ms`}
        hint="per response"
      />
    </div>
  );
}

interface CardProps {
  label: string;
  value: string;
  color?: ReturnType<typeof gradeComprehension>;
  hint: string;
  warn?: boolean;
}

function Card({ label, value, color, hint, warn }: CardProps) {
  return (
    <StatCard
      label={label}
      value={value}
      dot={color && <ColorDot color={color} metric={label} />}
      hint={hint}
      hintClassName={warn ? 'text-orange' : 'text-ink-dim/70'}
    />
  );
}
