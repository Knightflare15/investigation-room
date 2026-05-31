import { useEffect, useState, type ReactNode } from 'react';

type PanelHeaderProps = {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
};

type MediaPlateProps = {
  src?: string | null;
  alt: string;
  kind: 'suspect' | 'evidence' | 'location' | 'cover';
  label?: string;
  className?: string;
};

type SeverityProps = {
  value: number;
};

export function PanelHeader({ eyebrow, title, subtitle, actions }: PanelHeaderProps) {
  return (
    <div className="panel-header">
      <div>
        {eyebrow ? <p className="eyebrow">{eyebrow}</p> : null}
        <h2 className="section-title">{title}</h2>
        {subtitle ? <p className="section-subtitle">{subtitle}</p> : null}
      </div>
      {actions ? <div className="panel-actions">{actions}</div> : null}
    </div>
  );
}

export function MediaPlate({ src, alt, kind, label, className }: MediaPlateProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const placeholderText =
    kind === 'suspect'
      ? 'No portrait assigned'
      : kind === 'evidence'
        ? 'Placeholder evidence plate'
        : kind === 'location'
          ? 'Location dossier placeholder'
          : 'Case cover placeholder';

  useEffect(() => {
    setImageFailed(false);
  }, [src]);

  const classes = ['media-plate', `media-plate-${kind}`, className].filter(Boolean).join(' ');
  if (src && !imageFailed) {
    return (
      <div className={classes}>
        <img className="media-preview" src={src} alt={alt} onError={() => setImageFailed(true)} />
        {label ? <span className="media-label">{label}</span> : null}
      </div>
    );
  }

  return (
    <div className={`${classes} media-placeholder`}>
      <div className="placeholder-art" aria-hidden="true" />
      <div className="placeholder-lines" aria-hidden="true">
        <span />
        <span />
        <span />
      </div>
      <div className="placeholder-copy">
        <strong>{label ?? kind}</strong>
        <span>{placeholderText}</span>
      </div>
    </div>
  );
}

export function SuspicionMeter({ value }: SeverityProps) {
  const segments = 12;
  const activeSegments = Math.max(1, Math.round((value / 100) * segments));
  return (
    <div className="suspicion-meter" aria-label={`Suspicion level ${value}%`}>
      {Array.from({ length: segments }, (_, index) => {
        const active = index < activeSegments;
        return <span key={index} className={active ? 'suspicion-segment active' : 'suspicion-segment'} />;
      })}
      <strong>{value}%</strong>
    </div>
  );
}

export function CrestMark() {
  return (
    <div className="crest-mark" aria-hidden="true">
      <span className="crest-ring" />
      <span className="crest-core">IR</span>
      <span className="crest-crosshair" />
    </div>
  );
}
