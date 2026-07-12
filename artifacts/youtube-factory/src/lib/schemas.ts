import { z } from "zod";

export const projectSchema = z.object({
  title: z.string().min(1, "Title is required"),
  topic: z.string().min(1, "Topic is required"),
  description: z.string().optional(),
  tags: z.string().optional(), // We'll split this by comma
});
