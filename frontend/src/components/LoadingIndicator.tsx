import React from 'react';

/**
 * LoadingIndicator component shown during analysis.
 *
 * Displays a spinner and status message while the API request is in progress.
 *
 * Requirements: 9.3
 */

interface LoadingIndicatorProps {
  /** Optional message to display alongside the spinner */
  message?: string;
}

const LoadingIndicator: React.FC<LoadingIndicatorProps> = ({
  message = 'Analyzing content for misinformation...',
}) => {
  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '2rem',
        gap: '1rem',
      }}
    >
      <div
        style={{
          width: '40px',
          height: '40px',
          border: '3px solid #e5e7eb',
          borderTopColor: '#2563eb',
          borderRadius: '50%',
          animation: 'spin 0.8s linear infinite',
        }}
        aria-hidden="true"
      />
      <p
        style={{
          fontSize: '0.875rem',
          color: '#6b7280',
          textAlign: 'center',
        }}
      >
        {message}
      </p>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default LoadingIndicator;
