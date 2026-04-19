import React from 'react';

/**
 * ExplanationPanel renders the natural-language explanation of the analysis.
 *
 * Requirements: 10.2
 */

interface ExplanationPanelProps {
  /** The explanation text from the analysis response */
  explanation: string;
}

const ExplanationPanel: React.FC<ExplanationPanelProps> = ({ explanation }) => {
  return (
    <div
      style={{
        padding: '1.25rem',
        backgroundColor: '#f0f9ff',
        border: '1px solid #bae6fd',
        borderRadius: '0.75rem',
      }}
    >
      <h2
        style={{
          fontSize: '1rem',
          fontWeight: 600,
          color: '#0c4a6e',
          marginBottom: '0.75rem',
        }}
      >
        Analysis Explanation
      </h2>
      <p
        style={{
          fontSize: '0.875rem',
          lineHeight: 1.7,
          color: '#1e3a5f',
          margin: 0,
          whiteSpace: 'pre-wrap',
        }}
      >
        {explanation}
      </p>
    </div>
  );
};

export default ExplanationPanel;
