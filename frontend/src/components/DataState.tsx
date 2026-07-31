import {ReactNode} from 'react';
import {AlertCircle, FileText, LoaderCircle} from 'lucide-react';

type DataStateKind = 'loading' | 'empty' | 'error';

export function DataState({
  state,
  title,
  message,
  action,
  className = '',
}: {
  state: DataStateKind;
  title?: string;
  message: string;
  action?: ReactNode;
  className?: string;
}) {
  const icon = state === 'loading'
    ? <LoaderCircle className="size-4 animate-spin" aria-hidden="true" />
    : state === 'error'
      ? <AlertCircle className="size-4 text-destructive" aria-hidden="true" />
      : <FileText className="size-4 text-brand-amber" aria-hidden="true" />;

  return (
    <div
      className={`mt-4 flex items-start gap-2 text-sm text-muted-foreground ${className}`}
      role={state === 'error' ? 'alert' : 'status'}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <div>
        {title && <h3 className="font-medium text-foreground">{title}</h3>}
        <p className={state === 'error' ? 'text-destructive' : ''}>{message}</p>
        {action}
      </div>
    </div>
  );
}

