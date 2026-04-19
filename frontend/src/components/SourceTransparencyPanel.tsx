import React from 'react';
import type { ClaimAnalysis } from '@/types/api';
import DeductionReferenceCard from './DeductionReferenceCard';

/**
 * SourceTransparencyPanel groups DeductionReferences under their
 * corresponding Claims. Does not display a section for claims with
 * no deductions.
 *
 * Requirements: 28.5, 28.6, 28.7, 28.8
 */

interface SourceTransparencyPanelProps {
  /** Analyzed claims with their deduction references */
  claims: ClaimAnalysis[];
}

const SourceTransparencyPanel: React.FC<SourceTransparencyPanelProps> = ({ claims }) => {
  // Filter to claims that have deductions
  const claimsWithDeductions = claims.filter(
    (ca) => ca.deduction_references && ca.deduction_references.length > 0
  );

  if (claimsWithDeductions.length === 0) return null;

  return (
    <div
      style={{
        padding: '1.25rem',
        backgroundColor: '#fff',
        border: '1px solid #e5e7eb',
        borderRadius: '0.75rem',
      }}
    >
      <h2
        style={{
          fontSize: '1rem',
          fontWeight: 600,
          color: '#111827',
          marginBottom: '1rem',
        }}
      >
        Source Transparency
      </h2>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {claimsWithDeductions.map((ca, index) => (
          <div key={ca.claim.id || index}>
            <h3
              style={{
                fontSize: '0.8rem',
                fontWeight: 600,
                color: '#374151',
                marginBottom: '0.5rem',
                padding: '0.375rem 0.5rem',
                backgroundColor: '#f3f4f6',
                borderRadius: '0.375rem',
              }}
            >
              Claim: &ldquo;{ca.claim.text.length > 80
                ? ca.claim.text.slice(0, 80) + '...'
                : ca.claim.text}&rdquo;
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {ca.deduction_references.map((deduction, dIdx) => (
                <DeductionReferenceCard key={dIdx} deduction={deduction} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default SourceTransparencyPanel;
