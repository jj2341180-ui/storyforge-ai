import { Copy, Download, FileVideo, Image as ImageIcon, Rocket, RefreshCw, ShieldAlert, Square, Zap } from "lucide-react";
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { api } from "../../api";
import type { Job, Project, YouTubeMetadata } from "../../types";
import { ASPECTS } from "../../constants";
import { flushProject } from "../../saving";
import { Badge, EmptyState, Notice, ProgressBar, Spinner } from "../common";

export default function ExportPanel({
  project,
  update,
  notify,
}: {
  project: Project;
  update: (patch: Partial<Project>) => void;
  notify: (msg: string, tone?: "ok" | "err") => void;
}) {
  const [job, setJob] = useState<Job | null>(null);
  const [previewJob, setPreviewJob] = useState<Job | null>(null);
  const previewTimer = useRef<number | null>(null);
  const [meta, setMeta] = useState<YouTubeMetadata | null>(null);
  const [thumbTitle, setThumbTitle] = useState(project.script.title || project.name);
  const [thumbPlacement, setThumbPlacement] = useState("bottom");
  const [thumbAspect, setThumbAspect] = useState<string>(project.timeline.aspect);
  const [thumbBg, setThumbBg] = useState("");
  const [thumbUrl, setThumbUrl] = useState<string | null>(null);
  const timer = useRef<number | null>(null);
  const [now, setNow] = useState(Date.now());
  const [jobList, setJobList] = useState<Job[]>([]);
  const [jobsLoaded, setJobsLoaded] = useState(false);
  const restoreInput = useRef<HTMLInputElement | null>(null);

  const refreshJobs = () =>
    api.jobs(project.id)
      .then((jobs) => { setJobList(jobs); setJobsLoaded(true); })
      .catch(() => setJobsLoaded(true));

  // Completed render jobs are the fallback source of downloadable videos whenever the
  // project document's exports list is empty (e.g. the app was reopened after a server
  // restart on the free host).
  useEffect(() => {
    setJobsLoaded(false);
    refreshJobs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, project.exports.length]);

  const isActive = (j: Job | null) =>
    Boolean(j && ["queued", "running", "finalizing"].includes(j.status));

  useEffect(() => () => {
    if (timer.current) window.clearInterval(timer.current);
    if (previewTimer.current) window.clearInterval(previewTimer.current);
  }, []);

  // One-second ticker so the elapsed timer under the progress bar keeps moving.
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  // Coming back to the tab (or reopening it) must immediately re-sync job state instead of
  // waiting for the next 1.5s poll - and these polls double as keep-awake traffic for the
  // free host, which sleeps after 15 minutes without inbound requests.
  useEffect(() => {
    const resume = () => {
      if (job) api.job(job.id).then(setJob).catch(() => undefined);
      if (previewJob) api.job(previewJob.id).then(setPreviewJob).catch(() => undefined);
    };
    document.addEventListener("visibilitychange", resume);
    return () => document.removeEventListener("visibilitychange", resume);
  }, [job, previewJob]);

  // Reattach to renders started before a reload / navigation so a refresh never orphans
  // the progress bar. The most recent job of each kind wins.
  useEffect(() => {
    api.jobs(project.id).then((jobs) => {
      const active = jobs.filter((j) => isActive(j));
      const full = active.find((j) => j.kind === "render");
      const preview = active.find((j) => j.kind === "render-preview");
      if (full && !isActive(job)) {
        setJob(full);
        pollJob(full, setJob, async () => {
          update(await api.getProject(project.id));
          refreshJobs();
          notify("MP4 rendered and saved to your project");
        }, timer);
      }
      if (preview && !isActive(previewJob)) {
        setPreviewJob(preview);
        pollJob(preview, setPreviewJob,
          () => notify("Fast preview ready — check exported videos below"), previewTimer);
      }
    }).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  const pollJob = (j: Job, setter: (j: Job) => void, onDone: () => void,
                   intervalRef: MutableRefObject<number | null>) => {
    if (intervalRef.current) window.clearInterval(intervalRef.current);
    intervalRef.current = window.setInterval(async () => {
      try {
        const fresh = await api.job(j.id);
        setter(fresh);
        if (fresh.status === "done" || fresh.status === "failed") {
          if (intervalRef.current) window.clearInterval(intervalRef.current);
          if (fresh.status === "done") {
            onDone();
          } else {
            notify(fresh.message || "Render failed", "err");
          }
        }
      } catch {
        /* network blip: keep polling; the backend watchdog settles truly dead jobs */
      }
    }, 1500);
  };

  const cancelJob = async (j: Job, setter: (j: Job) => void,
                          intervalRef: MutableRefObject<number | null>) => {
    try {
      await api.cancelJob(j.id);
      notify("Cancelling render…");
      for (let i = 0; i < 20; i += 1) {
        await new Promise((r) => setTimeout(r, 1000));
        const fresh = await api.job(j.id);
        setter(fresh);
        if (fresh.status === "done" || fresh.status === "failed") {
          if (intervalRef.current) window.clearInterval(intervalRef.current);
          break;
        }
      }
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const startRender = async (preview = false) => {
    try {
      await flushProject(project.id);
      const j = await api.render(project.id, preview ? "360p" : undefined);
      if (preview) {
        setPreviewJob(j);
        pollJob(j, setPreviewJob, () => {
          refreshJobs();
          notify("Fast preview ready — check exported videos below");
        }, previewTimer);
      } else {
        setJob(j);
        pollJob(j, setJob, async () => {
          update(await api.getProject(project.id));
          refreshJobs();
          notify("MP4 rendered and saved to your project");
        }, timer);
      }
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const loadMeta = async () => {
    try {
      await flushProject(project.id);
      setMeta(await api.metadata(project.id));
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const makeThumb = async () => {
    try {
      await flushProject(project.id);
      const asset = await api.thumbnail(project.id, {
        title: thumbTitle,
        placement: thumbPlacement,
        aspect: thumbAspect,
        background_asset_id: thumbBg || null,
      });
      update({ assets: [...project.assets, asset] });
      setThumbUrl(api.mediaUrl(asset.path));
      notify("Thumbnail generated locally");
    } catch (e) {
      notify((e as Error).message, "err");
    }
  };

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    notify("Copied to clipboard");
  };

  const running = job && ["queued", "running", "finalizing"].includes(job.status);
  const previewRunning = previewJob && ["queued", "running", "finalizing"].includes(previewJob.status);

  return (
    <div className="space-y-6">
      {/* Render */}
      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
          <Rocket className="w-5 h-5 text-gold-400" /> Render & export MP4
        </h2>
        <div className="flex flex-wrap gap-3 text-sm">
          <Badge tone="blue">{project.timeline.aspect}</Badge>
          <Badge tone="blue">{project.timeline.resolution}</Badge>
          <Badge tone="neutral">{project.scenes.length} scenes</Badge>
          <Badge tone="amber">Image-based cinematic video (Ken Burns)</Badge>
          <Badge tone="neutral">H.264 + AAC</Badge>
          <Badge tone={project.timeline.burn_captions ? "green" : "neutral"}>
            {project.timeline.burn_captions ? "Captions on" : "Captions off"}
          </Badge>
        </div>
        {!project.scenes.length && (
          <Notice tone="warn">Add scenes before rendering.</Notice>
        )}
        <div className="grid sm:grid-cols-2 gap-3">
          <button className="btn-secondary" disabled={Boolean(running) || Boolean(previewRunning) || !project.scenes.length}
            onClick={() => startRender(true)}>
            {previewRunning ? <Spinner label="Building fast preview…" /> : <><Zap className="w-4 h-4" /> Fast preview (360p draft, quickest)</>}
          </button>
          <button className="btn-primary" disabled={Boolean(running) || Boolean(previewRunning) || !project.scenes.length}
            onClick={() => startRender(false)}>
            {running ? <Spinner label="Rendering — see progress below" /> : <><FileVideo className="w-4 h-4" /> Full quality render ({project.timeline.resolution})</>}
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Fast preview builds a 360p draft at 20 fps with static framed scenes and the speed-first encoder, so it
          finishes in minutes even on the free server; full quality uses your saved resolution, 30 fps and the Ken
          Burns motion with the high-quality encoder. The bar moves continuously, a stalled render is stopped
          automatically after 4 minutes of silence, and Cancel render stops it immediately. Keep this tab open while
          rendering so the free server stays awake.
        </p>
        {previewJob && (
          <div className="space-y-2">
            <ProgressBar value={previewJob.progress} message={`Preview · ${previewJob.message}`} />
            {isActive(previewJob) && (
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-400">
                  Elapsed {Math.max(0, Math.floor((now - previewJob.created_at * 1000) / 1000))}s · keep this tab open while rendering
                </span>
                <button className="btn-secondary text-xs px-3 py-1.5"
                  onClick={() => cancelJob(previewJob, setPreviewJob, previewTimer)}>
                  <Square className="w-3.5 h-3.5" /> Cancel render
                </button>
              </div>
            )}
            {previewJob.status === "failed" && (
              <div className="rounded-xl bg-red-950/50 border border-red-900 p-3 text-sm text-red-200 whitespace-pre-wrap">
                {previewJob.message}
              </div>
            )}
            {previewJob.status === "done" && <Notice tone="ok">Fast preview complete — play and download it below.</Notice>}
          </div>
        )}
        {job && (
          <div className="space-y-2">
            <ProgressBar value={job.progress} message={job.message} />
            {isActive(job) && (
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs text-slate-400">
                  Elapsed {Math.max(0, Math.floor((now - job.created_at * 1000) / 1000))}s · keep this tab open while rendering
                </span>
                <button className="btn-secondary text-xs px-3 py-1.5"
                  onClick={() => cancelJob(job, setJob, timer)}>
                  <Square className="w-3.5 h-3.5" /> Cancel render
                </button>
              </div>
            )}
            {job.status === "failed" && (
              <div className="rounded-xl bg-red-950/50 border border-red-900 p-3 text-sm text-red-200 whitespace-pre-wrap">
                {job.message}
              </div>
            )}
            {job.status === "done" && <Notice tone="ok">Export complete — download it below.</Notice>}
          </div>
        )}
      </div>

      {/* Exports: project exports merged with every finished render job, so a completed
          video always has a visible download even if a server restart cleared the list. */}
      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100">Exported videos — download anytime</h2>
        {(() => {
          const doneJobs = jobList.filter(
            (j) => j.status === "done" && j.result?.file &&
              (j.kind === "render" || j.kind === "render-preview"),
          );
          const seen = new Set<string>();
          type VideoRow = {
            key: string; file: string; width?: number; height?: number;
            duration?: number; placeholders?: number; tag: string; exists: boolean;
          };
          const videos: VideoRow[] = [];
          for (const ex of project.exports) {
            if (!ex.file || seen.has(ex.file)) continue;
            seen.add(ex.file);
            const match = doneJobs.find((j) => (j.result?.file as string) === ex.file);
            videos.push({
              key: ex.job_id || ex.file, file: ex.file,
              width: ex.width, height: ex.height, duration: ex.duration,
              placeholders: ex.used_placeholders?.length, tag: "Saved export",
              // Wait for job rows before showing a player, so a wiped file never fires a
              // 404; once loaded, an export without a job row is assumed present (restored
              // projects keep their files even though old job rows are gone).
              exists: jobsLoaded ? (match ? match.file_exists !== false : true) : false,
            });
          }
          for (const j of doneJobs) {
            const result = j.result;
            if (!result?.file) continue;
            const file = result.file as string;
            if (seen.has(file)) continue;
            seen.add(file);
            videos.push({
              key: j.id, file,
              width: result.width as number, height: result.height as number,
              duration: result.duration as number, tag: j.kind === "render-preview" ? "Fast preview" : "Full render",
              exists: j.file_exists !== false,
            });
          }
          if (videos.length === 0) {
            return <EmptyState icon={<FileVideo className="w-6 h-6" />} title="No exports yet" hint="Run the renderer to produce a real downloadable MP4." />;
          }
          if (!jobsLoaded) {
            return <Spinner label="Checking exported videos…" />;
          }
          return (
            <div className="space-y-4">
              {videos.slice().reverse().map((v) => (
                <div key={v.key} className="bg-ink-900 rounded-xl p-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Badge tone="blue">{v.tag}</Badge>
                    {v.width ? <Badge tone="neutral">{v.width}×{v.height} · {v.duration}s</Badge> : null}
                  </div>
                  {v.exists ? (
                    <>
                      <video controls src={api.mediaUrl(v.file)} className="w-full max-h-[380px] rounded-lg bg-black" />
                      <div className="flex flex-wrap items-center gap-2">
                        <a className="btn-primary text-xs px-4 py-2"
                          href={api.exportDownloadUrl(project.id, v.file)}
                          download={v.file.split("/").pop() || "storyforge-video.mp4"}>
                          <Download className="w-3.5 h-3.5" /> Download MP4
                        </a>
                        {v.placeholders ? <Badge tone="amber">contains {v.placeholders} placeholder frame(s)</Badge> : null}
                      </div>
                    </>
                  ) : (
                    <Notice tone="warn">
                      This video was stored on the free server's temporary disk and was cleared when the server
                      restarted or updated. Render it again and press Download MP4 right away, or restore a project
                      backup zip below.
                    </Notice>
                  )}
                </div>
              ))}
            </div>
          );
        })()}
      </div>

      {/* Project backup & restore: the permanent, zero-cost home for the work, since the
          free host wipes its disk on every redeploy/restart. */}
      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100">Project backup &amp; restore</h2>
        <p className="text-xs text-slate-500">
          The free server clears its storage whenever it restarts or updates. Download a backup zip after each
          session — it contains the story, every image/audio asset and all exported videos. Re-upload the zip here
          to bring the whole project back.
        </p>
        <div className="flex flex-wrap gap-3">
          <a className="btn-secondary" href={api.backupUrl(project.id)} download>
            <Download className="w-4 h-4" /> Download project backup (.zip)
          </a>
          <button className="btn-secondary" onClick={() => restoreInput.current?.click()}>
            <RefreshCw className="w-4 h-4" /> Restore project from backup (.zip)
          </button>
          <input ref={restoreInput} type="file" accept=".zip" className="hidden"
            onChange={async (e) => {
              const file = e.target.files?.[0];
              if (!file) return;
              try {
                await api.restoreBackup(file);
                notify("Project restored as a new project — opening Home so you can select it");
                window.setTimeout(() => { window.location.href = "/"; }, 1500);
              } catch (err) {
                notify((err as Error).message, "err");
              } finally {
                e.target.value = "";
              }
            }} />
        </div>
      </div>

      {/* Thumbnail */}
      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100 flex items-center gap-2">
          <ImageIcon className="w-5 h-5 text-gold-400" /> Thumbnail concept
        </h2>
        <div className="grid md:grid-cols-2 gap-3">
          <div>
            <label className="label">Title text on thumbnail</label>
            <input className="input" value={thumbTitle} onChange={(e) => setThumbTitle(e.target.value)} />
          </div>
          <div>
            <label className="label">Text placement</label>
            <select className="input" value={thumbPlacement} onChange={(e) => setThumbPlacement(e.target.value)}>
              <option value="top">Top</option>
              <option value="center">Center</option>
              <option value="bottom">Bottom</option>
            </select>
          </div>
          <div>
            <label className="label">Background image (optional)</label>
            <select className="input" value={thumbBg} onChange={(e) => setThumbBg(e.target.value)}>
              <option value="">Auto-generated cinematic background</option>
              {project.assets.filter((a) => a.kind === "image").map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="label">Format</label>
            <select className="input" value={thumbAspect} onChange={(e) => setThumbAspect(e.target.value)}>
              {ASPECTS.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            </select>
          </div>
        </div>
        <button className="btn-secondary" onClick={makeThumb}><RefreshCw className="w-4 h-4" /> Generate thumbnail</button>
        {thumbUrl && (
          <div className="space-y-2">
            <img src={thumbUrl} alt="Thumbnail preview" className="w-full max-w-md rounded-xl border border-ink-700" />
            <p className="text-xs text-slate-400">Small-size preview (as it may appear in search):</p>
            <img src={thumbUrl} alt="Small thumbnail" className="w-40 rounded-lg border border-ink-700" />
            <a className="btn-ghost text-xs px-2 py-1 border border-ink-600" href={thumbUrl} download>
              <Download className="w-3.5 h-3.5" /> Download thumbnail PNG
            </a>
          </div>
        )}
      </div>

      {/* YouTube metadata */}
      <div className="card p-5 space-y-4">
        <h2 className="font-display text-xl text-slate-100">YouTube metadata</h2>
        <button className="btn-secondary" onClick={loadMeta}>Generate titles, description & hashtags</button>
        {meta && (
          <div className="space-y-4 text-sm">
            <div>
              <p className="label">Three title options</p>
              {meta.title_options.map((t, i) => (
                <div key={i} className="flex items-center gap-2 bg-ink-900 rounded-lg px-3 py-2 mb-1.5">
                  <span className="flex-1 text-slate-200">{t}</span>
                  <button className="btn-ghost p-1" onClick={() => copy(t)}><Copy className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
            <div>
              <p className="label">Description {meta.chapters.length ? `(with ${meta.chapters.length} chapter timestamps)` : ""}</p>
              <pre className="bg-ink-900 rounded-lg p-3 whitespace-pre-wrap text-slate-300 text-xs max-h-64 overflow-y-auto">{meta.description}</pre>
              <button className="btn-ghost text-xs mt-1 border border-ink-600" onClick={() => copy(meta.description)}><Copy className="w-3.5 h-3.5" /> Copy description</button>
            </div>
            <div className="grid md:grid-cols-2 gap-3">
              <div>
                <p className="label">Keywords</p>
                <div className="flex flex-wrap gap-1.5">{meta.keywords.map((k) => <Badge key={k} tone="neutral">{k}</Badge>)}</div>
              </div>
              <div>
                <p className="label">Hashtags</p>
                <div className="flex flex-wrap gap-1.5">{meta.hashtags.map((h) => <Badge key={h} tone="blue">{h}</Badge>)}</div>
              </div>
            </div>
            <div>
              <p className="label">Pinned comment suggestion</p>
              <div className="flex items-center gap-2 bg-ink-900 rounded-lg px-3 py-2">
                <span className="flex-1 text-slate-300">{meta.pinned_comment}</span>
                <button className="btn-ghost p-1" onClick={() => copy(meta.pinned_comment)}><Copy className="w-3.5 h-3.5" /></button>
              </div>
            </div>
          </div>
        )}
      </div>

      <Notice tone="ok">
        <ShieldAlert className="w-4 h-4" />
        <div>
          <p className="font-semibold">Disclosure handled automatically</p>
          <p className="mt-1">
            Every generated description and pinned comment now includes an AI-assisted / synthetic-content
            disclosure block, so it travels with the text when you paste it into YouTube. You still need to toggle
            YouTube's own "altered or synthetic content" switch during upload. StoryForge does not guarantee rankings,
            views, monetization or copyright clearance — verify every asset's license yourself.
          </p>
        </div>
      </Notice>
    </div>
  );
}
