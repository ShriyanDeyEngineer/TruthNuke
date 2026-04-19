import React from 'react';

/**
 * SubmitButton component that triggers the POST /analyze request.
 *
 * Requirements: 9.2
 */

interface SubmitButtonProps {
  /** Click handler to trigger analysis */
  onClick: () => void;
  /** Whether the button is disabled */
  disabled?: boolean;
  /** Whether analysis is currently in progress */
  loading?: boolean;
}

const SubmitButton: React.FC<SubmitButtonProps> = ({
  onClick,
  disabled = false,
  loading = false,
}) => {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled || loading}
      aria-busy={loading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        padding: '0.75rem 1.5rem',
        fontSize: '1rem',
        fontWeight: 600,
        color: '#fff',
        backgroundColor: disabled || loading ? '#9ca3af' : '#2563eb',
        border: 'none',
        borderRadius: '0.5rem',
        cursor: disabled || loading ? 'not-allowed' : 'pointer',
        transition: 'background-color 0.15s ease',
        minWidth: '140px',
      }}
      onMouseEnter={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.backgroundColor = '#1d4ed8';
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled && !loading) {
          e.currentTarget.style.backgroundColor = '#2563eb';
        }
      }}
    >
      {loading ? 'Analyzing...' : 'Analyze'}
    </button>
  );
};

export default SubmitButton;
