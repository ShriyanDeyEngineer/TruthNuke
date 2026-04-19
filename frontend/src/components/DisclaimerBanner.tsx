import React from 'react';

/**
 * DisclaimerBanner displays a persistent disclaimer about automated assessments.
 *
 * Default text: "This analysis is an automated assessment and not a definitive
 * judgment of truth. Please review the referenced sources to form your own
 * conclusions."
 *
 * Requirements: 11.1
 */

interface DisclaimerBannerProps {
  /** Disclaimer text from the API response */
  disclaimer?: string;
}

const DEFAULT_DISCLAIMER =
  'This analysis is an automated assessment and not a definitive judgment of truth. Please review the referenced sources to form your own conclusions.';

const DisclaimerBanner: React.FC<DisclaimerBannerProps> = ({
  disclaimer = DEFAULT_DISCLAIMER,
}) => {
  return (
    <div
      role="note"
      aria-label="Disclaimer"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.5rem',
        padding: '0.75rem 1rem',
        backgroundColor: '#f0fdf4',
        border: '1px solid #bbf7d0',
        borderRadius: '0.5rem',
        fontSize: '0.8rem',
        lineHeight: 1.5,
        color: '#166534',
      }}
    >
      <span aria-hidden="true" style={{ flexShrink: 0 }}>ℹ️</span>
      <p style={{ margin: 0 }}>{disclaimer}</p>
    </div>
  );
};

export default DisclaimerBanner;
