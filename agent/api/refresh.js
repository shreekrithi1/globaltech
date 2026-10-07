// Weekly Vercel Cron (Wednesdays 14:00 UTC): asks Vercel to redeploy, which re-runs the events agent.
// Needs two project environment variables: DEPLOY_HOOK_URL (Settings → Git → Deploy Hooks)
// and CRON_SECRET (any random string; Vercel sends it automatically with cron requests).
module.exports = async function handler(req, res) {
  const secret = process.env.CRON_SECRET;
  if (secret && req.headers.authorization !== `Bearer ${secret}`) {
    return res.status(401).json({ ok: false, error: "unauthorized" });
  }
  const hook = process.env.DEPLOY_HOOK_URL;
  if (!hook) return res.status(500).json({ ok: false, error: "DEPLOY_HOOK_URL is not set" });
  const r = await fetch(hook, { method: "POST" });
  const body = await r.text();
  return res.status(r.ok ? 200 : 502).json({ ok: r.ok, status: r.status, deploy: body.slice(0, 300) });
};
