import { z } from 'zod';

export const tenantIdSchema = z.string().min(1);
export const correlationIdSchema = z.string().min(1);
export const capabilitySchema = z.record(z.string(), z.boolean());