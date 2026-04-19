import React from 'react';
import type { Claim } from '@/types/api';

/**
 * RiskyPhraseHighlighter highlights extracted claims in the original text
 * using start_index and end_index from each Claim.
 *
 * Requirements: 10.3
 */

interface RiskyPhraseHighlighterProps {
  /** The original input text */
  originalText: string;
  /** Claims extracted from the text */
  claims: Claim[];
}

interface TextSegment {
  text: string;
  highlighted: boolean;
  claimIndex?: number;
}

/**
 * Build non-overlapping segments from claims, sorted by start_index.
 */
function buildSegments(text: string, claims: Claim[]): TextSegment[] {
  if (claims.length === 0) {
    return [{ text, highlighted: false }];
  }

  // Sort claims by start_index, filter to valid ranges
  const sorted = claims
    .map((c, i) => ({ ...c, claimIndex: i }))
    .filter((c) => c.start_index >= 0 && c.end_index <= text.length && c.start_index < c.end_index)
    .sort((a, b) => a.start_index - b.start_index);

  const segments: TextSegment[] = [];
  let cursor = 0;

  for (const claim of sorted) {
    // Skip overlapping claims
    if (claim.start_index < cursor) continue;

    // Add non-highlighted text before this claim
    if (claim.start_index > cursor) {
      segments.push({
        text: text.slice(cursor, claim.start_index),
        highlighted: false,
      });
    }

    // Add highlighted claim text
    segments.push({
      text: text.slice(claim.start_index, claim.end_index),
      highlighted: true,
      claimIndex: claim.claimIndex,
    });

    cursor = claim.end_index;
  }

  // Add remaining text after last claim
  if (cursor < text.length) {
    segments.push({
      text: text.slice(cursor),
      highlighted: false,
    });
  }

  return segments;
}

const HIGHLIGHT_COLORS = [
  'rgba(239, 68, 68, 0.15)',  // red
  'rgba(245, 158, 11, 0.15)', // amber
  'rgba(168, 85, 247, 0.15)', // purple
  'rgba(14, 165, 233, 0.15)', // sky
  'rgba(34, 197, 94, 0.15)',  // green
];

const BORDER_COLORS = [
  'rgba(239, 68, 68, 0.5)',
  'rgba(245, 158, 11, 0.5)',
  'rgba(168, 85, 247, 0.5)',
  'rgba(14, 165, 233, 0.5)',
  'rgba(34, 197, 94, 0.5)',
];

const RiskyPhraseHighlighter: React.FC<RiskyPhraseHighlighterProps> = ({
  originalText,
  claims,
}) => {
  const segments = buildSegments(originalText, claims);

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
          marginBottom: '0.75rem',
        }}
      >
        Highlighted Claims
      </h2>
      <div
        style={{
          fontSize: '0.875rem',
          lineHeight: 1.8,
          color: '#374151',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}
      >
        {segments.map((seg, i) =>
          seg.highlighted ? (
            <mark
              key={i}
              title={`Claim ${(seg.claimIndex ?? 0) + 1}`}
              style={{
                backgroundColor: HIGHLIGHT_COLORS[(seg.claimIndex ?? 0) % HIGHLIGHT_COLORS.length],
                borderBottom: `2px solid ${BORDER_COLORS[(seg.claimIndex ?? 0) % BORDER_COLORS.length]}`,
                padding: '0.1rem 0.15rem',
                borderRadius: '2px',
              }}
            >
              {seg.text}
            </mark>
          ) : (
            <span key={i}>{seg.text}</span>
          )
        )}
      </div>
    </div>
  );
};

export default RiskyPhraseHighlighter;
