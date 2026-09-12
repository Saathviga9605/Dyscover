import { useEffect, useRef, useState } from 'react';

export function GazeVideo({ stream, className }: { stream?: MediaStream | null; className?: string }) {
  const videoRef = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const video = videoRef.current;
    if (video && stream && video.srcObject !== stream) video.srcObject = stream;
  }, [stream]);
  return <video ref={videoRef} className={className} autoPlay muted playsInline />;
}

export interface LiveGazePreviewProps {
  stream: MediaStream | null;
  active: boolean;
}

export function LiveGazePreview({ stream, active }: LiveGazePreviewProps) {
  const [collapsed, setCollapsed] = useState(false);

  if (!stream) return null;

  if (collapsed) {
    return (
      <button type="button" className="gaze-preview gaze-preview-collapsed" onClick={() => setCollapsed(false)} aria-label="Show camera preview" title="Show camera preview">
        <span className="gaze-preview-dot" />
      </button>
    );
  }

  return (
    <div className="gaze-preview" aria-hidden="true">
      <GazeVideo className="gaze-preview-video" stream={stream} />
      <div className="gaze-preview-label">
        <span className={`gaze-preview-dot ${active ? 'active' : ''}`} />
        <span>Eye tracking active</span>
        <button type="button" className="gaze-preview-minimize" onClick={() => setCollapsed(true)} aria-label="Hide camera preview" title="Hide camera preview">
          –
        </button>
      </div>
    </div>
  );
}