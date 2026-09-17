import React from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Badge } from '../common/Badge';
import { 
  Wrench, 
  ShieldCheck, 
  Calendar, 
  CheckCircle2, 
  AlertTriangle, 
  Wind, 
  Tv, 
  Sparkles,
  PhoneCall,
  FileText
} from 'lucide-react';

export const MaintenanceView = () => {
  const { state, isPlanApplied, setActiveTab } = useHousehold();

  return (
    <div className="space-y-6 animate-fade-in pb-12">
      {/* Header */}
      <div className="p-6 rounded-3xl bg-gradient-to-r from-amber-950 via-slate-900 to-navy-900 border border-amber-500/30">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <Badge variant="amber" size="sm">
                <Wrench className="w-3.5 h-3.5" />
                Appliance Health & Warranties
              </Badge>
              {isPlanApplied ? (
                <Badge variant="emerald" size="sm">Guest AC Service Booked (Fri 10 AM)</Badge>
              ) : (
                <Badge variant="amber" size="sm">Guest AC Needs Service</Badge>
              )}
            </div>
            <h2 className="text-xl lg:text-2xl font-black text-white">
              Home Appliances, Warranties & Maintenance
            </h2>
            <p className="text-xs text-slate-300 max-w-2xl mt-1 leading-relaxed">
              Operations Agent tracks manufacturer warranty agreements and proactively schedules pre-arrival HVAC inspections before guests arrive.
            </p>
          </div>
        </div>
      </div>

      {/* Primary Highlight: Guest Bedroom AC */}
      <div className="p-5 rounded-3xl bg-slate-900/90 border border-brand-500/40 shadow-xl backdrop-blur-md">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-start gap-3.5">
            <div className="p-3 rounded-2xl bg-brand-500/20 text-brand-400 shrink-0">
              <Wind className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-white">Guest Bedroom AC (Daikin 1.5T Inverter)</h3>
                <Badge
                  variant={isPlanApplied ? 'emerald' : 'amber'}
                  size="sm"
                >
                  {isPlanApplied ? 'Service Confirmed (Fri 10 AM)' : 'Service Required Before Saturday'}
                </Badge>
              </div>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed max-w-2xl">
                {isPlanApplied
                  ? 'Operations Agent matched warranty #DOC-WAR-03 and scheduled Daikin AMC technician visit for Friday 10:00 AM so the room is fully conditioned for the 4 arriving relatives.'
                  : 'Filters are dirty and pre-arrival cooling inspection is pending before 4 relatives arrive on Saturday.'}
              </p>
              <div className="flex flex-wrap items-center gap-3 mt-3 text-[11px] text-slate-400">
                <span>Warranty: <strong className="text-emerald-400">Active till Dec 2027</strong></span>
                <span>•</span>
                <span>Coverage: <strong className="text-slate-200">2 Free AMC Services/yr</strong></span>
                <span>•</span>
                <button
                  onClick={() => setActiveTab('documents')}
                  className="text-brand-400 hover:text-brand-300 font-semibold flex items-center gap-1"
                >
                  <FileText className="w-3 h-3" /> View Warranty Certificate (DOC-WAR-03)
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Appliance Fleet Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {state.maintenance.map((app) => (
          <div
            key={app.id}
            className="p-5 rounded-3xl bg-slate-900/80 border border-slate-800 flex flex-col justify-between"
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <Badge variant="outline" size="sm" className="font-mono text-[10px]">
                  {app.location}
                </Badge>
                <Badge
                  variant={
                    app.status === 'optimal'
                      ? 'emerald'
                      : app.status === 'scheduled'
                      ? 'brand'
                      : 'amber'
                  }
                  size="sm"
                >
                  {app.statusLabel}
                </Badge>
              </div>

              <h4 className="text-sm font-bold text-white">{app.name}</h4>
              <p className="text-xs text-slate-300 mt-1 leading-relaxed">
                {app.issueDescription}
              </p>
            </div>

            <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between">
              <span>Last Service: {app.lastService}</span>
              <span className="text-slate-300 font-mono text-[10px]">{app.warrantyStatus}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
