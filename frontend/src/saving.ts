// Registry that lets any panel force an immediate project save, bypassing the
// debounced autosave. Needed before API calls that reference freshly created scenes.
type Flusher = () => Promise<void>;

const flushers = new Map<string, Flusher>();

export function registerFlusher(projectId: string, fn: Flusher): void {
  flushers.set(projectId, fn);
}

export function unregisterFlusher(projectId: string): void {
  flushers.delete(projectId);
}

export async function flushProject(projectId: string): Promise<void> {
  await flushers.get(projectId)?.();
}
