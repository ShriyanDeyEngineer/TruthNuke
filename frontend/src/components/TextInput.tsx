import React from 'react';

/**
 * TextInput component for entering or pasting text to analyze.
 *
 * Requirements: 9.1
 */

interface TextInputProps {
  /** Current text value */
  value: string;
  /** Callback when text changes */
  onChange: (value: string) => void;
  /** Whether the input is disabled (e.g., during analysis) */
  disabled?: boolean;
  /** Maximum character length */
  maxLength?: number;
}

const TextInput: React.FC<TextInputProps> = ({
  value,
  onChange,
  disabled = false,
  maxLength = 50000,
}) => {
  const charCount = value.length;
  const isNearLimit = charCount > maxLength * 0.9;
  const isOverLimit = charCount > maxLength;

  return (
    <div style={{ width: '100%' }}>
      <label
        htmlFor="analysis-text-input"
        style={{
          display: 'block',
          marginBottom: '0.5rem',
          fontWeight: 600,
          fontSize: '0.875rem',
          color: '#374151',
        }}
      >
        Enter text to analyze
      </label>
      <textarea
        id="analysis-text-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        placeholder="Paste or type financial content here to check for misinformation..."
        aria-label="Text to analyze for financial misinformation"
        aria-describedby="char-count"
        style={{
          width: '100%',
          minHeight: '200px',
          padding: '0.75rem',
          fontSize: '1rem',
          lineHeight: 1.5,
          border: `1px solid ${isOverLimit ? '#ef4444' : '#d1d5db'}`,
          borderRadius: '0.5rem',
          resize: 'vertical',
          fontFamily: 'inherit',
          backgroundColor: disabled ? '#f9fafb' : '#fff',
          color: '#111827',
          outline: 'none',
        }}
        onFocus={(e) => {
          e.currentTarget.style.borderColor = isOverLimit ? '#ef4444' : '#3b82f6';
          e.currentTarget.style.boxShadow = `0 0 0 2px ${isOverLimit ? 'rgba(239,68,68,0.2)' : 'rgba(59,130,246,0.2)'}`;
        }}
        onBlur={(e) => {
          e.currentTarget.style.borderColor = isOverLimit ? '#ef4444' : '#d1d5db';
          e.currentTarget.style.boxShadow = 'none';
        }}
      />
      <div
        id="char-count"
        style={{
          display: 'flex',
          justifyContent: 'flex-end',
          marginTop: '0.25rem',
          fontSize: '0.75rem',
          color: isOverLimit ? '#ef4444' : isNearLimit ? '#f59e0b' : '#9ca3af',
        }}
        aria-live="polite"
      >
        {charCount.toLocaleString()} / {maxLength.toLocaleString()} characters
      </div>
    </div>
  );
};

export default TextInput;
