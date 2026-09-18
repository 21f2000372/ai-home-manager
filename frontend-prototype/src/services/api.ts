// HomeOps API Layer Interface
// Provides structured boundaries between UI components and backend/agent microservices.
import { householdService } from './householdService';
import { agentService } from './agentService';

export const api = {
  // Household State & Data
  async getHouseholdState() {
    return householdService.getState();
  },

  async getRawHouseholdState() {
    return householdService.getRawState();
  },

  async resetHouseholdState() {
    householdService.resetToBaseline();
    return { success: true };
  },

  // Active User / Persona & RBAC
  async setActiveUser(userId) {
    householdService.setActiveUser(userId);
    return householdService.getActiveUser();
  },

  async getActiveUser() {
    return householdService.getActiveUser();
  },

  // Tasks & Operations
  async toggleTask(taskId) {
    householdService.toggleTaskStatus(taskId);
    return { success: true };
  },

  async createTask(taskData) {
    householdService.addTask(taskData);
    return { success: true };
  },

  // Multi-Agent Execution & Planning
  async submitHouseholdUpdate(prompt, userId, onStepCallback) {
    return agentService.processQuery(prompt, userId, onStepCallback);
  },

  async applyCoordinatedPlan(plan) {
    const success = householdService.applyCoordinatedPlan(plan);
    return { success };
  },
};
