import { Component, type ErrorInfo, type PropsWithChildren, type ReactNode } from 'react';

type ErrorBoundaryState = { hasError: boolean };

export class ErrorBoundary extends Component<PropsWithChildren, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false };

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled application error', error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <main className="grid min-h-screen place-items-center bg-[#f4f7f9] px-6 text-center text-[#102a43]">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.18em] text-[#ef8354]">Hearthwise</p>
            <h1 className="mt-3 font-display text-3xl font-semibold">Something went wrong</h1>
            <p className="mt-3 max-w-md text-slate-600">Refresh the page to return to your household workspace.</p>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}