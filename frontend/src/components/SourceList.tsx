import React from 'react';
import type { SearchResult } from '@/types/api';

/**
 * SourceList displays the list of retrieved sources with titles and source names.
 *
 * Requirements: 10.4, 11.3
 */

interface SourceListProps {
  /** Array of search results / sources */
  sources: SearchResult[];
}

const SourceList: React.FC<SourceListProps> = ({ sources }) => {
  if (sources.length === 0) return null;

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
        Sources ({sources.length})
      </h2>
      <ul
        style={{
          listStyle: 'none',
          padding: 0,
          margin: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
        }}
      >
        {sources.map((source, index) => (
          <li
            key={index}
            style={{
              padding: '0.75rem',
              backgroundColor: '#f9fafb',
              borderRadius: '0.5rem',
              border: '1px solid #f3f4f6',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'flex-start',
                marginBottom: '0.25rem',
              }}
            >
              <span
                style={{
                  fontSize: '0.875rem',
                  fontWeight: 600,
                  color: '#111827',
                }}
              >
                {source.title}
              </span>
              <span
                style={{
                  fontSize: '0.7rem',
                  color: '#9ca3af',
                  flexShrink: 0,
                  marginLeft: '0.5rem',
                }}
              >
                {source.relevance_score.toFixed(2)}
              </span>
            </div>
            <div
              style={{
                fontSize: '0.75rem',
                color: '#6b7280',
                marginBottom: '0.25rem',
              }}
            >
              {source.source} · {source.timestamp}
            </div>
            <p
              style={{
                fontSize: '0.8rem',
                color: '#4b5563',
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              {source.summary}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
};

export default SourceList;
