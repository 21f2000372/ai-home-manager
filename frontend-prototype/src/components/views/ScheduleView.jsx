import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { 
  Calendar as CalendarIcon, 
  Clock, 
  MapPin, 
  Users,
  CheckCircle2,
  Sparkles,
  Plus
} from 'lucide-react';

export const ScheduleView = () => {
  const { state, isPlanApplied, addScheduleEvent } = useHousehold();
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Form State
  const [eventTitle, setEventTitle] = useState('');
  const [eventDay, setEventDay] = useState('Wednesday');
  const [eventTime, setEventTime] = useState('10:00 AM');
  const [eventLocation, setEventLocation] = useState('Home');
  const [eventDomain, setEventDomain] = useState('Tasks & Schedule');
  const [eventRecurring, setEventRecurring] = useState('None');
  const [selectedAttendees, setSelectedAttendees] = useState(['rajesh']);

  const handleCreateEvent = (e) => {
    e.preventDefault();
    if (!eventTitle.trim()) return;
    addScheduleEvent({
      title: eventTitle.trim(),
      day: eventDay,
      time: eventTime.trim(),
      location: eventLocation.trim(),
      attendees: selectedAttendees.length > 0 ? selectedAttendees : ['rajesh'],
      domain: eventDomain,
      recurring: eventRecurring,
    });
    setEventTitle('');
    setEventTime('10:00 AM');
    setEventLocation('Home');
    setEventRecurring('None');
    setIsAddModalOpen(false);
  };

  const toggleAttendee = (memberId) => {
    if (selectedAttendees.includes(memberId)) {
      if (selectedAttendees.length > 1) {
        setSelectedAttendees(selectedAttendees.filter(id => id !== memberId));
      }
    } else {
      setSelectedAttendees([...selectedAttendees, memberId]);
    }
  };

  const DAYS = ['Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];

  const totalEvents = state.schedule.length;

  return (
    <div className="space-y-5 max-w-5xl mx-auto animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              Household Agenda & Timeline
            </h2>
            <Badge variant="primary" size="xs">
              {totalEvents} Scheduled
            </Badge>
          </div>
          <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
            Chronological sequence of family commitments, technician visits, and guest arrivals.
          </p>
        </div>

        <div className="flex items-center gap-2 self-start sm:self-auto">
          {isPlanApplied && (
            <Badge variant="agent" size="sm" className="py-1 px-2.5">
              <Sparkles className="w-3.5 h-3.5" />
              Plan Synchronized
            </Badge>
          )}

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsAddModalOpen(true)}
            icon={Plus}
          >
            Add Event
          </Button>
        </div>
      </div>

      {/* Days Sequence */}
      <div className="space-y-2.5">
        {DAYS.map((dayName) => {
          const eventsOnDay = state.schedule.filter(s => s.day.includes(dayName));
          const isEmpty = eventsOnDay.length === 0;

          // Compressed State for Empty Days
          if (isEmpty) {
            return (
              <div
                key={dayName}
                className="px-3.5 py-2.5 rounded-xl bg-black/[0.02] dark:bg-white/[0.02] border border-dashed border-[#D9D8D2] dark:border-[#2D322E] flex items-center justify-between opacity-65 text-xs transition-colors hover:opacity-100"
              >
                <div className="flex items-center gap-2.5">
                  <CalendarIcon className="w-3.5 h-3.5 text-[#676B68] dark:text-[#969D96]" />
                  <span className="font-semibold text-[#171918] dark:text-[#EFF1EC]">{dayName}</span>
                </div>
                <span className="text-[11px] text-[#676B68] dark:text-[#969D96] italic">
                  No scheduled items
                </span>
              </div>
            );
          }

          // Rich Card for Active Days
          return (
            <Card key={dayName} className="p-3.5 sm:p-4 space-y-3">
              <div className="flex items-center justify-between pb-2 border-b border-[#D9D8D2] dark:border-[#2D322E]">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-xs sm:text-sm text-[#171918] dark:text-[#EFF1EC]">
                    {dayName}
                  </span>
                  <Badge variant="neutral" size="xs">
                    {eventsOnDay.length} {eventsOnDay.length === 1 ? 'event' : 'events'}
                  </Badge>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                {eventsOnDay.map((evt) => (
                  <div
                    key={evt.id}
                    className="p-3 rounded-xl bg-black/5 dark:bg-white/5 border border-[#D9D8D2]/60 dark:border-[#2D322E]/60 flex flex-col justify-between space-y-2 hover:border-[#5E9278]/50 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-semibold text-[#171918] dark:text-[#EFF1EC] leading-tight">
                        {evt.title}
                      </span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded-md bg-[#5E9278]/10 text-[#3d6551] dark:text-[#9BCDB4] shrink-0 font-medium">
                        {evt.time}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-[#676B68] dark:text-[#969D96] pt-1 border-t border-[#D9D8D2]/40 dark:border-[#2D322E]/40">
                      <span className="flex items-center gap-1 truncate max-w-[160px] sm:max-w-none">
                        <MapPin className="w-3 h-3 shrink-0" />
                        {evt.location}
                      </span>
                      <span className="font-medium text-[#5E9278] dark:text-[#9BCDB4] capitalize flex items-center gap-1 shrink-0">
                        <Users className="w-3 h-3 shrink-0" />
                        {evt.attendees.join(', ')}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          );
        })}
      </div>

      {/* Add Event Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Schedule Household Event"
        subtitle="Coordinate family commitments, deliveries, and technician visits"
      >
        <form onSubmit={handleCreateEvent} className="space-y-4 text-xs">
          <div>
            <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
              Event Title *
            </label>
            <Input
              value={eventTitle}
              onChange={(e) => setEventTitle(e.target.value)}
              placeholder="e.g. Family Dinner with Relatives, Doctor Follow-up..."
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Day of Week
              </label>
              <select
                value={eventDay}
                onChange={(e) => setEventDay(e.target.value)}
                className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
              >
                {DAYS.map(d => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Time Window
              </label>
              <Input
                value={eventTime}
                onChange={(e) => setEventTime(e.target.value)}
                placeholder="e.g. 6:30 PM - 8:00 PM"
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Location
              </label>
              <Input
                value={eventLocation}
                onChange={(e) => setEventLocation(e.target.value)}
                placeholder="e.g. Home Dining Room, Apollo Clinic..."
              />
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Domain
              </label>
              <select
                value={eventDomain}
                onChange={(e) => setEventDomain(e.target.value)}
                className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
              >
                <option value="Tasks & Schedule">Tasks & Schedule</option>
                <option value="Food & Inventory">Food & Inventory</option>
                <option value="Health & Care">Health & Care</option>
                <option value="Home & Maintenance">Home & Maintenance</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-2">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Recurring Rule
              </label>
              <select
                value={eventRecurring}
                onChange={(e) => setEventRecurring(e.target.value)}
                className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
              >
                <option value="None">None (One-off)</option>
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
                <option value="Monthly">Monthly</option>
              </select>
            </div>
          </div>

          {/* Attendees Selector */}
          <div>
            <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1.5">
              Household Attendees
            </label>
            <div className="flex flex-wrap gap-2">
              {state.members.map((m) => {
                const isSelected = selectedAttendees.includes(m.id);
                return (
                  <button
                    key={m.id}
                    type="button"
                    onClick={() => toggleAttendee(m.id)}
                    className={`min-h-[34px] px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 border transition-all active:scale-95 ${
                      isSelected
                        ? 'bg-[#5E9278]/15 border-[#5E9278] text-[#2F5542] dark:text-[#9BCDB4] font-semibold'
                        : 'border-[#D9D8D2] dark:border-[#2D322E] bg-black/[0.02] dark:bg-white/[0.02] text-[#676B68] dark:text-[#969D96]'
                    }`}
                  >
                    <span>{m.avatar}</span>
                    <span>{m.name.split(' ')[0]}</span>
                    {isSelected && <CheckCircle2 className="w-3.5 h-3.5 text-[#5E9278]" />}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsAddModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
            >
              Add Event to Schedule
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
