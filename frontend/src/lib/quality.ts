// Quality color-grading helpers (spec §8.2).
//
//   🟢 green  — score ≥ 8.0  AND  hallucination < 1.5
//   🟡 yellow — score 6.0–7.9  OR  hallucination 1.5–3.5
//   🔴 red    — score < 6.0    OR  hallucination > 3.5
//
// The backend returns an authoritative `color` per run/score; these helpers are
// for per-metric grading of individual cards (where there's no server color)
// and as a local fallback when one is absent.

import type { ValidationColor } from './types';

/** Grade a (comprehension score, hallucination) pair into a traffic light. */
export function gradeQuality(
  score: number,
  hallucination: number,
): ValidationColor {
  if (score >= 8.0 && hallucination < 1.5) return 'green';
  if (score < 6.0 || hallucination > 3.5) return 'red';
  return 'yellow';
}

/** Comprehension on its own (0–10, higher better). */
export function gradeComprehension(score: number): ValidationColor {
  if (score >= 8.0) return 'green';
  if (score < 6.0) return 'red';
  return 'yellow';
}

/** Hallucination on its own (0–10, LOWER better). */
export function gradeHallucination(hallucination: number): ValidationColor {
  if (hallucination < 1.5) return 'green';
  if (hallucination > 3.5) return 'red';
  return 'yellow';
}

/** Determinism on its own (0–100%, higher better). */
export function gradeDeterminism(determinism: number): ValidationColor {
  if (determinism >= 80) return 'green';
  if (determinism < 50) return 'red';
  return 'yellow';
}
