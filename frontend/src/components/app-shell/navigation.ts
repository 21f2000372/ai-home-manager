import { Bell, CalendarDays, ClipboardCheck, FileText, Home, MessageCircle, Package, Users, WalletCards, Wrench, type LucideIcon } from 'lucide-react';

export type Role = 'Admin' | 'Adult' | 'Child' | 'Guest';

export type NavigationItem = { to: string; label: string; icon: LucideIcon; roles: Role[] };

const ALL: Role[] = ['Admin', 'Adult', 'Child', 'Guest'];
const NON_GUEST: Role[] = ['Admin', 'Adult', 'Child'];

export const navigationItems: NavigationItem[] = [
  // Guests get a single, dedicated dashboard and nothing else.
  { to: 'dashboard', label: 'Dashboard', icon: Bell, roles: ['Guest'] },

  { to: 'overview', label: 'Overview', icon: Home, roles: NON_GUEST },
  { to: 'people', label: 'People', icon: Users, roles: ['Admin', 'Adult'] },
  { to: 'tasks', label: 'Tasks', icon: ClipboardCheck, roles: NON_GUEST },
  { to: 'calendar', label: 'Calendar', icon: CalendarDays, roles: NON_GUEST },
  { to: 'inventory', label: 'Inventory', icon: Package, roles: NON_GUEST },
  { to: 'finance', label: 'Finance', icon: WalletCards, roles: ['Admin', 'Adult'] },
  { to: 'maintenance', label: 'Maintenance', icon: Wrench, roles: NON_GUEST },
  { to: 'documents', label: 'Documents', icon: FileText, roles: NON_GUEST },
  { to: 'chat', label: 'AI assistant', icon: MessageCircle, roles: ALL },
];

/** Navigation items visible to a given role. */
export function navigationItemsForRole(role: Role | undefined): NavigationItem[] {
  if (!role) return [];
  return navigationItems.filter((item) => item.roles.includes(role));
}
