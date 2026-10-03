import { describe, expect, it } from 'vitest';
import { queryClient } from './query-client';

describe('query client foundation', () => {
  it('uses resilient defaults for server state', () => {
    const defaults = queryClient.getDefaultOptions();

    expect(defaults.queries?.staleTime).toBe(30_000);
    expect(defaults.queries?.retry).toBe(2);
    expect(defaults.mutations?.retry).toBe(0);
  });
});