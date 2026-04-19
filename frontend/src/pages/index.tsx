import React, { useState } from 'react';
import Head from 'next/head';
import TextInput from '@/components/TextInput';
import SubmitButton from '@/components/SubmitButton';
import LoadingIndicator from '@/components/LoadingIndicator';
import ErrorMessage from '@/components/ErrorMessage';
import TrustScoreMeter from '@/components/TrustScoreMeter';
import ExplanationPanel from '@/components/ExplanationPanel';
import RiskyPhraseHighlighter from '@/components/RiskyPhraseHighlighter';
import SourceList from '@/components/SourceList';
import SourceTransparencyPanel from '@/components/SourceTransparencyPanel';
import DisclaimerBanner from '@/components/DisclaimerBanner';
import apiClient, { ApiError } from '@/lib/api';
import type { AnalysisResponse } from '@/types/api';

/**
 * Main analysis page — wires TextInput, SubmitButton, and results display.
 *
 * Requirements: 9.1, 9.2, 9.3, 9.4, 10.1–10.5, 11.1, 28.5
 */
export default function Home() {
  const [text, setText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; statusCode?: number } | null>(null);
  const [result, setResult] = useState<AnalysisResponse | null>(null);

  const canSubmit = text.trim().length > 0 && text.length <= 50000 && !loading;

  const handleAnalyze = async () => {
    if (!canSubmit) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await apiClient.post<AnalysisResponse>('/analyze', {
        text,
      });
      setResult(response.data);
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ message: err.detail || err.message, statusCode: err.status });
      } else {
        setError({ message: 'An unexpected error occurred.', statusCode: 0 });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Head>
        <title>TruthNuke - Financial Misinformation Detector</title>
        <meta name="description" content="AI-powered financial misinformation detector" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <main
        style={{
          maxWidth: '800px',
          margin: '0 auto',
          padding: '2rem 1rem',
        }}
      >
        <header style={{ marginBottom: '2rem' }}>
          <h1 style={{ fontSize: '2rem', fontWeight: 700, color: '#111827' }}>
            TruthNuke
          </h1>
          <p style={{ color: '#6b7280', fontSize: '1rem' }}>
            AI-powered financial misinformation detector
          </p>
        </header>

        <section aria-label="Text input" style={{ marginBottom: '1rem' }}>
          <TextInput value={text} onChange={setText} disabled={loading} />
        </section>

        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '1.5rem' }}>
          <SubmitButton onClick={handleAnalyze} disabled={!canSubmit} loading={loading} />
        </div>

        {error && (
          <section aria-label="Error" style={{ marginBottom: '1.5rem' }}>
            <ErrorMessage
              message={error.message}
              statusCode={error.statusCode}
              onDismiss={() => setError(null)}
            />
          </section>
        )}

        {loading && (
          <section aria-label="Loading">
            <LoadingIndicator />
          </section>
        )}

        {result && (
          <section aria-label="Analysis results" style={{ marginTop: '1.5rem' }}>
            <DisclaimerBanner disclaimer={result.disclaimer} />

            {result.trust_score !== null && result.overall_classification && (
              <div style={{ margin: '1.5rem 0' }}>
                <TrustScoreMeter
                  score={result.trust_score}
                  classification={result.overall_classification}
                  breakdown={result.trust_score_breakdown}
                />
              </div>
            )}

            <div style={{ margin: '1.5rem 0' }}>
              <ExplanationPanel explanation={result.explanation} />
            </div>

            {result.claims.length > 0 && (
              <div style={{ margin: '1.5rem 0' }}>
                <RiskyPhraseHighlighter
                  originalText={text}
                  claims={result.claims.map((ca) => ca.claim)}
                />
              </div>
            )}

            {result.claims.length > 0 && (
              <div style={{ margin: '1.5rem 0' }}>
                <SourceTransparencyPanel claims={result.claims} />
              </div>
            )}

            {result.sources.length > 0 && (
              <div style={{ margin: '1.5rem 0' }}>
                <SourceList sources={result.sources} />
              </div>
            )}
          </section>
        )}
      </main>
    </>
  );
}
