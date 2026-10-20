import Link from "next/link";
import { redirect } from "next/navigation";
import { ArrowLeft, ArrowUpRight, Database, Eye, LockKeyhole, ShieldCheck } from "lucide-react";
import Github from "@/components/admin/github-icon";
import { getAdmin } from "@/lib/admin-auth";
import { adminConfig } from "@/lib/admin-session";

const errors: Record<string, string> = {
  configuration: "GitHub sign-in is not configured yet. Complete the server setup in frontend/README.md.",
  state: "This sign-in request expired or could not be verified. Please try again.",
  cancelled: "GitHub sign-in was cancelled. You can try again when you're ready.",
  provider: "We couldn't complete GitHub sign-in. Please try again.",
  denied: "This GitHub account isn't on the administrator allowlist. Use an approved account.",
};

export default async function LoginPage({ searchParams }: { searchParams: Promise<Record<string, string | string[] | undefined>> }) {
  if (await getAdmin()) redirect("/admin/crawler");
  const params = await searchParams;
  const ready = adminConfig().ready;
  const message = typeof params.error === "string" ? errors[params.error] : undefined;
  return <main className="admin-login">
    <Link href="/" className="admin-back"><ArrowLeft size={15} /> Back to Developer&apos;s Eye</Link>
    <section className="admin-login-card">
      <div className="admin-wordmark"><span className="admin-eye"><Eye size={23} /></span> developer&apos;s eye<span className="admin-accent">.</span></div>
      <div className="admin-login-art" aria-hidden="true"><div className="admin-orbit orbit-one" /><div className="admin-orbit orbit-two" /><div className="admin-orbit orbit-three" /><div className="admin-login-core"><Eye size={40} strokeWidth={1.2} /></div><span className="admin-orbit-node" /></div>
      <span className="admin-kicker"><LockKeyhole size={12} /> THE CONTROL ROOM</span>
      <h1>A closer look.<br /><span>Behind the search.</span></h1>
      <p>Follow every crawl, inspect the queue, and see how your developer knowledge index grows.</p>
      {(message || !ready) && <div className="admin-login-notice" role="status">{message || "Administrator sign-in needs configuration. Follow the GitHub OAuth setup in frontend/README.md."}</div>}
      {ready ? <a className="admin-button primary admin-github" href="/api/auth/github"><Github size={19} /> Continue with GitHub <ArrowUpRight size={17} /></a> : <button className="admin-button primary admin-github" disabled><Github size={19} /> GitHub sign-in not configured</button>}
      <div className="admin-login-trust"><ShieldCheck size={14} /> Approved administrators only <span>·</span> GitHub authentication</div>
      <div className="admin-login-bottom"><Database size={14} /><span>Your crawler. Your infrastructure. One clear view.</span></div>
    </section>
    <div className="admin-login-footer">DEVELOPER&apos;S EYE <span>ADMINISTRATION / 01</span></div>
  </main>;
}
