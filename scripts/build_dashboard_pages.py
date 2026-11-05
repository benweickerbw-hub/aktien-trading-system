#!/usr/bin/env python3
"""Publish the existing private Aktien Dashboard as a public GitHub Pages artifact.

Only dashboard/template.html, dashboard/positions.json and dashboard/research.json
are rendered into public/index.html. Other private repository files are NOT shipped.
"""
from __future__ import annotations
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
PUBLIC = ROOT / "public"

def inline_json(value: object) -> str:
    # Prevent a string inside a data file from breaking the surrounding <script>.
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            .replace("&", r"\u0026")
            .replace("<", r"\u003c")
            .replace(">", r"\u003e")
            .replace("\u2028", r"\u2028")
            .replace("\u2029", r"\u2029"))

def replace_one(html: str, begin: str, end: str, replacement: str) -> str:
    pattern = re.compile(re.escape(begin) + r"[\s\S]*?" + re.escape(end))
    html, count = pattern.subn(lambda _m: replacement, html, count=1)
    if count != 1:
        raise RuntimeError(f"Expected exactly one template marker: {begin}")
    return html

def main() -> None:
    template = (DASHBOARD / "template.html").read_text(encoding="utf-8")
    positions = json.loads((DASHBOARD / "positions.json").read_text(encoding="utf-8"))
    research = json.loads((DASHBOARD / "research.json").read_text(encoding="utf-8"))
    if not isinstance(positions.get("trades"), list) or not isinstance(research.get("runs"), list):
        raise ValueError("Dashboard JSON has an unexpected schema; refusing to publish.")
    if not isinstance(research.get("deep_dives", {}), dict):
        raise ValueError("deep_dives must be an object.")
    template = replace_one(template, "/*__POSITIONS_JSON_BEGIN__*/",
                           "/*__POSITIONS_JSON_END__*/", inline_json(positions))
    template = replace_one(template, "/*__RESEARCH_JSON_BEGIN__*/",
                           "/*__RESEARCH_JSON_END__*/", inline_json(research))
    sha = os.environ.get("GITHUB_SHA", "local-preview").strip()
    site_build = "const __SITE_BUILD_SHA__ = " + json.dumps(sha) + ";\n"
    if "<script>\nconst DATA" not in template:
        raise RuntimeError("Could not locate dashboard JS entry point.")
    template = template.replace("<script>\nconst DATA", "<script>\n" + site_build + "const DATA", 1)

    # Live-update only when the DEPLOYED snapshot has changed. Preserve tabs, filters and hash routes.
    old_refresh = "setInterval(()=>{if(!document.hidden)location.reload()},90000);overview();show();"
    new_refresh = """setInterval(async()=>{
  if(document.hidden)return;
  try {
    const res=await fetch('release.json?t='+Date.now(),{cache:'no-store'});
    if(!res.ok)return;
    const latest=await res.json();
    if(latest.build_sha && latest.build_sha!==__SITE_BUILD_SHA__){
      const url=new URL(window.location.href);
      url.searchParams.set('rev',String(latest.build_sha).slice(0,12));
      window.location.replace(url.toString());
    }
  } catch(e) { console.debug('Pages revision check unavailable',e); }
},60000);overview();show();"""
    if old_refresh not in template:
        raise RuntimeError("Dashboard refresh hook changed; adapt the publisher.")
    template = template.replace(old_refresh, new_refresh, 1)
    if not template.lstrip().lower().startswith("<!doctype html>"):
        raise ValueError("Rendered content is not HTML.")
    if "/*__POSITIONS_JSON_BEGIN__*/" in template or "/*__RESEARCH_JSON_BEGIN__*/" in template:
        raise ValueError("Unexpanded JSON markers in rendered page.")
    PUBLIC.mkdir(parents=True, exist_ok=True)
    (PUBLIC / "index.html").write_text(template, encoding="utf-8")
    (PUBLIC / ".nojekyll").write_text("", encoding="utf-8")
    (PUBLIC / "release.json").write_text(
        json.dumps({"build_sha":sha,"built_at":datetime.now(timezone.utc).isoformat(),
                    "positions_updated_at":positions.get("updated_at"),
                    "research_updated_at":research.get("updated_at"),
                    "public_notice":"All dashboard data in this deployment is public."},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Generated public/index.html ({len(template):,} characters); trades: {len(positions['trades'])}; research runs: {len(research['runs'])}; commit: {sha}")

if __name__ == "__main__":
    main()
