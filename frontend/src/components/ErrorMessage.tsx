import React from 'react';

/**
 * ErrorMessage component for displaying user-friendly error messages.
 *
 * Maps API error status codes to helpful messages.
 *
 * Requirements: 9.4
 */

interface ErrorMessageProps {
  /** Error message to display */
  message: string;
  /** HTTP status code (if available) */
  statusCode?: number;
  /** Callback to dismiss the error */
  onDismiss?: () => void;
}

/**
 * Returns a user-friendly error message based on the HTTP status code.
 */
function getUserFriendlyMessage(statusCode?: number, detail?: string): string {
  switch (statusCode) {
    case 400:
      return detail || 'The input text is invalid. Please check your text and try again.';
    case 422:
      return 'The input text is invalid. Please ensure it is not empty and under 50,000 characters.';
    case 503:
      return 'The analysis service is temporarily unavailable. Please try again in a few moments.';
    case 500:
      return 'An unexpected error occurred. Please try again later.';
    case 0:
      return 'Unable to connect to the server. Please check your internet connection and try again.';
    default:
      return detail || 'An error occurred. Please try again.';
  }
}

const ErrorMessage: React.FC<ErrorMessageProps> = ({
  message,
  statusCode,
  onDismiss,
}) => {
  const displayMessage = getUserFriendlyMessage(statusCode, message);

  return (
    <div
      role="alert"
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.75rem',
        padding: '1rem',
        backgroundColor: '#fef2f2',
        border: '1px solid #fecaca',
        borderRadius: '0.5rem',
        color: '#991b1b',
        fontSize: '0.875rem',
        lineHeight: 1.5,
      }}
    >
      <span aria-hidden="true" style={{ fontSize: '1.25rem', flexShrink: 0 }}>
        ⚠️
      </span>
      <div style={{ flex: 1 }}>
        <p style={{ margin: 0 }}>{displayMessage}</p>
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          aria-label="Dismiss error"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: '1.25rem',
            color: '#991b1b',
            padding: '0',
            lineHeight: 1,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      )}
    </div>
  );
};

export { getUserFriendlyMessage };
export default ErrorMessage;
