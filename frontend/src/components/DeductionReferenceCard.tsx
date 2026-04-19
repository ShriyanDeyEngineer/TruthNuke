import React from 'react';
import type { DeductionReference, NoCorroborationDeduction } from '@/types/api';
import { isDeductionReference } from '@/types/api';

/**
 * DeductionReferenceCard shows source name, summary, contradiction rationale,
 * and a clickable link that opens in a new tab.
 *
 * Also handles NoCorroborationDeduction display distinctly.
 *
 * Requirements: 28.5, 28.6, 28.7, 28.8
 */

interface DeductionReferenceCardProps {
  deduction: DeductionReference | NoCorroborationDeduction;
}

const DeductionReferenceCard: React.FC<DeductionReferenceCardProps> = ({ deduction }) => {
  if (isDeductionReference(deduction)) {
    return (
      <div
        style={{
          padding: '0.75rem',
          backgroundColor: '#fef2f2',
          border: '1px solid #fecaca',
          borderRadius: '0.5rem',
          fontSize: '0.8rem',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.375rem' }}>
          <span style={{ fontWeight: 600, color: '#991b1b' }}>
            {deduction.source_name}
          </span>
          <a
            href={deduction.url}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              fontSize: '0.7rem',
              color: '#2563eb',
              textDecoration: 'underline',
              flexShrink: 0,
              marginLeft: '0.5rem',
            }}
          >
            View source ↗
          </a>
        </div>
        <p style={{ color: '#4b5563', margin: '0 0 0.375rem 0', lineHeight: 1.5 }}>
          {deduction.summary}
        </p>
        <p style={{ color: '#991b1b', margin: 0, lineHeight: 1.5, fontStyle: 'italic' }}>
          {deduction.contradiction_rationale}
        </p>
      </div>
    );
  }

  // NoCorroborationDeduction
  return (
    <div
      style={{
        padding: '0.75rem',
        backgroundColor: '#fffbeb',
        border: '1px solid #fde68a',
        borderRadius: '0.5rem',
        fontSize: '0.8rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.375rem', marginBottom: '0.25rem' }}>
        <span aria-hidden="true">⚠️</span>
        <span style={{ fontWeight: 600, color: '#92400e' }}>No corroborating evidence</span>
      </div>
      <p style={{ color: '#78350f', margin: 0, lineHeight: 1.5 }}>
        {deduction.rationale}
      </p>
    </div>
  );
};

export default DeductionReferenceCard;
