import React from 'react';
import type { ClassificationLabel, TrustScoreBreakdown } from '@/types/api';

/**
 * TrustScoreMeter displays a color-coded gauge with the trust score
 * and classification badge.
 *
 * Color coding:
 * - Green (70–100): Likely reliable
 * - Yellow (40–69): Use caution
 * - Red (0–39): Likely unreliable
 *
 * Requirements: 10.1, 10.5
 */

interface TrustScoreMeterProps {
  /** Trust score 0–100 */
  score: number;
  /** Overall classification label */
  classification: ClassificationLabel | string;
  /** Optional breakdown of sub-scores */
  breakdown?: TrustScoreBreakdown | null;
}

function getScoreColor(score: number): string {
  if (score >= 70) return '#16a34a'; // green
  if (score >= 40) return '#ca8a04'; // yellow
  return '#dc2626'; // red
}

function getScoreLabel(score: number): string {
  if (score >= 70) return 'Likely reliable';
  if (score >= 40) return 'Use caution';
  return 'Likely unreliable';
}

function getClassificationColor(label: string): string {
  switch (label) {
    case 'VERIFIED':
      return '#16a34a';
    case 'MISLEADING':
      return '#ca8a04';
    case 'LIKELY_FALSE':
      return '#dc2626';
    case 'HARMFUL':
      return '#7c2d12';
    default:
      return '#6b7280';
  }
}

function formatClassificationLabel(label: string): string {
  return label.replace(/_/g, ' ');
}

const TrustScoreMeter: React.FC<TrustScoreMeterProps> = ({
  score,
  classification,
  breakdown,
}) => {
  const color = getScoreColor(score);
  const label = getScoreLabel(score);
  const classColor = getClassificationColor(classification);
  // Gauge fill percentage
  const fillPercent = Math.max(0, Math.min(100, score));

  return (
    <div
      aria-label={`Trust score: ${score} out of 100, ${label}`}
      style={{
        padding: '1.5rem',
        backgroundColor: '#f9fafb',
        borderRadius: '0.75rem',
        border: '1px solid #e5e7eb',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', marginBottom: '1rem' }}>
        <h2 style={{ fontSize: '1.125rem', fontWeight: 600, color: '#111827', margin: 0 }}>
          Trust Score
        </h2>
        <span
          style={{
            display: 'inline-block',
            padding: '0.25rem 0.75rem',
            fontSize: '0.75rem',
            fontWeight: 700,
            color: '#fff',
            backgroundColor: classColor,
            borderRadius: '9999px',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}
        >
          {formatClassificationLabel(classification)}
        </span>
      </div>

      {/* Score display */}
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginBottom: '0.75rem' }}>
        <span style={{ fontSize: '3rem', fontWeight: 700, color, lineHeight: 1 }}>
          {score}
        </span>
        <span style={{ fontSize: '1.25rem', color: '#9ca3af' }}>/100</span>
        <span style={{ fontSize: '0.875rem', color, marginLeft: '0.5rem' }}>{label}</span>
      </div>

      {/* Gauge bar */}
      <div
        style={{
          width: '100%',
          height: '8px',
          backgroundColor: '#e5e7eb',
          borderRadius: '4px',
          overflow: 'hidden',
          marginBottom: breakdown ? '1rem' : 0,
        }}
        role="progressbar"
        aria-valuenow={score}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={`Trust score gauge: ${score}%`}
      >
        <div
          style={{
            width: `${fillPercent}%`,
            height: '100%',
            backgroundColor: color,
            borderRadius: '4px',
            transition: 'width 0.5s ease',
          }}
        />
      </div>

      {/* Sub-score breakdown */}
      {breakdown && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
          {([
            ['Source Credibility', breakdown.source_credibility],
            ['Evidence Strength', breakdown.evidence_strength],
            ['Language Neutrality', breakdown.language_neutrality],
            ['Cross-Source Agreement', breakdown.cross_source_agreement],
          ] as [string, number][]).map(([name, value]) => (
            <div key={name} style={{ fontSize: '0.75rem', color: '#6b7280' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
                <span>{name}</span>
                <span style={{ fontWeight: 600, color: getScoreColor(value) }}>{value}</span>
              </div>
              <div
                style={{
                  width: '100%',
                  height: '4px',
                  backgroundColor: '#e5e7eb',
                  borderRadius: '2px',
                  overflow: 'hidden',
                }}
              >
                <div
                  style={{
                    width: `${value}%`,
                    height: '100%',
                    backgroundColor: getScoreColor(value),
                    borderRadius: '2px',
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TrustScoreMeter;
