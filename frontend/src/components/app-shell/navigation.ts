import { CalendarRange, FileText, Home, MessageCircle, Package, Users, WalletCards, Wrench, type LucideIcon } from 'lucide-react';

export type NavigationItem = { to: string; label: string; icon: LucideIcon };

export const navigationItems: NavigationItem[] = [
  { to: 'overview', label: 'Overview', icon: Home },
  { to: 'people', label: 'People', icon: Users },
  { to: 'plan', label: 'Plan', icon: CalendarRange },
  { to: 'inventory', label: 'Inventory', icon: Package },
  { to: 'finance', label: 'Finance', icon: WalletCards },
  { to: 'maintenance', label: 'Maintenance', icon: Wrench },
  { to: 'documents', label: 'Documents', icon: FileText },
  { to: 'chat', label: 'AI assistant', icon: MessageCircle },
];
