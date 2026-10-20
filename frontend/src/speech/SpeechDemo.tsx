import { useCallback, useEffect, useRef, useState } from 'react';
import { useLanguage } from '../l10n';
import { Mascot, MascotBubble } from '../components/ui';
import { apiClient } from '../services/apiClient';

interface ProviderInfo {
  name: string;
  available: boolean;
  model?: string;
  language?: string;
  device?: string;
  status?: string;
}

interface TranscriptResult {
  text: string;
  language: string;
  provider: string;
  provider_version: string;
  transcript_available: boolean;
  quality: string;
}

interface DemoTranscriptionResponse {
  transcript: TranscriptResult;
  provider: string;
  provider_version: string;
  audio_info: {
    filename: string;
    size_bytes: number;
    duration_estimated: number;
  };
}

interface CompareResult {
  status: string;
  transcript?: TranscriptResult;
  provider_version?: string;
  error?: string;
}

interface DemoCompareResponse {
  audio_info: { filename: string; size_bytes: number };
  results: Record<string, CompareResult>;
}

export interface SpeechDemoProps {
  onClose?: () => void;
}

export function SpeechDemo({ onClose }: SpeechDemoProps) {
  const { t } = useLanguage();
  const [providers, setProviders] = useState<Record<string, ProviderInfo>>({});
  const [selectedProvider, setSelectedProvider] = useState<string>('auto');
  const [language, setLanguage] = useState('en');
  const [consent, setConsent] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<DemoTranscriptionResponse | null>(null);
  const [compareResult, setCompareResult] = useState<DemoCompareResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [comparing, setComparing] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadProviders();
  }, []);

  const loadProviders = async () => {
    try {
      const response = await apiClient.get('/speech/demo/providers');
      setProviders(response.providers);
      // Auto-select first available provider
      const available = Object.entries(response.providers).find(([, v]) => v.available);
      if (available) {
        setSelectedProvider(available[0]);
      }
    } catch (e) {
      console.error('Failed to load providers:', e);
    }
  };

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setError(null);
      setResult(null);
      setCompareResult(null);
    }
  }, []);

  const transcribe = useCallback(async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError(t('speech.demo.noFile'));
      return;
    }
    if (!consent) {
      setError(t('speech.demo.consentRequired'));
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('language', language);
      formData.append('consent', 'true');
      if (selectedProvider !== 'auto') {
        formData.append('provider', selectedProvider);
      }

      const response = await apiClient.post<DemoTranscriptionResponse>('/speech/demo/transcribe', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(response);
    } catch (e: any) {
      setError(e.response?.data?.detail?.message || e.message || t('speech.demo.transcriptionFailed'));
    } finally {
      setUploading(false);
    }
  }, [fileInputRef, language, selectedProvider, consent, t]);

  const compare = useCallback(async () => {
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      setError(t('speech.demo.noFile'));
      return;
    }
    if (!consent) {
      setError(t('speech.demo.consentRequired'));
      return;
    }

    setComparing(true);
    setError(null);
    setCompareResult(null);

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('language', language);
      formData.append('consent', 'true');

      const response = await apiClient.post<DemoCompareResponse>('/speech/demo/compare', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setCompareResult(response);
    } catch (e: any) {
      setError(e.response?.data?.detail?.message || e.message || t('speech.demo.comparisonFailed'));
    } finally {
      setComparing(false);
    }
  }, [fileInputRef, language, consent, t]);

  const clearResults = useCallback(() => {
    setResult(null);
    setCompareResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  }, []);

  return (
    <div className="speech-demo">
      <div className="demo-header">
        <h2>{t('speech.demo.title')}</h2>
        <p className="demo-description">{t('speech.demo.description')}</p>
        {onClose && (
          <button className="demo-close" onClick={onClose} aria-label={t('common.close')}>
            ×
          </button>
        )}
      </div>

      <div className="demo-section">
        <h3>{t('speech.demo.providerSelection')}</h3>
        <div className="provider-grid">
          {Object.entries(providers).map(([key, provider]) => (
            <label key={key} className={`provider-card ${selectedProvider === key ? 'selected' : ''} ${!provider.available ? 'unavailable' : ''}`}>
              <input
                type="radio"
                name="provider"
                value={key}
                checked={selectedProvider === key}
                onChange={() => setSelectedProvider(key)}
                disabled={!provider.available && key !== 'auto'}
              />
              <div className="provider-info">
                <strong>{provider.name}</strong>
                {provider.model && <span className="provider-model">{provider.model}</span>}
                {provider.language && <span className="provider-lang">{provider.language}</span>}
                <span className={`provider-status ${provider.available ? 'available' : 'unavailable'}`}>
                  {provider.available ? t('speech.demo.available') : t('speech.demo.unavailable')}
                </span>
              </div>
            </label>
          ))}
        </div>
      </div>

      <div className="demo-section">
        <h3>{t('speech.demo.settings')}</h3>
        <div className="settings-row">
          <label>
            <span>{t('speech.demo.language')}</span>
            <select value={language} onChange={(e) => setLanguage(e.target.value)}>
              <option value="en">English</option>
              <option value="ta">Tamil</option>
              <option value="hi">Hindi</option>
              <option value="bn">Bengali</option>
              <option value="te">Telugu</option>
              <option value="mr">Marathi</option>
            </select>
          </label>
          <label className="consent-label">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
            />
            <span>{t('speech.demo.consentLabel')}</span>
          </label>
        </div>
      </div>

      <div className="demo-section">
        <h3>{t('speech.demo.uploadAudio')}</h3>
        <input
          type="file"
          ref={fileInputRef}
          accept="audio/*,.wav,.flac,.mp3,.ogg,.m4a,.webm"
          onChange={handleFileSelect}
          className="file-input"
          id="demo-audio-upload"
        />
        <label htmlFor="demo-audio-upload" className="file-label">
          <span className="file-icon">🎤</span>
          <span>{t('speech.demo.chooseFile')}</span>
          <span className="file-hint">{t('speech.demo.fileHint')}</span>
        </label>
        {fileInputRef.current?.files?.[0] && (
          <p className="selected-file">
            📄 {fileInputRef.current.files[0].name} ({(fileInputRef.current.files[0].size / 1024).toFixed(1)} KB)
          </p>
        )}
      </div>

      <div className="demo-actions">
        <button
          className="btn btn-primary"
          onClick={transcribe}
          disabled={uploading || !fileInputRef.current?.files?.[0] || !consent}
        >
          {uploading ? t('speech.demo.transcribing') : t('speech.demo.transcribe')}
        </button>
        <button
          className="btn btn-secondary"
          onClick={compare}
          disabled={comparing || !fileInputRef.current?.files?.[0] || !consent}
        >
          {comparing ? t('speech.demo.comparing') : t('speech.demo.compare')}
        </button>
        {(result || compareResult) && (
          <button className="btn btn-outline" onClick={clearResults}>
            {t('speech.demo.clear')}
          </button>
        )}
      </div>

      {error && (
        <div className="demo-error" role="alert">
          ⚠️ {error}
        </div>
      )}

      {result && (
        <div className="demo-result">
          <h4>{t('speech.demo.transcriptionResult')}</h4>
          <div className="result-meta">
            <span className="badge">{result.provider}</span>
            <span className="badge">{result.provider_version}</span>
            <span className="badge">{result.transcript.language}</span>
          </div>
          <div className="transcript-text" data-quality={result.transcript.quality}>
            {result.transcript.text || t('speech.demo.emptyTranscript')}
          </div>
          <details className="audio-meta">
            <summary>{t('speech.demo.audioInfo')}</summary>
            <pre>{JSON.stringify(result.audio_info, null, 2)}</pre>
          </details>
        </div>
      )}

      {compareResult && (
        <div className="demo-compare-result">
          <h4>{t('speech.demo.comparisonResult')}</h4>
          <div className="compare-grid">
            {Object.entries(compareResult.results).map(([provider, res]) => (
              <div key={provider} className={`compare-card ${res.status}`}>
                <h5>{provider}</h5>
                {res.status === 'success' && res.transcript && (
                  <>
                    <span className="badge">{res.provider_version}</span>
                    <div className="transcript-text">{res.transcript.text || t('speech.demo.emptyTranscript')}</div>
                  </>
                )}
                {res.status === 'unavailable' && <p className="status-unavailable">{t('speech.demo.unavailable')}</p>}
                {res.status === 'error' && <p className="status-error">{res.error}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}