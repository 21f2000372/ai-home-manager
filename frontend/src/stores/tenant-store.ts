import { create } from 'zustand';

type TenantState = {
  activeTenantId: string | null;
  switchStatus: 'idle' | 'validating' | 'switching' | 'failed';
  selectTenant: (tenantId: string) => void;
  clear: () => void;
};

export const useTenantStore = create<TenantState>((set) => ({
  activeTenantId: 'home-lakeview',
  switchStatus: 'idle',
  selectTenant: (activeTenantId) => set({ activeTenantId, switchStatus: 'switching' }),
  clear: () => set({ activeTenantId: null, switchStatus: 'idle' }),
}));