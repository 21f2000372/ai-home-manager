import React, { useState } from 'react';
import { useHousehold } from '../../context/HouseholdContext';
import { Card } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { Input } from '../ui/Input';
import { 
  CheckSquare, 
  CheckCircle2, 
  Plus, 
  Filter, 
  Clock, 
  User, 
  Calendar 
} from 'lucide-react';

export const TasksView = () => {
  const { state, activeUser, toggleTask, addTask } = useHousehold();
  const [filterMember, setFilterMember] = useState('all');
  const [filterStatus, setFilterStatus] = useState('pending');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);

  // Form State
  const [title, setTitle] = useState('');
  const [assignee, setAssignee] = useState(activeUser.id);
  const [dueDate, setDueDate] = useState('Today');
  const [priority, setPriority] = useState('medium');
  const [category, setCategory] = useState('General');
  const [recurring, setRecurring] = useState('None');

  const filteredTasks = state.tasks.filter((task) => {
    if (filterMember !== 'all' && task.assignedTo !== filterMember) return false;
    if (filterStatus === 'pending' && task.status === 'completed') return false;
    if (filterStatus === 'completed' && task.status !== 'completed') return false;
    return true;
  });

  const handleCreateTask = (e) => {
    e.preventDefault();
    if (!title.trim()) return;
    addTask({
      title,
      assignedTo: assignee,
      dueDate,
      priority,
      category,
      recurring,
    });
    setTitle('');
    setRecurring('None');
    setIsAddModalOpen(false);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fade-in pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-[#171918] dark:text-[#EFF1EC]">
            Household Tasks
          </h2>
          <p className="text-xs sm:text-sm text-[#676B68] dark:text-[#969D96]">
            Chores and family responsibilities coordinated across household members.
          </p>
        </div>

        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsAddModalOpen(true)}
          icon={Plus}
        >
          Add Task
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 p-2 rounded-2xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E]">
        {/* Member Filter Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 scrollbar-none">
          <button
            onClick={() => setFilterMember('all')}
            className={`min-h-[36px] px-3 py-1 rounded-xl text-xs font-medium transition-colors active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278] ${
              filterMember === 'all'
                ? 'bg-[#5E9278] text-white font-semibold shadow-xs'
                : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC]'
            }`}
          >
            All Members
          </button>
          {state.members.map((m) => (
            <button
              key={m.id}
              onClick={() => setFilterMember(m.id)}
              className={`min-h-[36px] flex items-center gap-1.5 px-3 py-1 rounded-xl text-xs font-medium transition-colors active:scale-95 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278] ${
                filterMember === m.id
                  ? 'bg-[#5E9278] text-white font-semibold shadow-xs'
                  : 'text-[#676B68] dark:text-[#969D96] hover:text-[#171918] dark:hover:text-[#EFF1EC]'
              }`}
            >
              <span>{m.avatar}</span>
              <span>{m.name.split(' ')[0]}</span>
            </button>
          ))}
        </div>

        {/* Status Toggle */}
        <div className="flex items-center gap-1 bg-black/5 dark:bg-white/5 p-1 rounded-xl text-xs">
          <button
            onClick={() => setFilterStatus('pending')}
            className={`min-h-[32px] px-3 py-1 rounded-lg font-medium transition-colors active:scale-95 ${
              filterStatus === 'pending'
                ? 'bg-[#FAF9F6] dark:bg-[#181B18] text-[#171918] dark:text-[#EFF1EC] shadow-xs'
                : 'text-[#676B68] dark:text-[#969D96]'
            }`}
          >
            Pending
          </button>
          <button
            onClick={() => setFilterStatus('completed')}
            className={`min-h-[32px] px-3 py-1 rounded-lg font-medium transition-colors active:scale-95 ${
              filterStatus === 'completed'
                ? 'bg-[#FAF9F6] dark:bg-[#181B18] text-[#171918] dark:text-[#EFF1EC] shadow-xs'
                : 'text-[#676B68] dark:text-[#969D96]'
            }`}
          >
            Completed
          </button>
          <button
            onClick={() => setFilterStatus('all')}
            className={`min-h-[32px] px-3 py-1 rounded-lg font-medium transition-colors active:scale-95 ${
              filterStatus === 'all'
                ? 'bg-[#FAF9F6] dark:bg-[#181B18] text-[#171918] dark:text-[#EFF1EC] shadow-xs'
                : 'text-[#676B68] dark:text-[#969D96]'
            }`}
          >
            All
          </button>
        </div>
      </div>

      {/* Tasks List */}
      <div className="space-y-2.5">
        {filteredTasks.length === 0 ? (
          <Card className="p-8 text-center text-xs text-[#676B68] dark:text-[#969D96]">
            No tasks match the selected filter.
          </Card>
        ) : (
          filteredTasks.map((task) => {
            const isCompleted = task.status === 'completed';

            return (
              <Card
                key={task.id}
                className={`p-3.5 sm:p-4 flex items-start justify-between gap-3.5 transition-all ${
                  isCompleted ? 'opacity-60 bg-black/5 dark:bg-white/5' : ''
                }`}
              >
                <div className="flex items-start gap-3 flex-1 min-w-0">
                  {/* 44px touch target button for task checkbox */}
                  <button
                    onClick={() => toggleTask(task.id)}
                    aria-label={isCompleted ? "Mark pending" : "Mark done"}
                    className="p-2 -m-2 min-h-[44px] min-w-[44px] flex items-center justify-center shrink-0 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#5E9278] rounded-lg"
                  >
                    <span className={`w-5 h-5 rounded-md border flex items-center justify-center transition-colors ${
                      isCompleted
                        ? 'bg-[#5E9278] border-[#5E9278] text-white'
                        : 'border-[#D9D8D2] dark:border-[#2D322E] hover:border-[#5E9278]'
                    }`}>
                      {isCompleted && <CheckCircle2 className="w-3.5 h-3.5" />}
                    </span>
                  </button>

                  <div className="space-y-1 flex-1 min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`text-xs sm:text-sm font-semibold ${isCompleted ? 'line-through text-[#676B68]' : 'text-[#171918] dark:text-[#EFF1EC]'}`}>
                        {task.title}
                      </span>
                      {task.reassigned && (
                        <Badge variant="warning" size="xs">
                          Reassigned from Mom
                        </Badge>
                      )}
                    </div>

                    {task.notes && (
                      <p className="text-xs text-[#676B68] dark:text-[#969D96] leading-snug">
                        {task.notes}
                      </p>
                    )}

                    <div className="flex flex-wrap items-center gap-2.5 text-[11px] text-[#676B68] dark:text-[#969D96]">
                      <span className="font-medium text-[#171918] dark:text-[#EFF1EC]">
                        {task.assignedToName}
                      </span>
                      <span>•</span>
                      <span>{task.dueDate}</span>
                      <span>•</span>
                      <span className="capitalize">{task.category}</span>
                      {task.recurring && task.recurring !== 'None' && (
                        <>
                          <span>•</span>
                          <span className="text-[#5E9278] dark:text-[#9BCDB4] font-medium flex items-center gap-0.5">
                            🔁 {task.recurring}
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                <Badge
                  variant={task.priority === 'urgent' ? 'critical' : task.priority === 'high' ? 'warning' : 'neutral'}
                  size="xs"
                >
                  {task.priority}
                </Badge>
              </Card>
            );
          })
        )}
      </div>

      {/* Add Task Modal */}
      <Modal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        title="Create New Task"
        subtitle="Add a task to the household schedule"
      >
        <form onSubmit={handleCreateTask} className="space-y-4 text-xs">
          <div>
            <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
              Task Name
            </label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Clean the patio furniture..."
              required
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Assign To
              </label>
              <select
                value={assignee}
                onChange={(e) => setAssignee(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none"
              >
                {state.members.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Due Date
              </label>
              <Input
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                placeholder="e.g. Thursday 5 PM"
              />
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2.5">
            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Category
              </label>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none"
              >
                <option value="General">General</option>
                <option value="Food">Food</option>
                <option value="Health">Health</option>
                <option value="Maintenance">Maintenance</option>
                <option value="Hospitality">Hospitality</option>
              </select>
            </div>

            <div>
              <label className="block font-medium text-[#171918] dark:text-[#EFF1EC] mb-1">
                Recurring Rule
              </label>
              <select
                value={recurring}
                onChange={(e) => setRecurring(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-[#FAF9F6] dark:bg-[#181B18] border border-[#D9D8D2] dark:border-[#2D322E] text-[#171918] dark:text-[#EFF1EC] outline-none"
              >
                <option value="None">None (One-off)</option>
                <option value="Daily">Daily</option>
                <option value="Weekly">Weekly</option>
                <option value="Monthly">Monthly</option>
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[#D9D8D2] dark:border-[#2D322E]">
            <Button
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
              Create Task
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
