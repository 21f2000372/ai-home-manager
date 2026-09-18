import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { 
  Users, 
  ShieldCheck, 
  Lock, 
  Check, 
  X, 
  CheckCircle2,
  Plus,
  Edit2
} from 'lucide-react';

export const MembersView = () => {
  const { rawState, activeUser, switchUser, addMember, updateMemberRole, updateMemberStatus } = useHousehold();

  // Invite / Add Member Modal State
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [memberName, setMemberName] = useState('');
  const [memberRelation, setMemberRelation] = useState('Visiting Relative');
  const [memberRole, setMemberRole] = useState('Guest / Visitor');
  const [memberAvatar, setMemberAvatar] = useState('🧑');
  const [memberAvailability, setMemberAvailability] = useState('Available');
  const [memberStatusText, setMemberStatusText] = useState('');
  const [memberDietaryNotes, setMemberDietaryNotes] = useState('No restrictions');

  // Edit Member Status Modal State
  const [editingMember, setEditingMember] = useState(null);
  const [editRole, setEditRole] = useState('');
  const [editAvailability, setEditAvailability] = useState('');
  const [editStatusText, setEditStatusText] = useState('');

  const handleInviteMember = (e) => {
    e.preventDefault();
    if (!memberName.trim()) return;
    addMember({
      name: memberName.trim(),
      relation: memberRelation,
      role: memberRole,
      avatar: memberAvatar,
      availability: memberAvailability,
      statusText: memberStatusText.trim() || `Active ${memberRelation.toLowerCase()} in household`,
      dietaryNotes: memberDietaryNotes.trim() || 'No restrictions',
      responsibilities: [memberRole.includes('Teen') ? 'Assigned Chores' : 'General Household Assistance'],
    });
    setMemberName('');
    setMemberStatusText('');
    setIsInviteModalOpen(false);
  };

  const handleOpenEditMember = (m, e) => {
    e.stopPropagation();
    setEditingMember(m);
    setEditRole(m.role);
    setEditAvailability(m.availability || 'Available');
    setEditStatusText(m.statusText || '');
  };

  const handleSaveMemberEdit = (e) => {
    e.preventDefault();
    if (!editingMember) return;
    updateMemberRole(editingMember.id, editRole);
    updateMemberStatus(editingMember.id, editStatusText, editAvailability);
    setEditingMember(null);
  };

  // Scannable capability highlights per member
  const getMemberCapabilities = (m) => {
    if (m.id === 'rajesh') {
      return [
        { label: 'Budget Administrator', variant: 'primary' },
        { label: 'Task Assignment', variant: 'neutral' },
        { label: 'Medical Clearance', variant: 'agent' },
      ];
    }
    if (m.id === 'priya') {
      return [
        { label: 'Budget Administrator', variant: 'primary' },
        { label: 'Family Hospitality', variant: 'neutral' },
        { label: 'Medical Clearance', variant: 'agent' },
      ];
    }
    if (m.id === 'aarav') {
      return [
        { label: 'Assigned Chores Only', variant: 'neutral' },
        { label: 'Finance Shielded', variant: 'critical' },
      ];
    }
    if (m.id === 'savitri') {
      return [
        { label: 'Senior Healthcare Profile', variant: 'agent' },
        { label: 'Protected Privacy', variant: 'info' },
      ];
    }
    return [
      { label: m.clearance || 'Standard Member', variant: 'neutral' },
      { label: m.availability || 'Available', variant: 'primary' },
    ];
  };

  return (
    <div className="space-y-5 max-w-5xl mx-auto animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-lg sm:text-xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
              Family Members & Privacy Clearances
            </h2>
            <Badge variant="primary" size="xs">Role-Based Access Control</Badge>
          </div>
          <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
            Switch perspectives to experience HomeOps as a parent, teenager, or senior family member.
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsInviteModalOpen(true)}
          icon={Plus}
        >
          Invite Member
        </Button>
      </div>

      {/* 1-Tap Active Perspective Switcher Bar */}
      <Card className="p-3 sm:p-4 space-y-2">
        <span className="text-[10px] uppercase font-bold tracking-wider text-[#676B68] dark:text-[#969D96] block">
          Select Active Perspective:
        </span>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {rawState.members.map((m) => {
            const isActive = m.id === activeUser.id;
            return (
              <button
                key={m.id}
                onClick={() => switchUser(m.id)}
                className={`min-h-[44px] p-2 rounded-xl flex items-center gap-2.5 text-left transition-all active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#5E9278] ${
                  isActive
                    ? 'bg-[#5E9278]/15 text-[#2F5542] dark:text-[#9BCDB4] border border-[#5E9278] font-semibold shadow-xs'
                    : 'bg-black/[0.02] dark:bg-white/[0.02] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] hover:border-[#5E9278]/60'
                }`}
              >
                <span className="text-xl shrink-0">{m.avatar}</span>
                <div className="min-w-0">
                  <div className="text-xs font-semibold truncate">{m.name.split(' ')[0]}</div>
                  <div className={`text-[10px] truncate ${isActive ? 'text-[#5E9278] dark:text-[#9BCDB4]' : 'text-[#676B68] dark:text-[#969D96]'}`}>
                    {isActive ? '● Active' : m.relation.split(' ')[0]}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {/* Member Profile Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 sm:gap-4">
        {rawState.members.map((member) => {
          const isActive = member.id === activeUser.id;
          const caps = getMemberCapabilities(member);

          return (
            <Card
              key={member.id}
              onClick={() => switchUser(member.id)}
              className={`p-4 sm:p-5 flex flex-col justify-between space-y-3.5 cursor-pointer transition-all ${
                isActive
                  ? 'border-[#5E9278] ring-1.5 ring-[#5E9278] bg-[#5E9278]/[0.03]'
                  : 'hover:border-[#5E9278]/60'
              }`}
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className="text-3xl shrink-0">{member.avatar}</span>
                    <div>
                      <h3 className="font-semibold text-sm sm:text-base text-[#171918] dark:text-[#EFF1EC] flex items-center gap-1.5">
                        {member.name}
                        {isActive && (
                          <Badge variant="primary" size="xs">Active</Badge>
                        )}
                      </h3>
                      <p className="text-xs text-[#676B68] dark:text-[#969D96]">
                        {member.role} • {member.relation}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-1.5">
                    <Badge variant={member.clearance?.includes('Full') ? 'primary' : 'neutral'} size="xs">
                      {member.clearance?.split(' ')[0]}
                    </Badge>
                    <button
                      type="button"
                      onClick={(e) => handleOpenEditMember(member, e)}
                      title="Edit role & status"
                      className="p-1.5 rounded-lg text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC] hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                    >
                      <Edit2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Status & Context */}
                <div className="p-2.5 rounded-xl bg-black/[0.03] dark:bg-white/[0.03] text-xs space-y-0.5">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-[11px] text-[#171918] dark:text-[#EFF1EC]">
                      Context:
                    </span>
                    <span className="text-[10px] font-medium text-[#5E9278] dark:text-[#9BCDB4]">
                      ● {member.availability || 'Available'}
                    </span>
                  </div>
                  <p className="text-[#676B68] dark:text-[#969D96] leading-snug">
                    {member.statusText}
                  </p>
                </div>

                {/* Simplified Scannable Capability Tags */}
                <div className="space-y-1.5">
                  <span className="font-semibold text-[#171918] dark:text-[#EFF1EC] text-[10px] uppercase tracking-wider block">
                    Domain Clearances:
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {caps.map((cap, i) => (
                      <Badge key={i} variant={cap.variant} size="xs">
                        {cap.label}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>

              {/* Card Footer / Action */}
              <div className="pt-3 border-t border-[#D9D8D2]/50 dark:border-[#2D322E]/50 flex items-center gap-2">
                {isActive ? (
                  <div className="flex-1 min-h-[36px] flex items-center justify-center gap-1 text-xs font-semibold text-[#5E9278] dark:text-[#9BCDB4]">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Active Session</span>
                  </div>
                ) : (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="flex-1 min-h-[36px]"
                    onClick={(e) => {
                      e.stopPropagation();
                      switchUser(member.id);
                    }}
                  >
                    Switch to {member.name.split(' ')[0]}
                  </Button>
                )}
                <Button
                  variant="subtle"
                  size="sm"
                  className="min-h-[36px] px-2.5 text-xs text-[#676B68]"
                  onClick={(e) => handleOpenEditMember(member, e)}
                >
                  <Edit2 className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline ml-1">Edit</span>
                </Button>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Invite Member Modal */}
      <Modal
        isOpen={isInviteModalOpen}
        onClose={() => setIsInviteModalOpen(false)}
        title="Invite / Add Household Member"
        subtitle="Configure role, permissions, and dietary profile"
      >
        <form onSubmit={handleInviteMember} className="space-y-4 text-xs">
          <div>
            <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
              Full Name *
            </label>
            <Input
              value={memberName}
              onChange={(e) => setMemberName(e.target.value)}
              placeholder="e.g. Meera Sharma, Rohan Verma..."
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Family Relation
              </label>
              <select
                value={memberRelation}
                onChange={(e) => setMemberRelation(e.target.value)}
                className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
              >
                <option value="Parent / Spouse">Parent / Spouse</option>
                <option value="Child / Student">Child / Student</option>
                <option value="Grandparent">Grandparent</option>
                <option value="Visiting Relative">Visiting Relative</option>
                <option value="Domestic Assistant">Domestic Assistant</option>
                <option value="Guest">Guest</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Clearance Role
              </label>
              <select
                value={memberRole}
                onChange={(e) => setMemberRole(e.target.value)}
                className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
              >
                <option value="Parent / Admin">Parent / Admin (Full Access)</option>
                <option value="Adult Member">Adult Member (Standard)</option>
                <option value="Teenager">Teenager (Chores Only, Shielded Finance)</option>
                <option value="Senior Member">Senior Member (Protected Health Privacy)</option>
                <option value="Guest / Visitor">Guest / Visitor (Restricted)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Avatar Icon
              </label>
              <div className="flex gap-1.5 flex-wrap">
                {['👨', '👩', '👦', '👧', '👵', '👴', '🧑', '👤'].map((emoji) => (
                  <button
                    key={emoji}
                    type="button"
                    onClick={() => setMemberAvatar(emoji)}
                    className={`w-9 h-9 rounded-xl flex items-center justify-center text-lg border transition-all ${
                      memberAvatar === emoji
                        ? 'border-[#5E9278] bg-[#5E9278]/15 font-bold scale-105'
                        : 'border-[#D9D8D2] dark:border-[#2D322E] bg-black/[0.02] dark:bg-white/[0.02]'
                    }`}
                  >
                    {emoji}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Initial Availability
              </label>
              <select
                value={memberAvailability}
                onChange={(e) => setMemberAvailability(e.target.value)}
                className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
              >
                <option value="Available">Available</option>
                <option value="At Work">At Work</option>
                <option value="In School / College">In School / College</option>
                <option value="Traveling / Away">Traveling / Away</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
              Context Notes / Schedule
            </label>
            <Input
              value={memberStatusText}
              onChange={(e) => setMemberStatusText(e.target.value)}
              placeholder="e.g. Arriving Saturday for 3-day family visit..."
            />
          </div>

          <div>
            <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
              Dietary Profile & Directives
            </label>
            <Input
              value={memberDietaryNotes}
              onChange={(e) => setMemberDietaryNotes(e.target.value)}
              placeholder="e.g. Vegetarian, Strict Low-Salt, Gluten intolerant..."
            />
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setIsInviteModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="primary"
              size="sm"
            >
              Add Household Member
            </Button>
          </div>
        </form>
      </Modal>

      {/* Edit Member Modal */}
      <Modal
        isOpen={Boolean(editingMember)}
        onClose={() => setEditingMember(null)}
        title={editingMember ? `Edit ${editingMember.name}` : 'Edit Member'}
        subtitle="Update household clearance and availability context"
      >
        {editingMember && (
          <form onSubmit={handleSaveMemberEdit} className="space-y-4 text-xs">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                  Role & Clearance
                </label>
                <select
                  value={editRole}
                  onChange={(e) => setEditRole(e.target.value)}
                  className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
                >
                  <option value="Parent / Administrator">Parent / Admin (Full Access)</option>
                  <option value="Adult / Member">Adult / Member (Standard)</option>
                  <option value="Teenager">Teenager (Restricted, Chores Only)</option>
                  <option value="Senior Family Member">Senior (Protected Health Privacy)</option>
                  <option value="Guest / Visitor">Guest / Visitor (Restricted)</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                  Availability Status
                </label>
                <select
                  value={editAvailability}
                  onChange={(e) => setEditAvailability(e.target.value)}
                  className="w-full min-h-[40px] px-3 py-2 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none text-xs"
                >
                  <option value="Available">Available</option>
                  <option value="At Work">At Work</option>
                  <option value="In School / College">In School / College</option>
                  <option value="Traveling / Away">Traveling / Away</option>
                </select>
              </div>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Context / Daily Status
              </label>
              <Input
                value={editStatusText}
                onChange={(e) => setEditStatusText(e.target.value)}
                placeholder="e.g. Traveling for business conference until Friday evening"
                required
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setEditingMember(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
              >
                Save Changes
              </Button>
            </div>
          </form>
        )}
      </Modal>
    </div>
  );
};
